from __future__ import annotations
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, File, UploadFile, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image, ImageOps, UnidentifiedImageError
from .settings import BASE, DATA, IMAGES, AUDIO, WAV, EXPORTS, SPEAKERS
from .project import load_project, save_project
from .voice import audio_paths, synthesize_line, wav_length, set_uploaded_audio
from .video import ffmpeg_path, sadtalker_ready, scene_image, render_static, render_motion, render_sadtalker, join_clips, output_name

app = FastAPI(title='Podcast GPT', docs_url=None, redoc_url=None)
app.mount('/files', StaticFiles(directory=str(DATA)), name='files')
app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')
_executor = ThreadPoolExecutor(max_workers=1)
_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_active: str | None = None


class RenderRequest(BaseModel):
    mode: Literal['static', 'motion', 'ai'] = 'motion'


def current_job():
    with _lock:
        if _active and _jobs.get(_active, {}).get('state') in {'queued', 'running'}:
            return _jobs[_active].copy()
        return None


def _job_update(job_id: str, **fields):
    with _lock:
        _jobs[job_id].update(fields)


def _runner(job_id: str, fn):
    global _active
    try:
        _job_update(job_id, state='running')
        result = fn(job_id)
        _job_update(job_id, state='done', progress=100, message='Completed', result=result)
    except Exception as exc:
        traceback.print_exc()
        _job_update(job_id, state='error', message=str(exc)[:1000], error=traceback.format_exc()[-3000:])
    finally:
        with _lock:
            if _active == job_id:
                _active = None


def schedule(label: str, fn) -> dict:
    global _active
    with _lock:
        if _active and _jobs[_active]['state'] in {'queued', 'running'}:
            raise HTTPException(status_code=409, detail='Another job is already running.')
        job_id = uuid.uuid4().hex[:12]
        job = {'id': job_id, 'state': 'queued', 'label': label, 'progress': 0, 'message': 'Queued'}
        _jobs[job_id] = job
        _active = job_id
    _executor.submit(_runner, job_id, fn)
    return job


@app.get('/')
def index():
    return FileResponse(str(BASE / 'static' / 'index.html'))


@app.get('/api/project')
def get_project():
    p = load_project()
    p['speakers'] = {key: {
        **speaker,
        'has_portrait': (IMAGES / f'{key}.png').exists(),
        'portrait_url': f'/files/portraits/{key}.png',
    } for key, speaker in SPEAKERS.items()}
    total = 0.0
    for line in p['lines']:
        _, wav = audio_paths(line)
        try:
            duration = round(wav_length(wav), 2) if wav.exists() else None
        except Exception:
            duration = None
        line['audio_url'] = f'/files/wav/{wav.name}' if duration else None
        line['duration'] = duration
        total += duration or 0
    p['duration_seconds'] = round(total, 2)
    p['ready_audio'] = sum(1 for line in p['lines'] if line['audio_url'])
    p['ai_ready'] = sadtalker_ready()
    p['current_job'] = current_job()
    return p


@app.put('/api/project')
def put_project(value: dict = Body(...)):
    if current_job():
        raise HTTPException(409, detail='Finish the active job before editing.')
    try:
        return save_project(value)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@app.post('/api/portrait/{speaker_id}')
async def upload_portrait(speaker_id: str, file: UploadFile = File(...)):
    if speaker_id not in SPEAKERS:
        raise HTTPException(404, detail='Unknown speaker')
    if current_job():
        raise HTTPException(409, detail='A job is running')
    raw = await file.read(12 * 1024 * 1024 + 1)
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, detail='Image is too large (max 12MB).')
    from io import BytesIO
    try:
        with Image.open(BytesIO(raw)) as source:
            source.verify()
        with Image.open(BytesIO(raw)) as source:
            converted = ImageOps.exif_transpose(source).convert('RGB')
            if converted.width < 200 or converted.height < 200:
                raise ValueError('Use a portrait at least 200×200 pixels.')
            if converted.width * converted.height > 25_000_000:
                raise ValueError('Image exceeds 25 megapixels.')
            converted.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            converted.save(IMAGES / f'{speaker_id}.png', optimize=True)
    except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(400, detail=f'Invalid image: {exc}') from exc
    return {'ok': True, 'url': f'/files/portraits/{speaker_id}.png'}


