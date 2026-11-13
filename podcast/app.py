"""Podcast GPT V2: local single-user studio. Do not expose this server publicly."""
from __future__ import annotations
import hashlib
import json
import subprocess
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Literal
from fastapi import FastAPI,HTTPException,File,UploadFile,Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image,ImageOps,UnidentifiedImageError
from .settings import BASE,DATA,SPEAKERS
from .workspace import active_workspace,choose_workspace,list_workspaces,new_workspace,get_workspace
from .project import load_project,save_project
from .voice import audio_paths,synthesize_line,wav_length,set_uploaded_audio,reset_line_audio,uploaded_marker
from .video import (ffmpeg_path,sadtalker_ready,scene_image,render_static,render_motion,
                    render_sadtalker,join_clips,output_name)
from .subtitles import write_srt

app=FastAPI(title='Podcast GPT V2',docs_url=None,redoc_url=None)
app.mount('/files',StaticFiles(directory=str(DATA)),name='files')
app.mount('/static',StaticFiles(directory=str(BASE/'static')),name='static')
_executor=ThreadPoolExecutor(max_workers=1)
_lock=threading.Lock()
_jobs:dict[str,dict]={}
_cancel_events:dict[str,threading.Event]={}
_active:str|None=None


class RenderRequest(BaseModel):
    mode:Literal['static','motion','ai']='static'
    quality:Literal['720p','1080p']='720p'

class CreateProject(BaseModel):
    title:str=Field(min_length=1,max_length=120)
    topic:str=Field(default='',max_length=240)
    target_minutes:float=Field(default=10,ge=1,le=120)


def current_job():
    with _lock:
        if _active and _jobs.get(_active,{}).get('state') in {'queued','running','cancelling'}:
            return _jobs[_active].copy()
        return None


def _job_update(job_id:str,**fields):
    with _lock:
        _jobs[job_id].update(fields)


def _runner(job_id:str,fn):
    global _active
    try:
        _job_update(job_id,state='running')
        result=fn(job_id)
        _job_update(job_id,state='done',progress=100,message='Completed',result=result)
    except InterruptedError:
        _job_update(job_id,state='cancelled',message='Stopped after current clip. Completed clips are cached.')
    except Exception as exc:
        traceback.print_exc()
        _job_update(job_id,state='error',message=str(exc)[:1000],error=traceback.format_exc()[-3000:])
    finally:
        with _lock:
            if _active==job_id: _active=None
            _cancel_events.pop(job_id,None)


def schedule(label:str,fn)->dict:
    global _active
    with _lock:
        if _active and _jobs[_active]['state'] in {'queued','running','cancelling'}:
            raise HTTPException(409,detail='Finish or cancel the active job first.')
        jid=uuid.uuid4().hex[:12]
        job={'id':jid,'state':'queued','label':label,'progress':0,'message':'Queued'}
        _jobs[jid]=job
        _cancel_events[jid]=threading.Event()
        _active=jid
    _executor.submit(_runner,jid,fn)
    return job


def cancelled(jid:str)->bool:
    event=_cancel_events.get(jid)
    return bool(event and event.is_set())


def safe_edit():
    if current_job(): raise HTTPException(409,detail='Finish or cancel current job before editing.')


def file_link(ws,folder:str,name:str)->str:
    return f'/files/projects/{ws.id}/{folder}/{name}'


@app.get('/')
def index(): return FileResponse(str(BASE/'static'/'index.html'))


@app.get('/api/projects')
def get_projects():
    ws=active_workspace()
    return {'active_id':ws.id,'projects':list_workspaces()}


@app.post('/api/projects')
def create_project(request:CreateProject):
    safe_edit()
    try: ws=new_workspace(request.title,request.topic,request.target_minutes)
    except ValueError as exc: raise HTTPException(400,detail=str(exc)) from exc
    return {'id':ws.id,'title':request.title}


@app.post('/api/projects/activate/{project_id}')
def activate_project(project_id:str):
    safe_edit()
    try: ws=choose_workspace(project_id)
    except ValueError as exc: raise HTTPException(404,detail=str(exc)) from exc
    return {'active_id':ws.id}


