# Podcast GPT v2 — Product specification and gap audit

**Status:** planning / NOT implemented. **Audit date:** 2026-11-13. **Baseline:** main at `a647412c60bcc61fa339b24bba4b4121f770453c`.

## 1. Product outcome

A nontechnical creator using a Windows 10/11 CPU-only PC should be able to produce a coherent ~10-minute three-person, Hindi/Hinglish, fictional AI video-podcast with original/authorized portraits, three recognizable voices, editable question/answer script, one active speaker per turn, intelligible subtitles and exportable MP4. Free-first: no *mandatory* paid service or GPU. External services, Internet, model download size, processing time, and licensing are disclosed. **It must not claim 10 minutes of realistic neural lip-sync is one-click or guaranteed on every CPU.**

### Required journey

1. Create a new project and supply a title/topic, language and target duration. Save multiple projects; never overwrite an unrelated episode.
2. Get a script via an explicit provider/optional local script generator **or** paste/import a generated script, then review accurate claims. Automatic generative script creation without API key/GPU is **not** implied by the existing code.
3. Set up **three persistent, consented fictional characters**, with separate portraits, crop calibration, voice profiles, camera panels. Built-in image generation is aspirational, not implemented. External portrait creation + import is acceptable at the initial milestone if disclosed.
4. Assign each character a **distinguishable** voice; preview a line and adjust speed, pause and pronunciation. Permit manual audio upload. Distinct pitch/rate of the *same* voice does **not** satisfy "three independent voices."
5. Produce dialogue audio; display per-turn duration, the total, and target difference. User can edit/regenerate individual lines; preserve any uploaded audio unless user explicitly replaces it.
6. Preview scenes quickly in low-resolution/static mode; generate neural talking-head clips separately (with limitations/queue/partial failure isolation); then composite the three-person master and speaker close-ups.
7. Preview, adjust, resume failed render, view diagnostics, export 1920x1080 MP4 with synchronized audio and subtitle file, plus an optional short-form cut.

### Non-goals / constraints

- No unconsented impersonation or undisclosed real-person doctor identities.
- No promise of real-time CPU neural video synthesis or unlimited zero-cost network TTS.
- No promise that external AI voice or portrait tools have commercial publishing rights: confirm current provider terms.
- No graphic sexual content required; sample sexual-health conversation must stay educational and evidence-based.
- No public Internet server, cloud account system, or automated YouTube publishing for initial v2.

## 2. Actual baseline findings (verified against repository code)

| ID | Severity | Requirement | Baseline code evidence | Current state |
|---|---|---|---|---|
| G01 | P0 | Topic -> 3-person episode generator | `podcast/project.py` only reads/validates preset/manual script; no generation endpoint | Missing |
| G02 | P0 | 3 truly distinct voice identities | `podcast/settings.py` uses `hi-IN-MadhurNeural` for Aarav and Kabir; Kabir only rate/pitch altered | Missing |
| G03 | P0 | Realistic default lip-sync | `podcast/video.py:render_motion` stretches a fixed mouth region based on audio amplitude; not neural/viseme accurate | Missing in default |
| G04 | P0 | One-click dependable neural workflow | `INSTALL_AI.bat` requires Python 3.8, Git, model downloads and unverified legacy dependencies; `START.bat` doesn't install it | Not ready |
| G05 | P0 | E2E Windows validation | GitHub tests only validate Python project logic and synthetic 0.42s clip; not real TTS, AI model or 10min export | Missing |
| G06 | P1 | Character creation/consistency | `app.py` accepts portrait uploads; `static/index.html` links to external generator | External only |
| G07 | P1 | Native high quality video | `video.py` composites at 960x540, 12 FPS and scales to 1280x720; no 1080p native | Missing |
| G08 | P1 | Accurate subtitles | `scene_image` draws short dialogue snippets in the composition; no word-level timing, SRT, overflow check | Missing |
| G09 | P1 | Real camera direction, shots, idle reactions | `scene_image` uses fixed three-card grid; no director timeline/close-up system | Missing |
| G10 | P1 | Multi-project and backups | `settings.py` uses one `data/project.json`; no project chooser/version history | Missing |
| G11 | P1 | Retry, resume, cancellation | `app.py` has single in-memory job manager; `render` reprocesses turns; no persisted per-turn checkpoints or cancel endpoint | Missing |
| G12 | P1 | Target-duration management | API totals WAV duration but doesn't provide target +/- tolerance or pacing controls | Missing |
| G13 | P1 | Voice selection and pronunciation preview | `SPEAKERS` hardcoded in settings; no user-facing profile editor/voice catalog | Missing |
| G14 | P1 | Replace/remove uploaded voice | `voice.py` reuses uploaded cache at fingerprint WAV path; no explicit `Reset audio` API/UX | Missing |
| G15 | P1 | Reliable reproducible install | `requirements.txt` specifies broad ranges, not tested lockfile; starter may not rediscover Python after winget installation | Risk |
| G16 | P1 | Media validation | Tests don't verify final timing sync, Hindi font coverage, corrupted input, multiple Windows locales, long jobs | Missing |
| G17 | P2 | Music, SFX, transitions, studio branding | FFmpeg scene renderer has no BGM/intro/transition editor | Missing |
| G18 | P2 | Multiple sizes, shorts, thumbnails | MP4 output is one 16:9 fixed layout; no 9:16 export or branding presets | Missing |
| G19 | P2 | Script citations/fact checking for educational claims | sample content is fixed and has fictional character disclaimer; no claims review workflow | Missing |
| G20 | P2 | Publishing compliance | README warns about terms, but app lacks export checklist for consent, model/service license, AI disclosure | Partial |

