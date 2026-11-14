"""Speech generation, actual Edge word timing and custom WAV uploads.

Edge TTS is an *unofficial* network-dependent endpoint. We do not promise any
particular voice or unlimited free access. Manually uploaded audio never has
fabricated word timestamps.
"""
from __future__ import annotations
import asyncio
import json
import subprocess
import time
import wave
from pathlib import Path
from .settings import AUDIO, WAV, SPEAKERS
from .project import text_fingerprint
from .video import ffmpeg_path

TICKS_PER_SECOND = 10_000_000
_CATALOG_TTL = 1800
_catalog: tuple[float, list[dict]] | None = None


def audio_paths(line: dict, profile: dict | None = None, ws=None) -> tuple[Path, Path]:
    profile = profile or SPEAKERS[line['speaker']]
    digest = text_fingerprint(line, profile)
    audio = ws.audio if ws else AUDIO
    wav_dir = ws.wav if ws else WAV
    return audio / f"{line['id']}-{digest}.mp3", wav_dir / f"{line['id']}-{digest}.wav"


def uploaded_marker(wav: Path) -> Path:
    return wav.with_suffix('.uploaded')


def alignment_path(wav: Path) -> Path:
    return wav.with_suffix('.words.json')


def wav_length(path: Path) -> float:
    with wave.open(str(path), 'rb') as handle:
        return handle.getnframes() / handle.getframerate()


