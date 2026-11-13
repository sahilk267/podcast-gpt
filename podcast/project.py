from __future__ import annotations
import json
import re
import hashlib
from pathlib import Path
from .settings import PROJECT, SPEAKERS

MAX_LINES=200
MAX_TEXT_CHARS=2200
_ID=re.compile(r'^[a-z0-9-]{1,40}$')
_VOICE=re.compile(r'^[a-z]{2,3}-[A-Z]{2}-[A-Za-z0-9]+(?:Neural|MultilingualNeural)$')
_RATE=re.compile(r'^[+-]\d{1,2}%$')
_PITCH=re.compile(r'^[+-]\d{1,2}Hz$')


def sample_project() -> dict:
    sample = Path(__file__).resolve().parent.parent / 'samples' / 'project.json'
    return validate_project(json.loads(sample.read_text(encoding='utf-8')))


def validate_project(value: object) -> dict:
    if not isinstance(value,dict): raise ValueError('Project must be an object.')
    title=value.get('title','')
    if not isinstance(title,str) or not title.strip() or len(title)>120:
        raise ValueError('Title required (max 120 characters).')
    topic=value.get('topic',title)
    if not isinstance(topic,str) or len(topic)>240: raise ValueError('Topic too long.')
    target=value.get('target_minutes',10)
    if not isinstance(target,(float,int)) or isinstance(target,bool) or not 1<=target<=120:
        raise ValueError('Target length must be 1–120 minutes.')
    source_speakers=value.get('speakers') or SPEAKERS
    if not isinstance(source_speakers,dict): raise ValueError('Speakers must be an object.')
    profiles={}
    for key,default in SPEAKERS.items():
        sp=source_speakers.get(key,default)
        if not isinstance(sp,dict): raise ValueError(f'Invalid speaker {key}.')
        name=sp.get('name',default['name'])
        role=sp.get('role',default['role'])
        voice=sp.get('voice',default['voice'])
        rate=sp.get('rate',default['rate'])
        pitch=sp.get('pitch',default['pitch'])
        if not isinstance(name,str) or not 1<=len(name.strip())<=45: raise ValueError('Invalid speaker name.')
        if not isinstance(role,str) or len(role)>60: raise ValueError('Invalid speaker role.')
        if not isinstance(voice,str) or not _VOICE.fullmatch(voice): raise ValueError(f'Invalid TTS voice: {voice}')
        if not isinstance(rate,str) or not _RATE.fullmatch(rate): raise ValueError('Invalid voice rate (e.g. +0%).')
        if not isinstance(pitch,str) or not _PITCH.fullmatch(pitch): raise ValueError('Invalid pitch (e.g. +0Hz).')
        profiles[key]={'name':name.strip(),'role':role.strip(),'voice':voice,'rate':rate,'pitch':pitch}
    lines=value.get('lines')
    if not isinstance(lines,list) or not 1<=len(lines)<=MAX_LINES:
        raise ValueError(f'Provide 1–{MAX_LINES} dialogue turns.')
    clean=[];seen=set()
    for i,line in enumerate(lines):
        if not isinstance(line,dict): raise ValueError(f'Invalid dialogue {i+1}.')
        identifier,who,content=line.get('id'),line.get('speaker'),line.get('text')
        if not isinstance(identifier,str) or not _ID.fullmatch(identifier) or identifier in seen:
            raise ValueError(f'Invalid or repeated dialogue ID at turn {i+1}.')
        if who not in SPEAKERS: raise ValueError(f'Unknown speaker at turn {i+1}.')
        if not isinstance(content,str) or not content.strip() or len(content)>MAX_TEXT_CHARS:
            raise ValueError(f'Dialogue {i+1} must contain 1–{MAX_TEXT_CHARS} chars.')
        shot=line.get('shot','wide')
        if shot not in ('wide','focus'): raise ValueError(f'Invalid shot at turn {i+1}.')
        pause=line.get('pause_after',0.0)
        if not isinstance(pause,(float,int)) or isinstance(pause,bool) or not 0<=pause<=5:
            raise ValueError('Pause must be from 0 to 5 seconds.')
        clean.append({'id':identifier,'speaker':who,'text':content.strip(),
                      'shot':shot,'pause_after':round(float(pause),2)})
        seen.add(identifier)
    return {'schema_version':2,'title':title.strip(),'topic':topic.strip(),
            'target_minutes':float(target),'speakers':profiles,'lines':clean}


def load_project(ws=None) -> dict:
    path=ws.project if ws else PROJECT
    if not path.exists(): save_project(sample_project(),ws)
    try: return validate_project(json.loads(path.read_text(encoding='utf-8')))
    except (ValueError,json.JSONDecodeError) as exc:
        raise RuntimeError(f'Project data invalid: {exc}') from exc


def save_project(project: dict, ws=None) -> dict:
    clean=validate_project(project)
    path=ws.project if ws else PROJECT
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(clean,indent=2,ensure_ascii=False),encoding='utf-8')
    tmp.replace(path)
    return clean


def text_fingerprint(line: dict, speaker: dict) -> str:
    source=json.dumps([line['text'],speaker['voice'],speaker['rate'],speaker['pitch']],ensure_ascii=False)
    return hashlib.sha256(source.encode('utf-8')).hexdigest()[:16]
