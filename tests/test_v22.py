"""No network or model downloads. Production speech metadata is mocked."""
import json
import math
import struct
import sys
import types
import wave
from pathlib import Path

import pytest
from podcast import voice as voice_module
from podcast import workspace as workspaces
from podcast.project import load_project
from podcast.subtitles import srt_text


def _workspaces(monkeypatch, tmp_path):
    monkeypatch.setattr(workspaces, 'PROJECTS', tmp_path / 'projects')
    monkeypatch.setattr(workspaces, 'ACTIVE', tmp_path / 'active.txt')


def _wav(path: Path, duration: float = 1.5):
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b''.join(struct.pack('<h', int(1000 * math.sin(2 * math.pi * 150 * i / 16000)))
                               for i in range(int(16000 * duration))))


def test_parse_word_boundaries_and_srt_uses_actual_offsets():
    metadata='\n'.join([
        json.dumps({'type':'WordBoundary','offset':2000000,'duration':4000000,'text':'नमस्ते'}),
        json.dumps({'type':'WordBoundary','offset':7000000,'duration':4000000,'text':'दोस्तों'}),
        json.dumps({'type':'audio','data':'ignored'}),
        '{broken json}',
    ])
    words=voice_module.parse_edge_metadata(metadata,2.0)
    assert words==[{'start':0.2,'end':0.6,'text':'नमस्ते'},
                   {'start':0.7,'end':1.1,'text':'दोस्तों'}]
    lines=[{'speaker':'aarav','text':'नमस्ते दोस्तों','pause_after':0.2},
           {'speaker':'meera','text':'अगला प्रश्न','pause_after':0}]
    srt=srt_text(lines,[2.0,1.0],{'aarav':'Aarav','meera':'Meera'},[words,[]])
    assert '00:00:00,200 --> 00:00:01,100' in srt
    assert '00:00:02,200 --> 00:00:03,200' in srt
    assert 'Aarav: नमस्ते दोस्तों' in srt
    assert 'Meera: अगला प्रश्न' in srt


def test_word_boundary_chunk_splits_when_too_many_words():
    words=[{'start':i*.2,'end':i*.2+.15,'text':'word'} for i in range(22)]
    srt=srt_text([{'speaker':'aarav','text':'ignored','pause_after':0}],[5],alignments=[words])
    assert srt.count('-->')==3
    assert '00:00:04,350' in srt


def test_audio_reset_removes_word_alignment(monkeypatch,tmp_path):
    _workspaces(monkeypatch,tmp_path)
    ws=workspaces.new_workspace('A','Topic')
    p=load_project(ws); line=p['lines'][0]
    _,wav=voice_module.audio_paths(line,p['speakers'][line['speaker']],ws)
    _wav(wav)
    voice_module.alignment_path(wav).write_text(json.dumps({'engine':'edge-tts','version':1,'words':[
        {'start':0.5,'end':0.8,'text':'Hi'}]}),encoding='utf-8')
    assert voice_module.load_alignment(wav)
    voice_module.uploaded_marker(wav).write_text('voice.wav',encoding='utf-8')
    assert voice_module.load_alignment(wav)==[]
    voice_module.reset_line_audio(line,p['speakers'][line['speaker']],ws)
    assert not voice_module.alignment_path(wav).exists()


def test_live_voice_catalog_keeps_only_real_returned_indian_voices(monkeypatch):
    _back=voice_module._catalog
    voice_module._catalog=None
    async def list_voices():
        return [
            {'ShortName':'hi-IN-MadhurNeural','Locale':'hi-IN','Gender':'Male'},
            {'ShortName':'hi-IN-SwaraNeural','Locale':'hi-IN','Gender':'Female'},
            {'ShortName':'hi-IN-ArjunNeural','Locale':'hi-IN','Gender':'Male'},
            {'ShortName':'en-IN-PrabhatNeural','Locale':'en-IN','Gender':'Male'},
            {'ShortName':'en-US-GuyNeural','Locale':'en-US','Gender':'Male'},
        ]
    monkeypatch.setitem(sys.modules,'edge_tts',types.SimpleNamespace(list_voices=list_voices))
    try:
        catalog=voice_module.voice_catalog(refresh=True)
        assert catalog['verified'] is True
        assert len(catalog['voices'])==4
        assert set(x['id'] for x in catalog['voices'] if x['locale']=='hi-IN')=={
            'hi-IN-MadhurNeural','hi-IN-SwaraNeural','hi-IN-ArjunNeural'}
    finally:
        voice_module._catalog=_back


