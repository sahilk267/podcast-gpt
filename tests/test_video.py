import subprocess
import wave
from pathlib import Path
from podcast.settings import DATA
from podcast.video import scene_image, render_static, render_motion, join_clips, ffmpeg_path


def test_scene_dimensions():
    from podcast.project import sample_project
    project = sample_project()
    im = scene_image(project['title'], project['lines'][0], 1, len(project['lines']))
    assert im.size == (960, 540)


def test_render_short_synthetic_audio(tmp_path: Path):
    # This integration test is optional and tests only the CPU video pipeline, not voice network/model installs.
    import math
    import struct
    duration = 0.42
    path = tmp_path / 'sample.wav'
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
        f.writeframes(b''.join(struct.pack('<h', int(5000*math.sin(2*math.pi*220*n/16000))) for n in range(int(16000*duration))))
    from podcast.project import sample_project
    project = sample_project()
    png = tmp_path / 'scene.png'
    scene_image(project['title'], project['lines'][0], 1, 32).save(png)
    static = tmp_path / 'static.mp4'
    motion = tmp_path / 'motion.mp4'
    render_static(png, path, duration, static)
    render_motion(png, path, project['lines'][0], duration, motion)
    assert static.stat().st_size > 1000
    assert motion.stat().st_size > 1000
    joined = tmp_path / 'joined.mp4'
    # join_clips outputs inside data/exports list, but final destination can be temp.
    join_clips([static, motion], joined)
    assert joined.stat().st_size > 1000
