"""Per-line Hindi/English speech generation with explicit uploaded-audio overrides."""
from __future__ import annotations
import asyncio
import subprocess
import wave
from pathlib import Path
from .settings import AUDIO, WAV, SPEAKERS
from .project import text_fingerprint
from .video import ffmpeg_path


def audio_paths(line: dict, profile: dict | None = None, ws=None) -> tuple[Path,Path]:
    profile=profile or SPEAKERS[line['speaker']]
    digest=text_fingerprint(line,profile)
    audio=ws.audio if ws else AUDIO
    wav_dir=ws.wav if ws else WAV
    return audio / f"{line['id']}-{digest}.mp3",wav_dir / f"{line['id']}-{digest}.wav"


def uploaded_marker(wav: Path)->Path: return wav.with_suffix('.uploaded')


def wav_length(path: Path) -> float:
    with wave.open(str(path),'rb') as handle:
        return handle.getnframes()/handle.getframerate()


def convert_wav(source: Path,dest: Path)->None:
    args=[ffmpeg_path(),'-hide_banner','-loglevel','error','-y','-i',str(source),
          '-ar','16000','-ac','1','-c:a','pcm_s16le',str(dest)]
    subprocess.run(args,check=True,capture_output=True,text=True,timeout=180)


def synthesize_line(line:dict,profile:dict|None=None,ws=None)->tuple[Path,float]:
    profile=profile or SPEAKERS[line['speaker']]
    mp3,wav=audio_paths(line,profile,ws)
    if wav.exists() and wav.stat().st_size>2000: return wav,wav_length(wav)
    if mp3.exists() and mp3.stat().st_size>2000:
        convert_wav(mp3,wav); return wav,wav_length(wav)
    try: import edge_tts
    except ImportError as exc: raise RuntimeError('edge-tts not installed; re-run START.bat') from exc
    async def generate():
        client=edge_tts.Communicate(text=line['text'],voice=profile['voice'],
                                    rate=profile['rate'],pitch=profile['pitch'])
        await client.save(str(mp3))
    for attempt in range(3):
        try:
            asyncio.run(generate())
            if not mp3.is_file() or mp3.stat().st_size<1000: raise RuntimeError('Voice service returned empty audio')
            convert_wav(mp3,wav)
            return wav,wav_length(wav)
        except Exception as exc:
            mp3.unlink(missing_ok=True)
            wav.unlink(missing_ok=True)
            if attempt==2: raise RuntimeError(f'Online voice generation failed: {exc}. Upload your own audio as fallback.') from exc
            import time
            time.sleep(2*(attempt+1))
    raise RuntimeError('TTS failed')


def set_uploaded_audio(line:dict,contents:bytes,extension:str,profile:dict|None=None,ws=None)->Path:
    if extension.lower() not in {'.wav','.mp3','.m4a'}:
        raise ValueError('Supported formats: wav, mp3, m4a.')
    if len(contents)>20*1024*1024: raise ValueError('Audio size limit 20 MB.')
    mp3,wav=audio_paths(line,profile,ws)
    origin=mp3.with_suffix('.upload'+extension.lower())
    origin.write_bytes(contents)
    tmp=wav.with_suffix('.tmp.wav')
    try:
        convert_wav(origin,tmp)
        if wav_length(tmp)<0.3: raise ValueError('Audio is too short.')
        tmp.replace(wav)
        uploaded_marker(wav).write_text(origin.name,encoding='utf-8')
    except Exception:
        tmp.unlink(missing_ok=True)
        origin.unlink(missing_ok=True)
        raise
    return wav


def reset_line_audio(line:dict,profile:dict|None=None,ws=None)->None:
    mp3,wav=audio_paths(line,profile,ws)
    mp3.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    uploaded_marker(wav).unlink(missing_ok=True)
    for file in mp3.parent.glob(mp3.stem+'.upload.*'): file.unlink(missing_ok=True)
