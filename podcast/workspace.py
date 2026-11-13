"""Isolated on-disk podcast workspaces; no path comes from unsanitized user input."""
from __future__ import annotations
import json
import re
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from .settings import DATA

PROJECTS = DATA / 'projects'
ACTIVE = DATA / 'active_project.txt'
SLUG = re.compile(r'^[a-z0-9-]{4,48}$')

@dataclass(frozen=True)
class Workspace:
    id: str
    root: Path

    @property
    def project(self) -> Path: return self.root / 'project.json'
    @property
    def images(self) -> Path: return self.root / 'portraits'
    @property
    def audio(self) -> Path: return self.root / 'audio'
    @property
    def wav(self) -> Path: return self.root / 'wav'
    @property
    def scenes(self) -> Path: return self.root / 'scenes'
    @property
    def clips(self) -> Path: return self.root / 'clips'
    @property
    def exports(self) -> Path: return self.root / 'exports'

    def ensure(self):
        for folder in (self.root,self.images,self.audio,self.wav,self.scenes,self.clips,self.exports):
            folder.mkdir(parents=True, exist_ok=True)
        return self


def get_workspace(identifier: str) -> Workspace:
    if not SLUG.fullmatch(identifier):
        raise ValueError('Invalid project ID')
    return Workspace(identifier, PROJECTS / identifier)


def new_workspace(title: str, topic: str = '', target_minutes: float = 10) -> Workspace:
    from .project import validate_project, save_project
    if not title or not title.strip():
        raise ValueError('Project title required')
    identifier = 'ep-' + secrets.token_hex(6)
    ws = get_workspace(identifier).ensure()
    intro = f'नमस्कार! आज हम {topic or title} के बारे में एक खुली और जानकारीपूर्ण बातचीत करेंगे।'
    project = {
        'title': title.strip(), 'topic': (topic or title).strip(), 'target_minutes': target_minutes,
        'lines': [
            {'id':'001','speaker':'aarav','text':intro,'shot':'wide','pause_after':0.2},
            {'id':'002','speaker':'kabir','text':'इस विषय पर लोगों के मन में सबसे आम सवाल क्या होते हैं?','shot':'focus','pause_after':0.2},
            {'id':'003','speaker':'meera','text':'पहले हमें भरोसेमंद स्रोत और संदर्भ देखना चाहिए। यहाँ सत्यापित जानकारी जोड़कर चर्चा आगे बढ़ाएँ।','shot':'focus','pause_after':0.2},
        ]
    }
    try:
        save_project(validate_project(project), ws)
    except Exception:
        shutil.rmtree(ws.root, ignore_errors=True)
        raise
    ACTIVE.write_text(ws.id, encoding='utf-8')
    return ws


def active_workspace() -> Workspace:
    PROJECTS.mkdir(parents=True, exist_ok=True)
    if ACTIVE.exists():
        identifier = ACTIVE.read_text(encoding='utf-8').strip()
        try:
            ws = get_workspace(identifier)
            if ws.project.is_file(): return ws.ensure()
        except ValueError:
            pass
    # Migrate previous single-project install safely. Copy, don't delete legacy data.
    from .settings import PROJECT, IMAGES, AUDIO, WAV, SCENES, CLIPS, EXPORTS
    if PROJECT.is_file():
        ws = get_workspace('ep-legacy-migrated').ensure()
        if not ws.project.exists():
            shutil.copy2(PROJECT, ws.project)
            for original, target in [(IMAGES,ws.images),(AUDIO,ws.audio),(WAV,ws.wav),(SCENES,ws.scenes),(CLIPS,ws.clips),(EXPORTS,ws.exports)]:
                if original.is_dir():
                    shutil.copytree(original, target, dirs_exist_ok=True)
        ACTIVE.write_text(ws.id, encoding='utf-8')
        return ws
    from .project import sample_project, save_project
    ws = get_workspace('ep-first-episode').ensure()
    if not ws.project.exists(): save_project(sample_project(), ws)
    ACTIVE.write_text(ws.id, encoding='utf-8')
    return ws


def choose_workspace(identifier: str) -> Workspace:
    ws = get_workspace(identifier)
    if not ws.project.is_file(): raise ValueError('Project not found')
    ACTIVE.write_text(identifier, encoding='utf-8')
    return ws.ensure()


def list_workspaces() -> list[dict]:
    PROJECTS.mkdir(parents=True, exist_ok=True)
    projects=[]
    for p in sorted(PROJECTS.iterdir()):
        if not p.is_dir() or not SLUG.fullmatch(p.name) or not (p/'project.json').is_file(): continue
        try:
            project=json.loads((p/'project.json').read_text(encoding='utf-8'))
            projects.append({'id':p.name,'title':project.get('title','Untitled'),
                             'topic':project.get('topic',''), 'updated':(p/'project.json').stat().st_mtime})
        except (ValueError, OSError): continue
    return sorted(projects,key=lambda x:x['updated'],reverse=True)
