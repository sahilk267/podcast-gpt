from __future__ import annotations
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
IMAGES = DATA / 'portraits'
AUDIO = DATA / 'audio'
WAV = DATA / 'wav'
SCENES = DATA / 'scenes'
CLIPS = DATA / 'clips'
EXPORTS = DATA / 'exports'
PROJECT = DATA / 'project.json'
ROOTS = (IMAGES, AUDIO, WAV, SCENES, CLIPS, EXPORTS)

SPEAKERS = {
    'aarav': {'name': 'Aarav', 'role': 'Host', 'voice': 'hi-IN-MadhurNeural', 'rate': '+0%', 'pitch': '+0Hz'},
    'meera': {'name': 'Meera', 'role': 'Expert', 'voice': 'hi-IN-SwaraNeural', 'rate': '-4%', 'pitch': '+0Hz'},
    'kabir': {'name': 'Kabir', 'role': 'Guest', 'voice': 'hi-IN-MadhurNeural', 'rate': '+9%', 'pitch': '-5Hz'},
}

for folder in ROOTS:
    folder.mkdir(parents=True, exist_ok=True)