@app.get('/api/project')
def get_project():
    ws=active_workspace()
    p=load_project(ws)
    p['id']=ws.id
    p['speakers']={key:{**speaker,
                        'has_portrait':(ws.images/f'{key}.png').exists(),
                        'portrait_url':file_link(ws,'portraits',f'{key}.png')}
                   for key,speaker in p['speakers'].items()}
    total=0.0
    for line in p['lines']:
        _,wav=audio_paths(line,p['speakers'][line['speaker']],ws)
        try: duration=round(wav_length(wav),2) if wav.exists() else None
        except (OSError,EOFError,ValueError): duration=None
        line['audio_url']=file_link(ws,'wav',wav.name) if duration else None
        line['audio_origin']='uploaded' if uploaded_marker(wav).exists() else ('tts' if duration else 'missing')
        line['duration']=duration
        total+=duration or 0
        total+=float(line.get('pause_after',0)) if duration is not None else 0
    p['duration_seconds']=round(total,2)
    p['target_seconds']=round(p['target_minutes']*60,1)
    p['ready_audio']=sum(1 for x in p['lines'] if x['duration'] is not None)
    p['ai_ready']=sadtalker_ready()
    p['current_job']=current_job()
    p['last_export']=None
    exports=sorted(ws.exports.glob('podcast-*.mp4'),key=lambda x:x.stat().st_mtime,reverse=True)
    if exports: p['last_export']=file_link(ws,'exports',exports[0].name)
    return p


@app.put('/api/project')
def put_project(value:dict=Body(...)):
    safe_edit()
    ws=active_workspace()
    try: return save_project(value,ws)
    except ValueError as exc: raise HTTPException(400,detail=str(exc)) from exc


@app.post('/api/portrait/{speaker_id}')
async def upload_portrait(speaker_id:str,file:UploadFile=File(...)):
    if speaker_id not in SPEAKERS: raise HTTPException(404,detail='Unknown speaker')
    safe_edit();ws=active_workspace()
    raw=await file.read(12*1024*1024+1)
    if len(raw)>12*1024*1024: raise HTTPException(413,detail='Image exceeds 12 MB')
    try:
        with Image.open(BytesIO(raw)) as source: source.verify()
        with Image.open(BytesIO(raw)) as source:
            converted=ImageOps.exif_transpose(source).convert('RGB')
            if converted.width<200 or converted.height<200: raise ValueError('Use at least 200×200 portrait')
            if converted.width*converted.height>25_000_000: raise ValueError('Image exceeds 25 megapixels')
            converted.thumbnail((1600,1600),Image.Resampling.LANCZOS)
            temp=ws.images/f'{speaker_id}.temp.png'
            converted.save(temp,optimize=True)
            temp.replace(ws.images/f'{speaker_id}.png')
    except (ValueError,UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
        raise HTTPException(400,detail=f'Invalid image: {exc}') from exc
    return {'ok':True,'url':file_link(ws,'portraits',speaker_id+'.png')}


@app.post('/api/audio/{line_id}')
async def upload_audio(line_id:str,file:UploadFile=File(...)):
    safe_edit();ws=active_workspace();p=load_project(ws)
    line=next((x for x in p['lines'] if x['id']==line_id),None)
    if not line: raise HTTPException(404,detail='Unknown dialogue')
    raw=await file.read(20*1024*1024+1)
    try: wav=set_uploaded_audio(line,raw,Path(file.filename or '').suffix,p['speakers'][line['speaker']],ws)
    except (ValueError,RuntimeError,OSError,subprocess.CalledProcessError) as exc:
        raise HTTPException(400,detail=f'Audio conversion failed: {exc}') from exc
    return {'ok':True,'url':file_link(ws,'wav',wav.name),'duration':wav_length(wav)}


@app.post('/api/audio/{line_id}/reset')
def reset_audio(line_id:str):
    safe_edit();ws=active_workspace();p=load_project(ws)
    line=next((x for x in p['lines'] if x['id']==line_id),None)
    if not line: raise HTTPException(404,detail='Unknown dialogue')
    reset_line_audio(line,p['speakers'][line['speaker']],ws)
    return {'ok':True}


@app.post('/api/voices')
def generate_voices():
    ws=active_workspace();p=load_project(ws)
    def work(jid):
        count=len(p['lines']);total=0
        for i,line in enumerate(p['lines']):
            if cancelled(jid): raise InterruptedError()
            _job_update(jid,progress=round(i/count*100),message=f'Voice {i+1}/{count}')
            _,secs=synthesize_line(line,p['speakers'][line['speaker']],ws)
            total+=secs+float(line.get('pause_after',0))
        return {'total_duration':round(total,2)}
    return schedule('Generate voices',work)


@app.post('/api/voices/line/{line_id}')
def generate_line_voice(line_id:str):
    ws=active_workspace();p=load_project(ws)
    line=next((x for x in p['lines'] if x['id']==line_id),None)
    if not line: raise HTTPException(404,detail='Unknown dialogue')
    def work(jid):
        if cancelled(jid):raise InterruptedError()
        _,seconds=synthesize_line(line,p['speakers'][line['speaker']],ws)
        return {'duration':seconds}
    return schedule('Generate single voice',work)


def render_key(project:dict,line:dict,ws,mode:str,quality:str)->str:
    sp=project['speakers'][line['speaker']]
    wav=audio_paths(line,sp,ws)[1]
    stats=[]
    for speaker in SPEAKERS:
        path=ws.images/f'{speaker}.png'
        stats.append((speaker,path.stat().st_size,path.stat().st_mtime_ns) if path.exists() else (speaker,0,0))
    wavstat=wav.stat()
    value=[project['title'],project['speakers'],line,mode,quality,stats,wavstat.st_size,wavstat.st_mtime_ns,'v2.1']
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:18]