**Critical wording:** A successful CI matrix means the tested cases passed; it does **not** mean "end-to-end one click neural podcast verified." The baseline's three-pane CPU mouth deformation must not be labeled a realistic lip-sync result.

## 3. Architecture for the next iteration

- **Project store**: `data/projects/<project-id>/project.json`, versioned schema, project-specific `portraits/`, `audio/`, `generated/`, `exports/`; migration from legacy `data/project.json`.
- **Script service**: provider-independent adapter: paste/import JSON/CSV/TXT; optional LLM-backed generator only if configured; validation of speaker distribution, word count, sections, and content notes.
- **Voice service**: configurable 3 character profiles with unique actual voice IDs or uploaded voice; WAV conversion; caching keyed by text, voice settings and engine version; individual preview, explicit replace/delete, failures per line.
- **Render engine**: FFmpeg scene compositor + selectable active speaker shot; static/low-cost draft mode and separate neural backend plugin; optional batch checkpoints per turn, diagnostics and resume.
- **Neural adapter**: explicit install check + executable model smoke test, CPU time measurement, configurable backend per clip; never mark ready based on presence of checkpoint files alone.
- **Editor**: timeline with shot selection, subtitle editing, pause durations, per-turn voice/lip-sync status, download previews and full project backup.
- **Health/security**: loopback-only by default; validated upload sizes/extensions; no remote admin; avoid exposing private project files unintentionally.

## 4. Delivery phases and testable acceptance criteria

### Phase A — Reliability foundations (P0)
- Versioned per-project save, backup/migration and errors visible in UI.
- `START.bat` prerequisite checks, deterministic dependency lock and actionable diagnostics.
- Render a 30-second synthetic scripted 3-voice **uploaded-audio** demo on Windows without an online service.
- Fix or explicitly disable unsuitable CPU mouth deformation; label quality accurately.
- CI across Windows Python 3.11/3.12 checks API routes, real 30-sec FFmpeg render, audio timing and project save/reload. At least one manual Windows-install test required before claiming one-click.

### Phase B — Authoring and audio (P0/P1)
- Import/generate valid 3-speaker script and preserve edits across tab switches.
- User chooses three actual distinguishable voices or provides clips; per-line preview, retry and replacement.
- Duration target shows spoken time + pauses; target 10 min can be reached via editable pacing, not false auto-promise.
- Export AAC audio master + SRT and offer pronunciation guide.

### Phase C — Visual direction (P1)
- Three consistent portrait panels, calibrated crop; consistent studio art.
- Scene presets: three-shot, active speaker, expert close-up, split-screen; automated basic shot timeline with manual overrides.
- Native 1080p 24/25 FPS FFmpeg export; readable Devanagari font and subtitle safe-area tested.
- Optional logo, intro/outro and licensed BGM.

### Phase D — Genuine neural lip-sync (P0 goal, hardware-dependent)
- Installer pins models, Python versions and expected hashes; validates model loading and real 5-second inference.
- One talking character at a time with cached/resumable clips; background characters may remain static. This is NOT real-time three-person full-body animation.
- Surface CPU render benchmark and explicit predicted effort; let user choose hybrid production rather than silently presenting visual mouth warp as neural lip-sync.
- Manual end-to-end 10min representative render validated on a named low-end CPU, or disclose not yet validated.

### Phase E — Quality and shipping (P1/P2)
- Automated visual/audio QC for black frames, clipped speech, blank subtitles, out-of-range text, ffprobe duration/dimensions.
- Final export checklist: AI-generated actors, fictional medical roles, consent for real likeness, voice/image/provider license review and informative sexual-health framing.
- Create release build / installer only once minimum acceptance criteria pass.

## 5. Release gates

`ALPHA`: frontend + CPU static/motion draft works, clearly labeled.

`BETA`: three user-chosen distinguishable voice tracks, multiple projects, reliable edit/preview, 1080p, subtitles, 30s Windows verified test.

`NEURAL BETA`: reliable install and verified neural inference at 5s on actual CPU hardware; resumable per-clip render.

`PRODUCTION`: manual 10min end-to-end run using fresh clone on target Windows hardware; verify portrait consistency, Hindi voice intelligibility, timing, audio-video sync, captions, final MP4 quality, failure recovery and publication rights.

**Current repository:** ALPHA foundation only. Do not describe it as a completed one-click realistic neural podcast production studio.