def convert_wav(source: Path, dest: Path) -> None:
    args = [ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
            '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(dest)]
    subprocess.run(args, check=True, capture_output=True, text=True, timeout=180)


def parse_edge_metadata(lines: str, audio_seconds: float) -> list[dict]:
    """Convert Edge TTS word boundaries in 100-ns ticks to seconds.

    Drop invalid events rather than giving users misleading precise timings.
    """
    result = []
    for row in lines.splitlines():
        if not row.strip():
            continue
        try:
            item = json.loads(row)
            if item.get('type') != 'WordBoundary':
                continue
            text = item.get('text')
            offset, duration = item['offset'], item['duration']
            if not isinstance(text, str) or not text.strip():
                continue
            if isinstance(offset, bool) or isinstance(duration, bool):
                continue
            start = float(offset) / TICKS_PER_SECOND
            end = start + float(duration) / TICKS_PER_SECOND
            if not (0 <= start < audio_seconds and end > start):
                continue
            end = min(audio_seconds, end)
            if end - start < 0.01:
                continue
            result.append({'start': round(start, 3), 'end': round(end, 3), 'text': text.strip()})
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
    result.sort(key=lambda word: word['start'])
    return result[:10000]


def load_alignment(wav: Path) -> list[dict]:
    """Return real speech word boundaries, or [] for user audio/invalid metadata."""
    if uploaded_marker(wav).exists() or not wav.exists():
        return []
    path = alignment_path(wav)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        if payload.get('engine') != 'edge-tts' or payload.get('version') != 1:
            return []
        seconds = wav_length(wav)
        words = payload.get('words', [])
        if not isinstance(words, list):
            return []
        return [word for word in words
                if isinstance(word, dict) and isinstance(word.get('text'), str)
                and isinstance(word.get('start'), (int, float))
                and isinstance(word.get('end'), (int, float))
                and 0 <= word['start'] < word['end'] <= seconds + 0.05][:10000]
    except (ValueError, TypeError, OSError, EOFError):
        return []


def voice_catalog(refresh: bool = False) -> dict:
    """Discover *actually returned* voices from the Edge endpoint.

    Microsoft's Azure voice catalog is not guaranteed to match Edge-TTS.
    """
    global _catalog
    if _catalog and not refresh and time.monotonic() - _catalog[0] < _CATALOG_TTL:
        return {'source': 'edge-live-cache', 'voices': _catalog[1], 'verified': True}
    import edge_tts
    async def fetch():
        return await asyncio.wait_for(edge_tts.list_voices(), timeout=15)
    voices = asyncio.run(fetch())
    result = []
    for voice in voices:
        name = voice.get('ShortName', '')
        locale = voice.get('Locale', '')
        if locale not in ('hi-IN', 'en-IN') or not name.endswith('Neural'):
            continue
        result.append({'id': name, 'locale': locale,
                       'gender': voice.get('Gender', 'Unknown'),
                       'name': voice.get('FriendlyName', name)})
    result.sort(key=lambda x: (x['locale'] != 'hi-IN', x['gender'] != 'Male', x['id']))
    if not result:
        raise RuntimeError('Edge voice endpoint returned no Hindi/Indian-English voices.')
    _catalog = (time.monotonic(), result)
    return {'source': 'edge-live', 'voices': result, 'verified': True}


def synthesize_line(line: dict, profile: dict | None = None, ws=None) -> tuple[Path, float]:
    profile = profile or SPEAKERS[line['speaker']]
    mp3, wav = audio_paths(line, profile, ws)
    if wav.exists() and wav.stat().st_size > 2000:
        return wav, wav_length(wav)
    if mp3.exists() and mp3.stat().st_size > 2000:
        convert_wav(mp3, wav)
        return wav, wav_length(wav)
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError('edge-tts not installed; re-run START.bat') from exc
    temp_mp3 = mp3.with_suffix('.part.mp3')
    temp_wav = wav.with_suffix('.part.wav')
    temp_meta = wav.with_suffix('.part.words.jsonl')

    async def generate():
        client = edge_tts.Communicate(text=line['text'], voice=profile['voice'],
                                      rate=profile['rate'], pitch=profile['pitch'],
                                      boundary='WordBoundary')
        await client.save(str(temp_mp3), str(temp_meta))

    for attempt in range(3):
        try:
            asyncio.run(generate())
            if not temp_mp3.is_file() or temp_mp3.stat().st_size < 1000:
                raise RuntimeError('Voice service returned empty audio')
            convert_wav(temp_mp3, temp_wav)
            seconds = wav_length(temp_wav)
            words = parse_edge_metadata(temp_meta.read_text(encoding='utf-8'), seconds) if temp_meta.exists() else []
            # Finalize audio first. If metadata is absent, captions fall back to estimated timing.
            temp_mp3.replace(mp3)
            temp_wav.replace(wav)
            aligned = alignment_path(wav)
            if words:
                staging = aligned.with_suffix('.words.part.json')
                staging.write_text(json.dumps({'engine': 'edge-tts', 'version': 1, 'words': words},
                                              ensure_ascii=False), encoding='utf-8')
                staging.replace(aligned)
            else:
                aligned.unlink(missing_ok=True)
            uploaded_marker(wav).unlink(missing_ok=True)
            temp_meta.unlink(missing_ok=True)
            return wav, seconds
        except Exception as exc:
            for path in (temp_mp3, temp_wav, temp_meta):
                path.unlink(missing_ok=True)
            if attempt == 2:
                raise RuntimeError(f'Online voice generation failed: {exc}. '
                                   'Try a verified voice from the catalog, or upload your own audio.') from exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError('TTS failed')


def set_uploaded_audio(line: dict, contents: bytes, extension: str,
                       profile: dict | None = None, ws=None) -> Path:
    if extension.lower() not in {'.wav', '.mp3', '.m4a'}:
        raise ValueError('Supported formats: wav, mp3, m4a.')
    if not contents or len(contents) > 20 * 1024 * 1024:
        raise ValueError('Audio must be 1 byte to 20 MB.')
    mp3, wav = audio_paths(line, profile, ws)
    origin = mp3.with_suffix('.upload' + extension.lower())
    origin.write_bytes(contents)
    temp = wav.with_suffix('.tmp.wav')
    try:
        convert_wav(origin, temp)
        if wav_length(temp) < 0.3:
            raise ValueError('Audio is too short.')
        temp.replace(wav)
        alignment_path(wav).unlink(missing_ok=True)
        uploaded_marker(wav).write_text(origin.name, encoding='utf-8')
    except Exception:
        temp.unlink(missing_ok=True)
        origin.unlink(missing_ok=True)
        raise
    return wav


def reset_line_audio(line: dict, profile: dict | None = None, ws=None) -> None:
    mp3, wav = audio_paths(line, profile, ws)
    mp3.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    alignment_path(wav).unlink(missing_ok=True)
    uploaded_marker(wav).unlink(missing_ok=True)
    for file in mp3.parent.glob(mp3.stem + '.upload.*'):
        file.unlink(missing_ok=True)
