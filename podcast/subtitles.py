"""Approximate phrase-level SRT timings from known dialogue audio durations.

This is *not* forced alignment. Captions are proportionally timed by character count.
"""
from __future__ import annotations
from pathlib import Path


def _timestamp(seconds: float) -> str:
    millis=max(0,round(seconds*1000))
    hours,rest=divmod(millis,3_600_000)
    minutes,rest=divmod(rest,60_000)
    secs,ms=divmod(rest,1000)
    return f'{hours:02}:{minutes:02}:{secs:02},{ms:03}'


def _caption_chunks(text: str, limit: int = 75) -> list[str]:
    """Split long sentences on spaces; avoid huge single-frame captions."""
    chunks=[];chunk=''
    for word in text.split():
        next_chunk=f'{chunk} {word}'.strip()
        if chunk and len(next_chunk)>limit:
            chunks.append(chunk)
            chunk=word
        else: chunk=next_chunk
    if chunk:chunks.append(chunk)
    return chunks or ['']


def srt_text(lines:list[dict],durations:list[float],names:dict[str,str]|None=None)->str:
    if len(lines)!=len(durations):raise ValueError('Each dialogue needs one duration.')
    names=names or {};out=[];cursor=0.0;index=1
    for line,seconds in zip(lines,durations):
        if seconds<0:raise ValueError('Duration cannot be negative')
        chunks=_caption_chunks(' '.join(line['text'].split()))
        lengths=[max(1,len(x)) for x in chunks]
        total=sum(lengths)
        position=cursor
        for j,(chunk,length) in enumerate(zip(chunks,lengths)):
            end=cursor+seconds if j==len(chunks)-1 else position+seconds*(length/total)
            speaker=names.get(line['speaker'],line['speaker'])
            out.append(f'{index}\n{_timestamp(position)} --> {_timestamp(end)}\n{speaker}: {chunk}\n')
            index+=1;position=end
        cursor+=seconds+float(line.get('pause_after',0))
    return '\n'.join(out)+'\n'


def write_srt(path:Path,lines:list[dict],durations:list[float],names:dict[str,str]|None=None)->Path:
    path.write_text(srt_text(lines,durations,names),encoding='utf-8-sig')
    return path
