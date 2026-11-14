"""Time-stamped SRT subtitles with genuine Edge-TTS word timings when present.

Custom-uploaded WAV/MP3 has no word alignment. Such lines deliberately fall
back to an *estimated* proportional split. We never label that as word-aligned.
"""
from __future__ import annotations
from pathlib import Path


def _timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, rest = divmod(millis, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f'{hours:02}:{minutes:02}:{secs:02},{ms:03}'


def _caption_chunks(text: str, limit: int = 75) -> list[str]:
    chunks, chunk = [], ''
    for word in text.split():
        next_chunk = f'{chunk} {word}'.strip()
        if chunk and len(next_chunk) > limit:
            chunks.append(chunk)
            chunk = word
        else:
            chunk = next_chunk
    if chunk:
        chunks.append(chunk)
    return chunks or ['']


def _timed_word_chunks(words: list[dict], seconds: float, limit: int = 66,
                       max_words: int = 10) -> list[tuple[float, float, str]]:
    """Group true timecoded words; subtitles are sparse during speech pauses."""
    cleaned = []
    for word in words:
        try:
            start, end = float(word['start']), float(word['end'])
            body = str(word['text']).strip()
            if not body or not 0 <= start < end <= seconds + 0.06:
                continue
            cleaned.append((start, min(seconds, end), body))
        except (ValueError, TypeError, KeyError):
            continue
    cleaned.sort(key=lambda w: w[0])
    if not cleaned:
        return []
    chunks = []
    current = []
    for item in cleaned:
        text = ' '.join(x[2] for x in current)
        gap = item[0] - current[-1][1] if current else 0
        if current and (len(current) >= max_words or len(text) + len(item[2]) + 1 > limit or gap > 0.75):
            chunks.append((current[0][0], max(x[1] for x in current), text))
            current = []
        current.append(item)
    if current:
        chunks.append((current[0][0], max(x[1] for x in current), ' '.join(x[2] for x in current)))
    return chunks


def srt_text(lines: list[dict], durations: list[float], names: dict[str, str] | None = None,
             alignments: list[list[dict]] | None = None) -> str:
    if len(lines) != len(durations):
        raise ValueError('Each dialogue needs one duration.')
    if alignments is not None and len(alignments) != len(lines):
        raise ValueError('Each dialogue needs one alignment array.')
    names = names or {}
    out, cursor, index = [], 0.0, 1
    tracks = alignments if alignments is not None else [[] for _ in lines]
    for i, (line, seconds) in enumerate(zip(lines, durations)):
        if seconds < 0:
            raise ValueError('Duration cannot be negative')
        timed = _timed_word_chunks(tracks[i], seconds)
        if not timed:
            # Estimated captions for uploaded audio or missing metadata.
            chunks = _caption_chunks(' '.join(line['text'].split()))
            lengths = [max(1, len(chunk)) for chunk in chunks]
            total = sum(lengths)
            position = 0.0
            timed = []
            for j, (chunk, length) in enumerate(zip(chunks, lengths)):
                end = seconds if j == len(chunks) - 1 else position + seconds * length / total
                timed.append((position, end, chunk))
                position = end
        for start, end, body in timed:
            if end <= start:
                continue
            speaker = names.get(line['speaker'], line['speaker'])
            out.append(f'{index}\n{_timestamp(cursor + start)} --> {_timestamp(cursor + end)}\n{speaker}: {body}\n')
            index += 1
        cursor += seconds + float(line.get('pause_after', 0))
    return '\n'.join(out) + '\n'


def write_srt(path: Path, lines: list[dict], durations: list[float],
              names: dict[str, str] | None = None,
              alignments: list[list[dict]] | None = None) -> Path:
    path.write_text(srt_text(lines, durations, names, alignments), encoding='utf-8-sig')
    return path
