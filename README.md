# ClipForge AI

**Your AI watches. Your AI listens. Your AI finds the moments.**

A local-first AI video clipping studio. Import a long video (stream, podcast, vlog, tutorial). ClipForge transcribes it, listens for laughter and reactions, watches for scene changes, faces and sudden action, and suggests complete, explainable short clips. Then you edit captions, crop to vertical, trim, and export validated MP4s. It works with English, Filipino/Tagalog and Taglish, runs on the CPU (no NVIDIA GPU needed), and can be used from your phone over home Wi-Fi.

Everything runs on your computer. Nothing is uploaded unless you explicitly enable a cloud AI service.

## Quick start (Windows)
1. Download the repository (Code → Download ZIP) and unzip it.
2. Right-click `scripts\setup-windows.ps1` → **Run with PowerShell** (installs Python, Node.js and FFmpeg if missing).
3. Double-click **ClipForge AI** on your Desktop (the setup creates it). It opens in its own window; close the window to quit. The first screen helps you download the AI models (~670 MB).

## Documentation
The docs are an **Obsidian vault named `Claude`** in the [`Claude/`](Claude/) folder. Open that folder as a vault in Obsidian, or read the files on GitHub:

- [Home](Claude/Home.md)
- [INSTALLATION](Claude/INSTALLATION.md): Windows setup, desktop installer build, development
- [MODEL_SETUP](Claude/MODEL_SETUP.md): models, licenses, and the optional vision model on AMD GPUs (llama.cpp Vulkan)
- [User Guide](Claude/User%20Guide.md): import → analyze → review → edit → export, phone access
- [TROUBLESHOOTING](Claude/TROUBLESHOOTING.md)
- [DEVELOPMENT_PLAN](Claude/DEVELOPMENT_PLAN.md): architecture and milestones
- [How Clip Selection Works](Claude/How%20Clip%20Selection%20Works.md)
- [Testing](Claude/Testing.md) · [Known Limitations](Claude/Known%20Limitations.md)

## Stack
Tauri 2 · React 19 + TypeScript + Vite + Tailwind CSS 4 · Python · FastAPI · SQLite/SQLAlchemy · FFmpeg · PySceneDetect · OpenCV · Whisper (sherpa-onnx / faster-whisper) · CED audio tagging · Silero VAD · YuNet · optional local vision-language model through any OpenAI-compatible server.

## Development
```bash
scripts/setup-dev.sh                                   # or scripts\setup-windows.ps1
cd backend && .venv/bin/python -m clipforge.main       # http://127.0.0.1:8756
cd backend && python tests/fetch_test_models.py && python -m pytest
```

## License notes
Bundled caption fonts are under the SIL Open Font License. AI models are downloaded separately under their own licenses (listed in the app and in MODEL_SETUP).