def test_fake_edge_tts_save_produces_word_alignment(monkeypatch,tmp_path):
    _workspaces(monkeypatch,tmp_path)
    ws=workspaces.new_workspace('TTS mock','Test')
    p=load_project(ws)
    line=p['lines'][0]; profile=p['speakers'][line['speaker']]

    class FakeCommunicate:
        def __init__(self, **kwargs):
            assert kwargs['boundary']=='WordBoundary'
        async def save(self, mp3, metadata):
            Path(mp3).write_bytes(b'A' * 1200)
            Path(metadata).write_text(json.dumps({'type':'WordBoundary','offset':1000000,
                                                   'duration':4000000,'text':'नमस्ते'}))

    def fake_convert(source, dest):
        _wav(dest,1.0)

    monkeypatch.setitem(sys.modules,'edge_tts',types.SimpleNamespace(Communicate=FakeCommunicate))
    monkeypatch.setattr(voice_module,'convert_wav',fake_convert)
    wav, seconds=voice_module.synthesize_line(line,profile,ws)
    assert 0.9<seconds<1.1
    assert voice_module.load_alignment(wav)==[{'start':0.1,'end':0.5,'text':'नमस्ते'}]
    assert voice_module.synthesize_line(line,profile,ws)[0]==wav


def test_offline_preflight_without_audio_refuses_render(monkeypatch,tmp_path):
    pytest.importorskip('httpx')
    from fastapi.testclient import TestClient
    _workspaces(monkeypatch,tmp_path)
    ws=workspaces.new_workspace('Offline','Testing')
    from podcast.app import app
    client=TestClient(app)
    pre=client.get('/api/preflight')
    assert pre.status_code==200
    report=pre.json()
    assert report['project_id']==ws.id
    assert report['missing_audio']
    assert report['duplicate_voice_ids']
    r=client.post('/api/render',json={'mode':'static','quality':'720p','offline_only':True})
    assert r.status_code==409
    for line in load_project(ws)['lines']:
        _,wav=voice_module.audio_paths(line,load_project(ws)['speakers'][line['speaker']],ws)
        _wav(wav,0.6)
    report=client.get('/api/preflight').json()
    assert report['missing_audio']==[]
    assert report['audio_ready']==3


def test_complete_offline_export_uses_real_tts_word_times(monkeypatch,tmp_path):
    import time
    pytest.importorskip('httpx')
    from fastapi.testclient import TestClient
    from podcast.project import save_project
    _workspaces(monkeypatch,tmp_path)
    ws=workspaces.new_workspace('Aligned video','Education')
    project=load_project(ws)
    project['lines']=project['lines'][:2]
    project['lines'][0]['pause_after']=0.25
    project['lines'][1]['pause_after']=0
    save_project(project,ws)
    for line in project['lines']:
        _,wav=voice_module.audio_paths(line,project['speakers'][line['speaker']],ws)
        _wav(wav,0.6)
    _,first=voice_module.audio_paths(project['lines'][0],project['speakers']['aarav'],ws)
    voice_module.alignment_path(first).write_text(json.dumps({
        'engine':'edge-tts','version':1,
        'words':[{'start':0.1,'end':0.4,'text':'नमस्ते'}]
    }),encoding='utf-8')
    from podcast.app import app
    mount=next(route for route in app.routes if getattr(route,'path',None)=='/files')
    monkeypatch.setattr(mount.app,'directory',str(tmp_path))
    monkeypatch.setattr(mount.app,'all_directories',[str(tmp_path)])
    client=TestClient(app)
    r=client.post('/api/render',json={'mode':'static','quality':'720p','offline_only':True})
    assert r.status_code==200,r.text
    jid=r.json()['id']
    for _ in range(100):
        status=client.get('/api/job/'+jid).json()
        if status['state'] in ('done','error','cancelled'):
            break
        time.sleep(0.1)
    assert status['state']=='done',status
    assert status['result']['word_timed_lines']==1
    subtitles=client.get(status['result']['subtitle_url']).text
    assert '00:00:00,100 --> 00:00:00,400' in subtitles
    assert 'नमस्ते' in subtitles
    assert '00:00:00,850' in subtitles
    assert client.get(status['result']['video_url']).status_code==200
