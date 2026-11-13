import json
import math
import struct
import subprocess
import wave
from pathlib import Path
import pytest

from podcast.project import sample_project,save_project,load_project,validate_project
from podcast.subtitles import srt_text
from podcast.video import ffmpeg_path,scene_image,render_static
from podcast.voice import audio_paths,wav_length,uploaded_marker,reset_line_audio
from podcast import workspace as workspace_module


def _isolated_workspaces(monkeypatch,tmp_path):
    monkeypatch.setattr(workspace_module,'PROJECTS',tmp_path/'projects')
    monkeypatch.setattr(workspace_module,'ACTIVE',tmp_path/'active.txt')


def _wav(path,duration=0.4):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(b''.join(struct.pack('<h',int(1000*math.sin(2*math.pi*150*i/16000)))
                               for i in range(int(16000*duration))))


def test_isolated_projects_and_voice_settings(monkeypatch,tmp_path):
    _isolated_workspaces(monkeypatch,tmp_path)
    first=workspace_module.new_workspace('Episode one','Travel',10)
    second=workspace_module.new_workspace('Episode two','Science',15)
    assert first.root!=second.root
    assert load_project(first)['title']=='Episode one'
    assert load_project(second)['topic']=='Science'
    assert workspace_module.active_workspace().id==second.id
    workspace_module.choose_workspace(first.id)
    assert workspace_module.active_workspace().id==first.id
    p=load_project(first)
    p['speakers']['kabir']['voice']='en-IN-PrabhatNeural'
    save_project(p,first)
    assert load_project(first)['speakers']['kabir']['voice']=='en-IN-PrabhatNeural'
    assert load_project(second)['speakers']['kabir']['voice']!='en-IN-PrabhatNeural'
    assert len(workspace_module.list_workspaces())==2
    with pytest.raises(ValueError):workspace_module.get_workspace('../bad-id')


def test_project_rejects_malformed_settings():
    p=sample_project();p['lines'][0]['shot']='illegal'
    with pytest.raises(ValueError):validate_project(p)
    p=sample_project();p['speakers']['aarav']['voice']='../../evil'
    with pytest.raises(ValueError):validate_project(p)
    p=sample_project();p['lines'][0]['pause_after']=1000
    with pytest.raises(ValueError):validate_project(p)


def test_srt_pause_and_hindi():
    lines=[{'speaker':'aarav','text':'नमस्ते सभी को','pause_after':0.25},
           {'speaker':'meera','text':'स्वागत है','pause_after':0}]
    subs=srt_text(lines,[1.50,2.00],{'aarav':'Aarav','meera':'Meera'})
    assert '00:00:00,000 --> 00:00:01,500' in subs
    assert '00:00:01,750 --> 00:00:03,750' in subs
    assert 'नमस्ते सभी को' in subs


def test_custom_audio_reset_and_cache_fingerprint(monkeypatch,tmp_path):
    _isolated_workspaces(monkeypatch,tmp_path)
    ws=workspace_module.new_workspace('Test','Sound')
    p=load_project(ws);l=p['lines'][0];sp=p['speakers'][l['speaker']]
    mp3,wav=audio_paths(l,sp,ws)
    _wav(wav)
    uploaded_marker(wav).write_text('custom.wav')
    assert wav_length(wav)>0
    reset_line_audio(l,sp,ws)
    assert not wav.exists() and not uploaded_marker(wav).exists()
    sp2={**sp,'pitch':'+2Hz'}
    assert audio_paths(l,sp2,ws)!=audio_paths(l,sp,ws)


def test_focus_layout_and_1080p_render(monkeypatch,tmp_path):
    _isolated_workspaces(monkeypatch,tmp_path)
    ws=workspace_module.new_workspace('Test','Video')
    p=load_project(ws);line={**p['lines'][0],'shot':'focus'}
    scene=tmp_path/'focus.png';scene_image(p['title'],line,1,3,ws,p['speakers']).save(scene)
    assert scene.stat().st_size>1000
    wav=tmp_path/'test.wav';_wav(wav,0.35)
    out=tmp_path/'out.mp4';render_static(scene,wav,0.35,out,'1080p',0.15)
    assert out.stat().st_size>1000
    result=subprocess.run([ffmpeg_path(),'-hide_banner','-i',str(out)],capture_output=True,text=True)
    assert '1920x1080' in result.stderr


