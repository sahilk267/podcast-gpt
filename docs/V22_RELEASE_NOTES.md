# Podcast GPT V2.2 Alpha — Voice Discovery, Timed Subtitles, Offline Preflight

This is an **incremental V2 alpha**, not a verified 10-minute three-person neural video generator. Intended for Windows 10/11 without a dedicated GPU; the basic audio/video compositor also runs on Linux. The optional SadTalker CPU backend remains experimental.

## What's new

- **Live Indian voice catalog**: Characters → **Check live Hindi voices** fetches actual voices currently returned by the unofficial Edge-TTS endpoint. It separates Hindi and English-India voices. Do not assume the full Microsoft Azure Speech catalog is available through this unofficial route. If the catalog fails, existing voice settings/custom audio remain usable.
- **3 independent Hindi voice IDs, conditionally**: If the live catalog returns at least two distinct Hindi male voices and one Hindi female voice, **Assign 3 different Hindi voices** selects distinct IDs for Aarav, Meera, Kabir. It changes only in-browser selections until you save. You must audition a spoken sample from each; a voice ID is not a quality guarantee. If the service returns fewer voices, use uploaded third-party/recorded audio with appropriate permission.
- **Word-timed SRT where available**: Newly synthesized Edge-TTS lines request `WordBoundary` metadata (100-nanosecond ticks) and store a sidecar `.words.json`, with per-word timestamps. SRT groups actual word timestamps into readable captions. For imported/custom audio, or older audio that lacks metadata, subtitles continue to use approximate proportional timing. Timed captions do **not** mean face lip-sync is phoneme-accurate.
- **Episode readiness check**: Produce → **Check episode readiness** reports missing audio, portrait coverage, duplicate voice IDs, word timing coverage and known limitations.
- **Offline-only export**: Check **Offline-only export** when all WAV takes are prepared. If any audio is missing, render refuses to call online TTS and displays a clear error. Useful when your computer is offline or the TTS endpoint is unavailable.
- **Reproducible tests**: Mocked Edge TTS catalog/metadata tests, word timing unit tests, offline preflight rejection and an offline FFmpeg/MP4/SRT end-to-end test. GitHub Actions runs Windows + Ubuntu CI and browser JavaScript syntax check.

## What is not implemented or validated

- Full offline Hindi TTS, third-party commercial rights, model-backed script generation or integrated portrait generation.
- Actual availability/quality of every newly listed voice on *your* network; the live catalog must be checked at runtime.
- Word timing for custom-uploaded audio (requires alignment engine), burned-in captions or text-based media editing timeline.
- Guaranteed one-click installation on all CPU Windows hardware, photorealistic default lip-sync, automatic gestures, or tested 10-minute SadTalker neural inference. The default mouth-motion effect is approximate visual deformation.
- Real-time multi-person neural video generation; composited speaker shots still use static photos for silent guests.

## How to test after updating

1. **Back up `data/`** then `git pull origin main` and run `START.bat`.
2. Open an episode, go to Characters → **Check live Hindi voices** → **Assign 3 different Hindi voices** (only if supported). **Save episode.**
3. In Voices, use Generate on one short line per character; preview all three. If a voice fails, select another verified voice or upload audio clips.
4. In Produce, click **Check episode readiness**. Generate/upload any missing audio, then enable **Offline-only export**.
5. Render a **short** 720p static episode first; download MP4 + SRT. Verify audio durations, Devanagari font, and word timestamps where available. Try 1080p only after the short test passes.
6. For CPU neural lip-sync, separately test **one 5-second** SadTalker inference before longer renders. Its installer and CPU performance have not been certified.

## Implementation and source references

- [`podcast/voice.py`](../podcast/voice.py): voice catalog, metadata and cache handling.
- [`podcast/subtitles.py`](../podcast/subtitles.py): word timing and estimated fallback.
- [`podcast/app.py`](../podcast/app.py): readiness and render integration.
- [Microsoft Azure language/voice availability](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support) is informational only; it is **not** an inventory of the unofficial Edge endpoint.
- [edge-tts](https://github.com/rany2/edge-tts) provides `list_voices()`, `Communicate(..., boundary='WordBoundary')` and metadata on `save(audio, metadata)`; its unofficial service availability can change.

**Publishing:** Verify voices/images/music licenses, fictional identity disclosures and medical accuracy independently. Do not misrepresent fictional experts as licensed doctors.
