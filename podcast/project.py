from __future__ import annotations
import json
import re
from pathlib import Path
from .settings import PROJECT, SPEAKERS

MAX_LINES = 100
MAX_TEXT_CHARS = 2000
_ID = re.compile(r'^[a-z0-9-]{1,40}$')


def sample_project() -> dict:
    sample = Path(__file__).resolve().parent.parent / 'samples' / 'project.json'
    return json.loads(sample.read_text(encoding='utf-8'))


def validate_project(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError('Project must be an object.')
    title = value.get('title', '')
    if not isinstance(title, str) or not title.strip() or len(title) > 120:
        raise ValueError('Title is required (max 120 characters).')
    lines = value.get('lines')
    if not isinstance(lines, list) or not 1 <= len(lines) <= MAX_LINES:
        raise ValueError(f'Provide 1 to {MAX_LINES} dialogue turns.')
    output = []
    seen = set()
    for i, line in enumerate(lines):
        if not isinstance(line, dict):
            raise ValueError(f'Invalid dialogue {i + 1}.')
        identifier, who, content = line.get('id'), line.get('speaker'), line.get('text')
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier) or identifier in seen:
            raise ValueError(f'Invalid or repeated dialogue ID at turn {i + 1}.')
        if who not in SPEAKERS:
            raise ValueError(f'Invalid speaker at turn {i + 1}.')
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_TEXT_CHARS:
            raise ValueError(f'Dialogue {i + 1} must contain 1–{MAX_TEXT_CHARS} characters.')
        output.append({'id': identifier, 'speaker': who, 'text': content.strip()})
        seen.add(identifier)
    return {'title': title.strip(), 'lines': output}


def load_project() -> dict:
    if not PROJECT.exists():
        save_project(sample_project())
    try:
        return validate_project(json.loads(PROJECT.read_text(encoding='utf-8')))
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Project data invalid: {exc}') from exc


def save_project(project: dict) -> dict:
    clean = validate_project(project)
    tmp = PROJECT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(PROJECT)
    return clean


def text_fingerprint(line: dict, speaker: dict) -> str:
    import hashlib
    source = json.dumps([line['text'], speaker['voice'], speaker['rate'], speaker['pitch']], ensure_ascii=False)
    return hashlib.sha256(source.encode('utf-8')).hexdigest()[:16]