def test_api_create_switch_and_voice_reset(monkeypatch,tmp_path):
    httpx=pytest.importorskip('httpx')
    from fastapi.testclient import TestClient
    _isolated_workspaces(monkeypatch,tmp_path)
    from podcast.app import app
    client=TestClient(app)
    assert client.get('/api/health').json()['version'].startswith('2.')
    created=client.post('/api/projects',json={'title':'API Test','topic':'Biology','target_minutes':10})
    assert created.status_code==200
    ident=created.json()['id']
    p=client.get('/api/project').json();assert p['id']==ident
    p['title']='Updated episode'
    saved=client.put('/api/project',json=p)
    assert saved.status_code==200,saved.text
    assert client.get('/api/project').json()['title']=='Updated episode'
    assert client.post('/api/audio/001/reset').json()['ok']
    assert client.post('/api/projects/activate/not-a-project').status_code==404


def test_three_speaker_end_to_end_export_no_network(monkeypatch,tmp_path):
    import time
    pytest.importorskip('httpx')
    from fastapi.testclient import TestClient
    _isolated_workspaces(monkeypatch,tmp_path)
    ws=workspace_module.new_workspace('Three Speaker Smoke Test','Education',10)
    p=load_project(ws)
    for i,line in enumerate(p['lines']):
        line['pause_after']=0.1
        line['shot']='focus' if i>0 else 'wide'
    save_project(p,ws)
    for line in p['lines']:
        _,wav=audio_paths(line,p['speakers'][line['speaker']],ws)
        _wav(wav,0.40)
    from podcast.app import app
    # Test workspace root is a temp directory, while production lives in DATA/projects.
    # Point only the static-file mount to the isolated root.
    file_mount=next(route for route in app.routes if getattr(route,'path',None)=='/files')
    monkeypatch.setattr(file_mount.app,'directory',str(tmp_path))
    monkeypatch.setattr(file_mount.app,'all_directories',[str(tmp_path)])
    client=TestClient(app)
    response=client.post('/api/render',json={'mode':'static','quality':'720p'})
    assert response.status_code==200,response.text
    jid=response.json()['id']
    for _ in range(200):
        info=client.get('/api/job/'+jid).json()
        if info['state'] in {'done','error','cancelled'}:break
        time.sleep(0.1)
    assert info['state']=='done',info
    url=info['result']['video_url']
    subs=info['result']['subtitle_url']
    assert url.endswith('.mp4') and subs.endswith('.srt')
    assert client.get(url).status_code==200
    assert '00:00:00,000' in client.get(subs).text
    assert info['result']['duration_seconds']>1.0
    # Rendering the same project again should reuse cached clips.
    cached=list(ws.clips.glob('*.mp4'))
    assert len(cached)==3
    old={p.name:p.stat().st_mtime_ns for p in cached}
    response=client.post('/api/render',json={'mode':'static','quality':'720p'})
    assert response.status_code==200
    jid=response.json()['id']
    for _ in range(100):
        info=client.get('/api/job/'+jid).json()
        if info['state'] in {'done','error','cancelled'}:break
        time.sleep(0.1)
    assert info['state']=='done',info
    assert {p.name:p.stat().st_mtime_ns for p in cached}==old


def test_long_dialogue_caption_is_chunked():
    text=' '.join(['इस विषय पर हमारे दर्शक क्या सोचते हैं']*15)
    subs=srt_text([{'speaker':'aarav','text':text,'pause_after':0}],[9],{'aarav':'Aarav'})
    cues=subs.strip().split('\n\n')
    assert len(cues)>5
    assert all(len(cue.splitlines()[-1])<=90 for cue in cues)
    assert '00:00:09,000' in cues[-1]
