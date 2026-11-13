# Podcast GPT V2 — Local AI Podcast Studio

**Free-first, Windows CPU-first.** Create multiple podcast episodes using three fictional/authorized portrait characters, Hindi/Hinglish dialogue, editable voice profiles, uploaded audio, speaker-directed visual panels and MP4 + SRT export. **V2 Alpha** is a working local creator—not an automatic unlimited cinema-quality lip-sync service.

## Start on Windows

```powershell
git clone https://github.com/sahilk267/podcast-gpt.git
cd podcast-gpt
.\START.bat
```

Or download a GitHub ZIP, extract it, and **double-click `START.bat`**. Windows 10/11 (64-bit) and Internet are recommended. The launcher locates Python 3.10–3.12, prefers 3.11, and can offer a `winget` Python installation. If that fails, install Python 3.11 manually from https://python.org and retry. Initial setup installs dependencies to `.venv`. No separate system FFmpeg install is required for normal video export.

The launcher opens **http://127.0.0.1:8765**. Leave the terminal window open while using the app. No API key is required for the core editor.

### Upgrade from V1

```powershell
cd podcast-gpt
git pull origin main
.\START.bat
```

Existing `data/project.json` plus old audio/portraits/clips are **copied**, not deleted, to `data/projects/ep-legacy-migrated/` on first V2 launch. Make a backup of `data/` before upgrading. Each new episode has its own `project.json`, portraits, audio, cached clips and exports under `data/projects/<id>/`.

## How to make an episode

1. **New episode:** set title, topic and target duration (default 10 minutes). A 3-turn editable **starter** is created; it is NOT a 10-minute automatically generated script.
2. **Script:** click **Copy 10-minute AI script prompt**, send it to ChatGPT, review/fact-check the response. Paste conversation lines as `Aarav: ...`, `Meera: ...`, `Kabir: ...` in **Import speaker dialogue**, then Save. Choose **Wide** or **Focus** shot per turn and pause after turns.
3. **Characters:** upload one front-facing licensed/authorized fictional portrait per speaker; edit names/roles and voice presets. External image generator required.
4. **Voices:** use **Generate missing audio**, individual **Generate** buttons, or manually **upload a WAV/MP3/M4A** per line. Replacing a script line or profile automatically changes its cache key; Reset removes an existing take. Edge-based online speech requires internet and is unofficial/unreliable for long-term service guarantees.
5. **Produce:** choose **Static** for dependable CPU playback, **CPU mouth motion** for a visual-only audio-reactive approximation, or **SadTalker AI (experimental)** for genuine neural talking face inference. Export 720p or upscaled 1080p MP4 plus dialogue-level SRT captions. Preview MP4 in browser.
6. If a render is interrupted or fails, retry the **same unchanged project/mode/quality** to reuse already completed dialogue clips.

**Actual podcast duration** is calculated from generated/uploaded audio **plus inter-dialogue pauses**. Target length is a comparison, not an automatic duration guarantee. Continue editing until near 10 minutes.

### Voice reality

By default Hindi has **Madhur male** and **Swara female** Edge neural voice identities. The third male Kabir uses a modified Madhur voice by default; this is **not** an independent third identity. A different English-India voice is selectable but may not pronounce Hindi accurately. For three unmistakably distinct Hindi voices, upload custom third-speaker audio or use a properly licensed external provider. Never clone real people's voices without consent.

## What this project can and cannot do

| Capability | Current status |
|---|---|
| Multi-episode saving and V1 backup migration | Yes |
| Script editor, ChatGPT prompt export, bulk dialogue import | Yes; no built-in LLM |
| 3 portrait uploads + editable character names | Yes; no image generator |
| Online Hindi TTS and custom speech imports | Yes; two standard Hindi voices |
| Speaker-directed close-up/wide composition | Yes; pictures, not multi-camera footage |
| True natural 3-person AI lip-sync | **Not guaranteed**; optional unverified SadTalker |
| CPU mouth motion | Approximation, not accurate lip-sync |
| 720p / 1080p export, 24 FPS | Yes; 1080p upscale of 960×540 scenes |
| Dialogue SRT + editable pauses | Yes; not word-level captions |
| Render retry with finished clips cached | Yes; cancellation between turns |
| Automatic fact-checked 10-minute video with one click | **Not implemented** |

Read **[V2 release notes](docs/V2_RELEASE_NOTES.md)** and **[product gaps/specification](docs/PRODUCT_SPEC_V2.md)** before treating this as a finished system.

## Developer setup / tests

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest httpx
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe -m uvicorn podcast.app:app --host 127.0.0.1 --port 8765
```

The tests include isolated project saves, input validation, API smoke tests and an **offline synthetic audio three-speaker render with SRT**. Continuous integration tests on Windows and Ubuntu. The tests do not validate the external Edge TTS service, SadTalker inference or a complete 10-minute realistic episode.

## Technical overview

- Python FastAPI API: `podcast/app.py`; browser app: `static/`.
- Data: `podcast/workspace.py`, `podcast/project.py`.
- TTS/custom voice: `podcast/voice.py`.
- FFmpeg still-image and CPU approximate-motion scene compositor: `podcast/video.py`; SRT: `podcast/subtitles.py`.
- Optional genuine neural backend: [SadTalker setup](docs/SADTALKER.md). `INSTALL_AI.bat` installs legacy Python 3.8 model dependencies separately from the reliable core app. This path is experimental, potentially slow and may need manual fixes.
- Python packages are range-bounded in `requirements.txt`; they are not fully hash-locked. `START.bat` attempts to bootstrap but no developer can guarantee one-click setup on all Windows configurations.
- Local browser UI runs only on `127.0.0.1`; no public user accounts or cloud database. Do not change host binding without adding authentication.

## Responsible use

Use AI-generated original or consented likenesses and voice recordings. Check portrait/voice/model terms before publishing or monetizing. Clearly disclose fictional AI presenters. A fictional educator is not a real licensed medical professional. Sex education episodes should be respectful, non-graphic and based on reliable medical information.

MIT license covers this project's code only, not third-party models, user-provided media, TTS provider rights or model weights.
