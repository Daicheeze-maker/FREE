---
tags: [clipforge, index]
---
# ClipForge AI

> Your AI watches. Your AI listens. Your AI finds the moments.

ClipForge AI is a local-first desktop studio that turns long videos (streams, podcasts, vlogs, tutorials) into captioned short clips. Your videos stay on your computer.

## Start here
- [[INSTALLATION]]: set it up on Windows (or Linux/macOS for development)
- [[MODEL_SETUP]]: which AI models to download, and the optional vision model on an AMD GPU
- [[User Guide]]: from importing a video to exporting a clip, plus phone access
- [[TROUBLESHOOTING]]: when something does not work

## For developers
- [[DEVELOPMENT_PLAN]]: architecture, milestones, and what is done
- [[How Clip Selection Works]]: the multimodal analysis and scoring, explained
- [[Testing]]: test suite, fixtures, and what was verified by hand
- [[Known Limitations]]: honest list of what is not verified or not supported

## Project facts
| | |
|---|---|
| Version | 0.1.0 |
| Desktop shell | Tauri 2 (Rust) |
| Interface | React 19 + TypeScript + Vite + Tailwind CSS 4 |
| Engine | Python 3.12+, FastAPI, SQLite (SQLAlchemy), FFmpeg |
| Speech | Whisper (ONNX via sherpa-onnx, or faster-whisper), CPU |
| Audio events | CED AudioSet tagger, Silero VAD, CPU |
| Vision | OpenCV + PySceneDetect + YuNet faces; optional local VLM (e.g. Qwen2.5-VL via llama.cpp Vulkan) |
| Data folder | `%LOCALAPPDATA%\ClipForge` (Windows), `~/.clipforge` (Linux/macOS) |
