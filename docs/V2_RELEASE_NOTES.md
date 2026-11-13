# Podcast GPT V2 Alpha — 2026-11-14

This is **V2 Milestone 1**, not the completed cinematic 3-AI-actor product. Built for a standard Windows computer with **no dedicated GPU**.

## What is implemented

- Multi-episode local project library and per-episode separate assets/exports, with a safe **copy-based migration** of existing V1 `data/project.json` and its media into an `ep-legacy-migrated` workspace.
- Topic/title/target-duration fields. An intentionally short 3-turn generic starter is provided for a new episode. The `Copy 10-minute AI script prompt` action delegates substantive script generation to your own ChatGPT conversation; users can paste/import 3-speaker scripts using `Aarav:`, `Meera:`, `Kabir:` lines.
- Per-speaker editable names/roles and voice presets with speed/pitch, plus user-supplied audio for any dialogue. Hindi TTS still only has **two standard neural identities**. The distinct third English-India voice is an optional workaround and may mispronounce Hindi; the preferred workaround is to upload a real third voice.
- Per-line shot direction (**wide** or **focus**) and configurable pauses, plus target/actual duration meter.
- 720p and upscaled 1080p / 24fps MP4 outputs; 1080p is not native 1080p talking-face detail.
- Dialogue-level SRT export; it is **not** word-aligned. For a long line, the SRT may require manual subtitle splitting/editing.
- Per-project per-dialogue cached MP4 segments for reuse when a render is repeated. Stop request only takes effect between dialogues (neural jobs may take a long time).
- Explicit reset of generated/uploaded WAV takes and better per-line voice control.
- Offline automated API/render tests using generated synthetic WAV input; no paid API or GPU needed.

## Not implemented or not yet verified

- No built-in LLM or image generator. Automated long-form factual script generation requires an external AI, and facts need review.
- No reliably deployable, real-time, full 10-minute photorealistic neural talking-head engine on a slow Windows CPU. SadTalker optional installer/adapter remains **experimental**, and still uses legacy Python 3.8 and external weights.
- No built-in full-body gestures/blinks, simultaneous speaking, cinematic camera footage, or actual physical 3-person studio capture.
- No perfect 3 distinct Hindi voices from the bundled online Edge TTS service; user must choose/bring a third.
- No video burned-in word-level subtitles, master audio EQ, licensed background music, automated publishing, logo branding, or 4K.
- Internet and third-party provider licensing/publishing conditions remain outside project control.
- Python dependency ranges are bounded but not reproducibly hash-locked. CI success is not equivalent to manual deployment/voice/neural validation on your specific Windows PC.

## Suggested next milestones

1. **Windows real-machine gate:** fresh clone on Windows 10/11 + CPU-only, `START.bat` complete, 3 distinct user-provided WAV takes, 2-minute source footage export with correct SRT, no admin privileges, no missing fonts.
2. **Voice authoring:** reliable third Hindi voice provider (licensed), pronunciation dictionary, failure retries, pause editing, consistent speaking style.
3. **Neural talking portraits:** pinned model packages and weights, 5-second CPU benchmark, accurate crop mapping, resumable per-turn neural render, measured actual 10-minute performance.
4. **Production:** video/timeline editor, 1080p native assets, safe-area subtitles, transitions, EQ, title cards, music, 9:16 shorts, disclosure/license checklist.

## Troubleshooting and safety

Local UI binds to `127.0.0.1:8765`. All user project files stay in `data/projects/<episode-id>/`. Do not expose this local server on a public network. To upgrade run `git pull origin main` and double-click `START.bat`; V1 user data remains in the original location and is copied during migration. Back up `data/` before any upgrade.

For sex education and health, the fictional expert should be described as an educator, not a licensed doctor unless that is truthful. Check medical facts before publishing and disclose AI speakers.
