# Optional neural lip-sync: SadTalker CPU backend

This application runs **without SadTalker** in its static and approximate-mouth-motion modes. For genuine AI talking portraits, install the **optional** upstream SadTalker backend.

## Setup

1. Install [Python 3.8.10 (64-bit)](https://www.python.org/downloads/release/python-3810/) and [Git for Windows](https://git-scm.com/download/win), ensure Python launcher `py -3.8` works. Keep Python 3.8 separate from the core app's Python 3.11 environment.
2. Double-click `INSTALL_AI.bat`. The script clones [OpenTalker/SadTalker](https://github.com/OpenTalker/SadTalker) into `third_party/SadTalker`, creates `.venv38/`, installs PyTorch CPU / upstream requirements, and downloads the 256-pixel checkpoints and facial alignment files from official GitHub release sources.
3. Ensure installation finished without errors. The UI checks `.venv38/Scripts/python.exe`, SadTalker's `inference.py`, and its main safetensors checkpoint. **This check does not prove that full inference works.**
4. In the UI upload a separate, front-facing portrait for each of the three speakers and generate the audio tracks.
5. Select **SadTalker AI** and test a short dialogue first. Full 10-minute renders on ordinary CPUs can be unreasonably slow. SadTalker AI uses `--cpu --size 256 --batch_size 1 --preprocess crop --still`. Animation is generated for the active speaker, overlaid in their card, then combined with the other characters' static portraits.

### Manual verification

Run this in PowerShell from the project directory (adapt the audio and image paths):

```powershell
cd third_party\SadTalker
..\..\.venv38\Scripts\python.exe inference.py `
  --driven_audio "..\..\data\wav\001_example.wav" `
  --source_image "..\..\data\portraits\aarav.png" `
  --cpu --size 256 --batch_size 1 --preprocess crop
```

Use an **actual** filename listed in `data/wav/` rather than the illustrative `001_example.wav` path above. Models and face-detector weights are stored under SadTalker's `checkpoints` and `gfpgan/weights`.

### Known problems

- Legacy libraries (Python 3.8 and PyTorch 1.12) are old; dependencies may need manual fixes on some systems. This third-party stack is **not** installed with `START.bat` because it can break or delay the core studio.
- `torch.cuda.is_available() == False` is expected on a CPU-only machine.
- Face detection prefers one straight-on, well-lit human-like portrait with visible mouth.
- Model downloads may exceed gigabytes and can fail due to upstream redirects, network filters or rate limits. Retry `INSTALL_AI.bat` (it skips already-downloaded files above a size threshold).
- Keep the terminal open while rendering; processed clips are saved under `data/clips/` and the final MP4 under `data/exports/`.
- This installer has **not been fully run on every supported Windows configuration**; use the tested static/motion pipeline if it fails.

Docs: [upstream install](https://github.com/OpenTalker/SadTalker/blob/main/docs/install.md), [upstream best practices](https://github.com/OpenTalker/SadTalker/blob/main/docs/best_practice.md).
