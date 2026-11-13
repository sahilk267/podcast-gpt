# Podcast GPT — Windows CPU Podcast Studio

**3 fictional characters · Hindi/Hinglish voices · editable Q&A · local MP4 rendering · optional neural lip-sync.**

A local-first, free/open-source creator tool designed for normal Windows computers **without a dedicated GPU**. It is a functional studio application, not a magical unlimited online video generator. Your portraits and podcast files stay in the local `data/` directory. An internet connection is used for first-run package installation and Edge-generated voices.

## 🚀 One-click start on Windows

1. Download the repository as a ZIP, extract it, or clone it:
   ```powershell
   git clone https://github.com/sahilk267/podcast-gpt.git
   cd podcast-gpt
   ```
2. **Double-click `START.bat`.** It will find Python 3.10–3.12 (prefers 3.11), try installing Python 3.11 through `winget` if missing, create `.venv`, install Python packages, and open `http://127.0.0.1:8765` once the server is ready.
3. On your first launch, allow enough disk space and internet access. `winget` may prompt for approval. If Python couldn't be installed automatically, install [Python 3.11 (64-bit)](https://www.python.org/downloads/release/python-3119/) and run `START.bat` again.
4. Upload **three front-facing fictional/consented portraits**. Script → Characters → Voices → Produce.
5. Click **Generate all voices** (Edge TTS uses Microsoft's online speech endpoint, no key). You can also **upload your own .wav/.mp3/.m4a audio** for any dialogue turn.
6. First render in **Static** mode to verify audio and layout, then choose **CPU mouth motion**, or optionally install SadTalker for neural talking faces.
7. Download the final `.mp4` from Produce. Output is **1280×720 / H.264 / AAC**; saved in `data/exports/`.

**On later starts**, `START.bat` reuses the virtual environment and avoids unnecessary package installs unless `requirements.txt` changes. Leave the terminal window running while using the app. Stop the app by closing it / pressing Ctrl+C in the terminal.

## Features

- 3 speaker identities: Aarav (Hindi male), Meera (Hindi female), Kabir (Hindi male with different rate/pitch). The free voice provider gives us **two distinct Hindi neural voice identities**, so Kabir is a *variation* of Aarav rather than a unique third actor. Custom recorded voices supported.
- Editable 1–100 turn script, auto-save on demand, and sample **sex-education Q&A** script with educational, non-graphic discussion and a fictional-speaker disclosure.
- Upload PNG/JPG/WebP images. Image creation is **not built in**; generate from external tools like Leonardo or create your own. Placeholder portraits are simplistic illustrations.
- Real per-line audio generation and duration display. Output duration depends on actual speech rate, **not** fixed at 10 minutes. Edit/add dialogue until duration meets your target.
- **Static mode:** CPU-friendly composited 3-person podcast with active speaker highlighting and visible captions (no moving lips).
- **CPU mouth-motion mode:** Audio-reactive approximate mouth deformation—**not phoneme-accurate realistic neural lip-sync**. Results vary with photo framing.
- **SadTalker AI mode:** Optional CPU inference through upstream [OpenTalker/SadTalker](https://github.com/OpenTalker/SadTalker), with a separate Python 3.8 environment, model weights, and significant processing cost. No CUDA needed, but some old dependency combinations may fail on modern Windows. See [docs/SADTALKER.md](docs/SADTALKER.md).
- MP4 encoding uses bundled `imageio-ffmpeg`: no system-wide FFmpeg installation required for the main app.
- Local UI binds only to `127.0.0.1`; media and projects remain in the local `data/` folder.

## Updated code on your machine

```powershell
cd podcast-gpt
git pull origin main
# Then double-click START.bat
```

## Architecture

```text
START.bat                        PowerShell bootstrap, Python venv, browser launch
INSTALL_AI.bat                   Optional SadTalker CPU setup (may need manual fixes)
podcast/app.py                   FastAPI local API / job manager / safe uploads
podcast/project.py               Editable project validation + SHA-aware audio cache
podcast/voice.py                 Online Edge TTS + uploaded audio + 16 kHz WAV
podcast/video.py                 FFmpeg scene renderer, approximate CPU motion, SadTalker bridge
static/                          Browser-based studio UI
samples/project.json             Editable 32-turn Hindi episode
scripts/                         Windows setup scripts
tests/                           Unit tests + synthetic-audio video smoke test
data/                            Local user content (ignored by Git)
```

### Local API

- `GET /api/health`, `GET /api/project`, `PUT /api/project`
- `POST /api/portrait/{aarav|meera|kabir}`
- `POST /api/audio/{line_id}` — attach user-provided dialogue audio
- `POST /api/voices` — generate missing voice tracks
- `POST /api/render` — `{ "mode": "static" | "motion" | "ai" }`
- `GET /api/job/{id}` — job progress/result

Only **one long-running job** is allowed at a time; rendering jobs run in a background worker while the local browser polls progress. No jobs are executed after the computer shuts down. Audio caching uses script text + voice settings to invalidate changed lines.

## Windows troubleshooting

| Symptom | Next step |
|---|---|
| `py` / Python not found | Install Python 3.11 64-bit and reopen `START.bat`. |
| `winget` not found | Install Python manually from the official site. |
| Server cannot open port 8765 | Close other apps using port 8765; check console output. |
| Voice generation fails | Check internet access / firewall; Edge TTS online backend can change or rate limit. Upload your own audio instead. |
| Hindi script appears as empty boxes in export | Use Windows Nirmala UI / Mangal fonts; verify Windows language fonts. |
| Render is slow | Start with **Static** mode, then test 10 seconds in **CPU motion**. SadTalker is much slower on CPU. |
| SadTalker setup fails | See [docs/SADTALKER.md](docs/SADTALKER.md). Standard modes still work. |
| Audio is too long/short | Adjust script text or voices; the app shows total audio duration once generated. |
| Subtitles don't match words exactly | Current subtitles display dialogue snippets, not timed word-level captions. |

For diagnostics (after `START.bat` has succeeded):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
```

## Licensing and responsible use

- App code: **MIT** (see `LICENSE`). SadTalker code, model weights, and voice services have **their own terms**; not bundled in this repository.
- Upstream SadTalker says its license is Apache 2.0 and has removed a prior non-commercial restriction. Still check all third-party model/voice/image usage rights and current service terms **before publishing/monetizing**.
- Use your own characters or portraits with permission, disclose AI-generated presenters, and never imply a fictional medical speaker is a real licensed clinician.
- This project is a technical tool; no medical advice is implied by the sample script.

## What "one click" does **not** guarantee

It starts the **core studio** with automated setup where Python / internet / `winget` allow it. It cannot guarantee 100% successful installation on all Windows environments, an unlimited free voice API, perfect photorealistic lip-sync on CPU, or model downloads that external projects change. Test a short episode before a 10-minute neural render.