@app.post('/api/render')
def start_render(request:RenderRequest):
    ws=active_workspace();p=load_project(ws)
    if request.mode=='ai':
        if not sadtalker_ready():raise HTTPException(400,detail='Neural backend unavailable. Run INSTALL_AI.bat.')
        missing=[key for key in SPEAKERS if not (ws.images/f'{key}.png').is_file()]
        if missing:raise HTTPException(400,detail='Missing portraits: '+', '.join(missing))
    def work(jid):
        clips=[];durations=[];count=len(p['lines'])
        for i,line in enumerate(p['lines']):
            if cancelled(jid):raise InterruptedError()
            _job_update(jid,progress=round(95*i/count),message=f'Video {i+1}/{count} · {line["speaker"]} · {request.mode}')
            profile=p['speakers'][line['speaker']]
            wav,seconds=synthesize_line(line,profile,ws)
            durations.append(seconds)
            key=render_key(p,line,ws,request.mode,request.quality)
            clip=ws.clips/f'{line["id"]}-{key}.mp4'
            if not clip.exists() or clip.stat().st_size<1000:
                scene=ws.scenes/f'{line["id"]}-{key}.png'
                scene_image(p['title'],line,i+1,count,ws,p['speakers']).save(scene)
                temp=ws.clips/f'{line["id"]}-{key}.tmp.mp4'
                temp.unlink(missing_ok=True)
                pause=float(line.get('pause_after',0))
                try:
                    if request.mode=='static':render_static(scene,wav,seconds,temp,request.quality,pause)
                    elif request.mode=='motion':render_motion(scene,wav,line,seconds,temp,request.quality,pause)
                    else:render_sadtalker(scene,wav,line,seconds,temp,i+1,ws,request.quality,pause)
                    if not temp.is_file() or temp.stat().st_size<1000:raise RuntimeError('Clip missing')
                    temp.replace(clip)
                finally:temp.unlink(missing_ok=True)
            clips.append(clip)
        if cancelled(jid):raise InterruptedError()
        _job_update(jid,progress=97,message='Joining video and creating SRT subtitles...')
        dest=ws.exports/output_name(p,request.mode,request.quality)
        temp=dest.with_name(dest.stem+'.part.mp4')
        try:
            join_clips(clips,temp)
            temp.replace(dest)
        finally:temp.unlink(missing_ok=True)
        srt=write_srt(dest.with_suffix('.srt'),p['lines'],durations,
                      {k:s['name'] for k,s in p['speakers'].items()})
        return {'video_url':file_link(ws,'exports',dest.name),
                'subtitle_url':file_link(ws,'exports',srt.name),
                'filename':dest.name,'size_mb':round(dest.stat().st_size/1048576,1),
                'duration_seconds':round(sum(durations)+sum(float(x.get('pause_after',0)) for x in p['lines']),1)}
    return schedule(f'Render {request.mode} {request.quality}',work)


@app.get('/api/job/{jid}')
def job_status(jid:str):
    with _lock:
        if jid not in _jobs:raise HTTPException(404,detail='Job not found; cached clips can still be reused.')
        return _jobs[jid].copy()


@app.post('/api/job/{jid}/cancel')
def cancel_job(jid:str):
    with _lock:
        event=_cancel_events.get(jid)
        if not event:raise HTTPException(404,detail='No active job')
        event.set()
        _jobs[jid]['state']='cancelling'
    return {'ok':True,'message':'Will stop after current dialogue turn'}


@app.get('/api/health')
def health():
    import platform
    try: ffmpeg=Path(ffmpeg_path()).exists()
    except Exception:ffmpeg=False
    return {'ok':True,'system':platform.platform(),'ffmpeg':ffmpeg,
            'sadtalker_installed_not_validated':sadtalker_ready(),'version':'2.1-alpha','mode':'local-only'}
