from __future__ import annotations
import asyncio
import subprocess
import wave
from pathlib import Path
from .settings import AUDIO, WAV, SPEAKERS
from .project import text_fingerprint
from .video import ffmpeg_path


def audio_paths(line: dict) -> tuple[Path, Path]:
    digest = text_fingerprint(line, SPEAKERS[line['speaker']])
    return AUDIO / f"{line['id']}-{digest}.mp3", WAV / f"{line['id']}-{digest}.wav"


def wav_length(path: Path) -> float:
    with wave.open(str(path), 'rb') as handle:
        return handle.getnframes() / handle.getframerate()


def convert_wav(source: Path, dest: Path) -> None:
    command = [ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
               '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(dest)]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)


def synthesize_line(line: dict) -> tuple[Path, float]:
    mp3, wav = audio_paths(line)
    if wav.exists() and wav.stat().st_size > 2000:
        return wav, wav_length(wav)
    if mp3.exists() and mp3.stat().st_size > 2000:
        convert_wav(mp3, wav)
        return wav, wav_length(wav)
    import edge_tts
    speaker = SPEAKERS[line['speaker']]
    async def generate():
        client = edge_tts.Communicate(text=line['text'], voice=speaker['voice'],
                                      rate=speaker['rate'], pitch=speaker['pitch'])
        await client.save(str(mp3))
    for attempt in range(3):
        try:
            asyncio.run(generate())
            if mp3.stat().st_size < 1000:
                raise RuntimeError('Voice service returned empty audio')
            convert_wav(mp3, wav)
            return wav, wav_length(wav)
        except Exception:
            mp3.unlink(missing_ok=True)
            wav.unlink(missing_ok=True)
            if attempt == 2:
                raise
            import time
            time.sleep(2 * (attempt + 1))
    raise RuntimeError('TTS failed')


def set_uploaded_audio(line: dict, contents: bytes, extension: str) -> Path:
    if extension.lower() not in {'.wav', '.mp3', '.m4a'}:
        raise ValueError('Supported formats: wav, mp3, m4a.')
    if len(contents) > 20 * 1024 * 1024:
        raise ValueError('Audio size limit 20 MB.')
    mp3, wav = audio_paths(line)
    origin = AUDIO / f'{mp3.stem}.upload{extension.lower()}'
    origin.write_bytes(contents)
    try:
        convert_wav(origin, wav)
        if wav_length(wav) < 0.3:
            raise ValueError('Audio is too short.')
    except Exception:
        wav.unlink(missing_ok=True)
        raise
    return wav
