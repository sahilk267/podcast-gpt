"""CPU-friendly video compositor and optional SadTalker integration.

Static mode works with FFmpeg alone. Motion mode is an intentionally approximate,
energy-driven mouth deformation (NOT phoneme-level neural lip-sync). AI mode runs
upstream SadTalker on CPU when the user installs its optional dependencies.
"""
from __future__ import annotations
import hashlib
import math
import os
import subprocess
import sys
import wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from .settings import BASE, IMAGES, SCENES, CLIPS, EXPORTS, WAV, SPEAKERS

WIDTH, HEIGHT = 960, 540
FPS = 12
PANEL_Y, PANEL_H = 94, 324
PANEL_W = 263
PANEL_X = (35, 348, 661)
COLORS = {'aarav': '#54c3ff', 'meera': '#ffb7d7', 'kabir': '#9ef1cb'}


def ffmpeg_path() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def system_font(bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    filenames = [
        'C:/Windows/Fonts/NirmalaB.ttf' if bold else 'C:/Windows/Fonts/Nirmala.ttf',
        'C:/Windows/Fonts/mangal.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for file in filenames:
        if Path(file).exists():
            try: return ImageFont.truetype(file, 20 if bold else 18)
            except OSError: pass
    return ImageFont.load_default()


def crop_cover(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(source.convert('RGB'), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.43))


def portrait(speaker: str) -> Image.Image:
    path = IMAGES / f'{speaker}.png'
    if path.exists():
        with Image.open(path) as im:
            return crop_cover(im, (PANEL_W, PANEL_H))
    # Distinct fallback cards are generated locally; user uploads realistic photos.
    bg = Image.new('RGB', (PANEL_W, PANEL_H), {'aarav': '#193e5c', 'meera': '#5a2946', 'kabir': '#1e4d40'}[speaker])
    d = ImageDraw.Draw(bg)
    d.ellipse((71, 55, 190, 174), fill='#a1abba')
    d.rounded_rectangle((45, 185, 220, 358), radius=70, fill='#8493ac')
    return bg


def _wrapped(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int = 2) -> list[str]:
    tokens = text.split(' ')
    rows = []
    line = ''
    for token in tokens:
        candidate = f'{line} {token}'.strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
        else:
            if line: rows.append(line)
            line = token
        if len(rows) >= max_lines:
            break
    if line and len(rows) < max_lines:
        rows.append(line)
    if len(rows) == max_lines and len(' '.join(rows)) < len(text):
        rows[-1] = rows[-1].rstrip(' .') + '...'
    return rows


def scene_image(title: str, line: dict, turn: int, total: int) -> Image.Image:
    canvas = Image.new('RGB', (WIDTH, HEIGHT), '#0b1122')
    draw = ImageDraw.Draw(canvas)
    normal, strong = system_font(), system_font(bold=True)
    draw.rounded_rectangle((23, 18, 937, 76), radius=18, fill='#151e33')
    draw.text((42, 31), 'PODCAST GPT', font=strong, fill='#ffffff')
    draw.text((235, 33), title[:90], font=normal, fill='#bbc7e4')
    draw.text((855, 34), f'{turn}/{total}', font=normal, fill='#7a8eaf')
    active = line['speaker']
    for i, (key, speaker) in enumerate(SPEAKERS.items()):
        x = PANEL_X[i]
        active_now = key == active
        frame_color = COLORS[key] if active_now else '#283851'
        draw.rounded_rectangle((x - 3, PANEL_Y - 3, x + PANEL_W + 3, PANEL_Y + PANEL_H + 45),
                               radius=16, fill=frame_color if active_now else '#192238')
        canvas.paste(portrait(key), (x, PANEL_Y))
        draw = ImageDraw.Draw(canvas)
        label = f"{speaker['name']}  /  {speaker['role']}"
        draw.text((x + 8, PANEL_Y + PANEL_H + 11), label, font=normal, fill='#101827' if active_now else '#e6eefd')
        if active_now:
            draw.ellipse((x + PANEL_W - 26, PANEL_Y + 10, x + PANEL_W - 10, PANEL_Y + 26), fill='#58e4a1')
    draw.rounded_rectangle((23, 472, 937, 530), radius=12, fill='#18223a')
    preview = _wrapped(draw, line['text'], normal, 875, 2)
    for j, part in enumerate(preview):
        draw.text((42, 480 + j * 23), part, font=normal, fill='#f4f7ff')
    return canvas


def run_ffmpeg(arguments: list[str], *, timeout: int = 3600) -> None:
    proc = subprocess.run([ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-y', *arguments],
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode:
        raise RuntimeError(f'FFmpeg failed: {proc.stderr[-2000:]}')


def _video_output_args(path: Path, seconds: float) -> list[str]:
    return ['-t', f'{seconds:.3f}', '-r', str(FPS), '-vf', 'scale=1280:720:flags=bilinear',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '25',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(path)]


def render_static(scene: Path, wav: Path, seconds: float, output: Path) -> None:
    run_ffmpeg(['-loop', '1', '-framerate', str(FPS), '-i', str(scene), '-i', str(wav),
                *_video_output_args(output, seconds)])


def _read_audio_envelopes(wav: Path, frames: int) -> list[float]:
    import numpy as np
    with wave.open(str(wav), 'rb') as handle:
        sample_rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
        channels = handle.getnchannels()
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    env = []
    for frame in range(frames):
        a = int(frame * sample_rate / FPS)
        b = min(len(samples), int((frame + 1) * sample_rate / FPS))
        chunk = samples[a:b]
        env.append(float(np.sqrt(np.mean(chunk * chunk))) if len(chunk) else 0.0)
    high = max(max(env), 0.03)
    norm = [min(1.0, max(0.0, (v / high - 0.09) / 0.65)) for v in env]
    smooth = []
    previous = 0.0
    for v in norm:
        previous = previous * 0.45 + v * 0.55
        smooth.append(previous)
    return smooth


def render_motion(scene: Path, wav: Path, line: dict, seconds: float, output: Path) -> None:
    """Approximate, non-AI local mouth movement, works without a GPU."""
    base = Image.open(scene).convert('RGB')
    x = PANEL_X[list(SPEAKERS).index(line['speaker'])]
    # Use calibrated front-facing portraits: mouth near x50%, y61% of image.
    cx, cy = x + PANEL_W // 2, PANEL_Y + int(PANEL_H * 0.62)
    rect = (cx - 44, cy - 23, cx + 44, cy + 23)
    clean = base.crop(rect)
    frames = max(1, math.ceil(seconds * FPS))
    env = _read_audio_envelopes(wav, frames)
    cmd = [ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-y',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{WIDTH}x{HEIGHT}',
           '-r', str(FPS), '-i', '-', '-i', str(wav), *_video_output_args(output, seconds)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for e in env:
            frame = base.copy()
            if e > 0.065:
                # Subtle movement; not a learned phoneme-to-viseme model.
                mid = clean.height // 2
                upper = clean.crop((0, 0, clean.width, mid))
                lower = clean.crop((0, mid, clean.width, clean.height))
                shift = min(5, round(e * 5))
                patch = clean.copy()
                patch.paste(upper, (0, -shift))
                patch.paste(lower, (0, mid + shift))
                # Dark narrow mouth opening, feathered into the original area.
                alpha = Image.new('L', clean.size, 0)
                mask_draw = ImageDraw.Draw(alpha)
                mask_draw.ellipse((7, 8, 81, 38), fill=175)
                alpha = alpha.filter(ImageFilter.GaussianBlur(9))
                frame.paste(patch, (rect[0], rect[1]), alpha)
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode('utf-8', 'replace')
        if proc.wait() != 0:
            raise RuntimeError(f'FFmpeg failed: {err[-2000:]}')
    except Exception:
        try: proc.kill()
        except OSError: pass
        raise
    finally:
        base.close()
        clean.close()


def sadtalker_ready() -> bool:
    py = BASE / '.venv38' / 'Scripts' / 'python.exe' if os.name == 'nt' else BASE / '.venv38' / 'bin' / 'python'
    external = BASE / 'third_party' / 'SadTalker'
    return (py.exists() and (external / 'inference.py').exists() and
            (external / 'checkpoints' / 'SadTalker_V0.0.2_256.safetensors').exists())


def render_sadtalker(scene: Path, wav: Path, line: dict, seconds: float, output: Path, render_number: int) -> None:
    if not sadtalker_ready():
        raise RuntimeError('SadTalker not installed. Run INSTALL_AI.bat and check docs/SADTALKER.md.')
    py = BASE / '.venv38' / 'Scripts' / 'python.exe' if os.name == 'nt' else BASE / '.venv38' / 'bin' / 'python'
    external = BASE / 'third_party' / 'SadTalker'
    result_dir = CLIPS / f'_ai_{render_number:03d}'
    result_dir.mkdir(parents=True, exist_ok=True)
    arguments = [str(py), 'inference.py', '--driven_audio', str(wav),
                 '--source_image', str(IMAGES / (line['speaker'] + '.png')),
                 '--result_dir', str(result_dir), '--cpu', '--size', '256',
                 '--batch_size', '1', '--preprocess', 'crop', '--still']
    proc = subprocess.run(arguments, cwd=external, capture_output=True, text=True, timeout=7200)
    if proc.returncode:
        raise RuntimeError(f'SadTalker failed: {(proc.stderr or proc.stdout)[-2500:]}')
    videos = sorted(result_dir.rglob('*.mp4'), key=lambda f: f.stat().st_mtime, reverse=True)
    if not videos:
        raise RuntimeError(f'SadTalker produced no video. Output: {proc.stdout[-1000:]}')
    x = PANEL_X[list(SPEAKERS).index(line['speaker'])]
    # Overlay AI-talking head inside the active speaker's panel of the full scene.
    filter_complex = (f'[0:v]scale={WIDTH}:{HEIGHT}[bg];'
                      f'[1:v]scale={PANEL_W}:{PANEL_H}:force_original_aspect_ratio=increase,'
                      f'crop={PANEL_W}:{PANEL_H},setsar=1[face];'
                      f'[bg][face]overlay={x}:{PANEL_Y}:shortest=0:repeatlast=1,'
                      f'scale=1280:720:flags=bilinear[v]')
    run_ffmpeg(['-loop', '1', '-framerate', str(FPS), '-i', str(scene),
                '-i', str(videos[0]), '-i', str(wav),
                '-filter_complex', filter_complex, '-map', '[v]', '-map', '2:a:0',
                '-t', f'{seconds:.3f}', '-r', str(FPS), '-c:v', 'libx264',
                '-preset', 'ultrafast', '-crf', '25', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(output)], timeout=7200)


def join_clips(clips: list[Path], dest: Path) -> None:
    playlist = EXPORTS / 'concat.txt'
    # All segments are encoded with identical video/audio settings.
    playlist.write_text(''.join(f"file '{str(clip.resolve()).replace(chr(39), chr(39)+chr(92)+chr(39))}'\n"
                                for clip in clips), encoding='utf-8')
    run_ffmpeg(['-f', 'concat', '-safe', '0', '-i', str(playlist), '-c', 'copy', '-movflags', '+faststart', str(dest)], timeout=3600)


def output_name(project: dict, mode: str) -> str:
    content = (project['title'] + mode + ''.join(line['id'] + line['text'] for line in project['lines'])).encode()
    return 'podcast-' + hashlib.sha1(content).hexdigest()[:10] + '-' + mode + '.mp4'
