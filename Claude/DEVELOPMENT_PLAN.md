---
tags: [clipforge, architecture, plan]
---
# Development plan

Back to [[Home]] · Details: [[How Clip Selection Works]] · [[Testing]] · [[Known Limitations]]

## Environment found at the start
Empty repository (only skill files). Build machine: Linux, Python 3.13, Node 22, Cargo 1.97, FFmpeg 6.1 (with libass, flite, libx264/265), 4 CPU threads, 15 GB RAM, no GPU. Hugging Face, YouTube and the OpenAI CDN were blocked by the network policy; GitHub release downloads worked. So sherpa-onnx (models on GitHub releases) became the default speech runtime, with faster-whisper as an alternative.

Target machine: Windows 11, Ryzen 5 7500F, Radeon RX 9060 XT 16 GB, 16 GB RAM.

## Key decisions
| Decision | Why |
|---|---|
| Python engine as a local HTTP server; UI is a web app; Tauri window loads it | One UI serves the desktop **and** the phone browser. The engine stays a normal Python process (easy model management). |
| All bundled models on CPU (ONNX Runtime, OpenCV) | No CUDA dependency; AMD-safe; predictable. ONNX models stay small enough for 16 GB RAM. |
| Vision-language model via a user-run OpenAI-compatible server | GPU runtimes for AMD on Windows (llama.cpp Vulkan, LM Studio) are best run as their own process; ClipForge stays small and replaceable. |
| Replaceable providers | `ai/asr.py` (sherpa Whisper / faster-whisper), `ai/llm.py` (any OpenAI-compatible server), a model catalog with verify/select. |
| One heavy job at a time | A single worker runs analysis/export; models are freed between stages. Downloads run on their own threads. |
| Captions stored in source time | Trimming can never desync captions; converted to clip time only when rendering. |
| Same crop plan for preview and render | The editor shows what the export produces. |
| Validate before delivering | A render goes to a temp folder, is probed and fully decoded, then moved to the output folder. |
| Security | Binds to 127.0.0.1 by default; session cookie; Origin/Host checks (blocks CSRF and DNS rebinding); phone access is opt-in with a PIN; API keys never sent to the UI; only database-registered files are served. |

## Structure
```
backend/clipforge/
  main.py            app, access control, static UI
  config.py db.py models.py settings.py logging_setup.py errors.py hardware.py
  api/               system, projects, clips, media routes
  jobs/manager.py    queue, measured progress, pause/cancel, recovery
  media/ffmpeg.py    probe, run with progress, frames, encoders
  audio/             extraction, loudness/spikes/pauses, VAD, AudioSet tagger
  ai/                catalog, model manager, ASR providers, local LLM client
  analysis/          visual, speech events, context (LLM), clip engine, pipeline
  captions/engine.py cues, styles, SRT/VTT/ASS
  export/            reframing, FFmpeg render, validation, export job
  importing/         local + upload, YouTube (yt-dlp)
backend/tests/       fixtures, unit + end-to-end tests
frontend/src/        React app: pages, components (design system, editor), hooks, lib
src-tauri/           desktop shell (starts/stops the engine)
scripts/             Windows setup, launcher, installer build; dev setup
Claude/              this Obsidian vault (documentation)
```

## Database (SQLite, WAL)
projects · source_videos (fingerprint unique: no duplicates) · jobs · transcripts · speakers · transcript_segments (words JSON) · scenes · detected_events · clip_candidates · generated_clips (all editor state) · caption_tracks · caption_styles · export_jobs (validation report) · ai_models · app_settings. Media files stay on disk.

## Milestones
| # | Milestone | Status |
|---|---|---|
| 1 | Foundation: app, design system, navigation, DB, logging, settings | ✅ |
| 2 | Video importing: local/upload/path, metadata, thumbnails, persistence, preview proxy | ✅ |
| 3 | Audio AI: transcription, language detection, audio events, transcript storage | ✅ (diarization not implemented) |
| 4 | Visual analysis: scenes, frames, faces, motion; optional VLM frame descriptions | ✅ (VLM untested on GPU) |
| 5 | Clip detection: context windows, fusion, scoring, ranking, boundaries | ✅ |
| 6 | Clip generation: candidates, thumbnails, storage | ✅ |
| 7 | Captions: presets, styling, editing, SRT/VTT, burn-in | ✅ |
| 8 | Editor: preview, timeline, trim, aspect, crop, audio, music | ✅ |
| 9 | Export: presets, FFmpeg render, validation, output management | ✅ |
| 10 | Polish: loading/error states, workflow tests, restart recovery, docs, desktop shell | ✅ on Linux; Windows build not yet run |

## Next steps
1. Run `scripts\setup-windows.ps1` on the target PC and go through the [[User Guide]] once; fix anything Windows-specific.
2. Build the installer on Windows (`scripts\build-windows.ps1`).
3. Try the Vulkan llama.cpp vision model on the RX 9060 XT and tune the frame budget.
4. Add speaker diarization (sherpa-onnx offline diarization) for automatic Podcast speaker labels.
5. Measure Whisper small vs medium speed and accuracy on real Tagalog/Taglish clips.