@app.post('/api/audio/{line_id}')
async def upload_audio(line_id: str, file: UploadFile = File(...)):
    if current_job():
        raise HTTPException(409, detail='A job is running')
    line = next((x for x in load_project()['lines'] if x['id'] == line_id), None)
    if line is None:
        raise HTTPException(404, detail='Unknown dialogue ID')
    raw = await file.read(20 * 1024 * 1024 + 1)
    try:
        wav = set_uploaded_audio(line, raw, Path(file.filename or '').suffix)
    except (ValueError, RuntimeError, OSError) as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return {'ok': True, 'url': f'/files/wav/{wav.name}', 'duration': wav_length(wav)}


@app.post('/api/voices')
def generate_voices():
    project = load_project()
    def work(job_id):
        count = len(project['lines'])
        total_duration = 0
        for i, line in enumerate(project['lines']):
            _job_update(job_id, progress=round(i / count * 100),
                        message=f"Voice {i+1}/{count} · {SPEAKERS[line['speaker']]['name']}")
            _, seconds = synthesize_line(line)
            total_duration += seconds
        return {'total_duration': round(total_duration, 2)}
    return schedule('Generate voices', work)


@app.post('/api/render')
def start_render(request: RenderRequest):
    project = load_project()
    if request.mode == 'ai':
        if not sadtalker_ready():
            raise HTTPException(400, detail='SadTalker unavailable. Run INSTALL_AI.bat first.')
        missing = [x for x in SPEAKERS if not (IMAGES / f'{x}.png').exists()]
        if missing:
            raise HTTPException(400, detail=f'Missing portraits: {", ".join(missing)}')
    def work(job_id):
        from .settings import SCENES, CLIPS
        clips = []
        count = len(project['lines'])
        for i, line in enumerate(project['lines']):
            _job_update(job_id, progress=round(100 * i / (count + 1)),
                        message=f"Rendering {i+1}/{count} · {line['speaker']} · {request.mode}")
            wav, seconds = synthesize_line(line)
            scene = SCENES / f'{i+1:03d}.png'
            scene_image(project['title'], line, i + 1, count).save(scene)
            clip = CLIPS / f'{i+1:03d}_{request.mode}.mp4'
            if request.mode == 'static':
                render_static(scene, wav, seconds, clip)
            elif request.mode == 'motion':
                render_motion(scene, wav, line, seconds, clip)
            else:
                render_sadtalker(scene, wav, line, seconds, clip, i + 1)
            if not clip.exists() or clip.stat().st_size < 1000:
                raise RuntimeError(f'Output missing for dialogue {i + 1}')
            clips.append(clip)
        _job_update(job_id, progress=98, message='Joining video clips...')
        dest = EXPORTS / output_name(project, request.mode)
        join_clips(clips, dest)
        return {'video_url': f'/files/exports/{dest.name}', 'filename': dest.name,
                'size_mb': round(dest.stat().st_size / 1048576, 1)}
    return schedule(f'Render {request.mode}', work)


@app.get('/api/job/{job_id}')
def job_status(job_id: str):
    with _lock:
        if job_id not in _jobs:
            raise HTTPException(404, detail='Job not found')
        return _jobs[job_id].copy()


@app.get('/api/health')
def health():
    import platform
    try:
        ffmpeg = ffmpeg_path()
        ffmpeg_ok = Path(ffmpeg).exists()
    except Exception:
        ffmpeg_ok = False
    return {'ok': True, 'system': platform.platform(), 'ffmpeg': ffmpeg_ok,
            'sadtalker': sadtalker_ready(), 'mode': 'local-only'}
