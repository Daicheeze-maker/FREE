---
tags: [clipforge, models, amd]
---
# Model setup

Back to [[Home]] · See also [[How Clip Selection Works]]

ClipForge never downloads a model by itself. Each model shows its size, RAM estimate, runtime and license, and downloads only when you press **Download** (first-run setup, or Settings → AI models). Downloads can be paused and resumed. **Verify** loads the model and runs a test inference.

## Recommended starting set (~670 MB)

| Model | Purpose | Download | RAM (est.) | License |
|---|---|---|---|---|
| Whisper small (ONNX) | Speech recognition + language detection | 639 MB | ~1.6 GB | MIT |
| CED-tiny | Audio events: laughter, screams, cheering, music, impacts (527 classes) | 29 MB | ~0.3 GB | Apache-2.0 |
| Silero VAD | Finds where speech starts and stops | 0.6 MB | ~0.05 GB | MIT |
| YuNet | Face detection for face tracking and reframing | 0.2 MB | ~0.05 GB | MIT |

All four run on the **CPU** through ONNX Runtime/OpenCV. No CUDA or GPU is needed. On a Ryzen 5 7500F, CPU inference is the stable choice; see [[#Why speech runs on the CPU]].

## Choosing a speech model

| Model | Good for | Timing |
|---|---|---|
| Whisper tiny / base | Quick tests, clear English | sentence-level* |
| **Whisper small** | Best balance on a 6-core CPU; usable Tagalog/Taglish | sentence-level* |
| Whisper medium | Noticeably better Tagalog/Taglish; considerably slower than small | sentence-level* |
| Whisper turbo (large-v3-turbo) | Near-large accuracy | sentence-level* |
| faster-whisper small / medium / large-v3-turbo | **True word-level timestamps** for word-by-word captions | word-level |

\* The sherpa-onnx Whisper exports give timing per speech chunk (VAD splits audio into chunks of at most 14 s at real pauses). Word highlight timing inside a caption is then **estimated**, and the app says so in the editor. For exact word-by-word captions, use a faster-whisper model. Those download from Hugging Face, and the download progress is not shown while it runs.

**Language:** leave it on *Detect automatically*, or pick *Filipino / Tagalog / Taglish* for Taglish videos so short chunks are not misdetected. Captions keep the original language; nothing is translated.

## Optional: vision-language and context model

Adds frame descriptions (facial expressions, on-screen text, gameplay events) and a conversation-level judgement of which moments are self-contained. Without it, ClipForge still selects clips from audio, motion, face and transcript signals.

ClipForge does not run this model itself. It talks to a local **OpenAI-compatible server** you run. This keeps big GPU models out of the Python process and lets you pick the runtime that works on your GPU.

### AMD Radeon RX 9060 XT (16 GB): llama.cpp with Vulkan

Vulkan works on all current AMD drivers on Windows; it does not need ROCm or CUDA.

1. Download a **Vulkan** build of llama.cpp for Windows (`llama-*-bin-win-vulkan-x64.zip`) from the llama.cpp GitHub releases page and unzip it.
2. Download a vision model in GGUF format with its projector file (`mmproj`), for example **Qwen2.5-VL-7B-Instruct, Q4_K_M** (about 4.7 GB model + 1.3 GB projector, fits in 16 GB VRAM with room for context).
3. Start the server:
   ```powershell
   llama-server.exe -m Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf --mmproj mmproj-Qwen2.5-VL-7B-Instruct-f16.gguf -ngl 99 -c 8192 --port 8080
   ```
   `-ngl 99` puts all layers on the GPU. Check the startup log mentions your Radeon card via Vulkan.
4. In ClipForge: **Settings → AI models → Vision-language & context model**: turn it on, address `http://127.0.0.1:8080/v1`, keep "Model accepts images" on, then **Save and test connection**.

Alternatives: **LM Studio** (Vulkan runtime on AMD; Developer tab → start server, address `http://127.0.0.1:1234/v1`) or **Ollama** (`http://127.0.0.1:11434/v1`, model name e.g. `qwen2.5vl:7b`). Text-only models work too: turn off "Model accepts images" and only the transcript-context pass runs.

> [!warning] Verify on your machine
> Exact file names, model availability and VRAM use change between releases. Check the llama.cpp and model pages before downloading. This setup was **not** tested in the build environment (no GPU was available there). The ClipForge side (the requests, JSON parsing, fallback when the server is missing) is covered by tests.

**How much it is used:** the *Analysis intensity* profile limits how many frames go to the vision model (12 / 30 / 80 for Performance / Balanced / Quality). Frames are chosen around already-detected events plus one per scene, not every frame.

**Privacy:** addresses on this PC or your home network are allowed. Any other address is refused unless you switch on **Allow cloud AI** (Settings → Privacy & devices). With that on, sampled frames and transcript text are sent to that service.

## Why speech runs on the CPU

- ONNX Runtime's GPU paths on Windows are DirectML (works with AMD) and CUDA (NVIDIA only). The Python wheels used here ship the CPU provider; DirectML builds of these models are not a tested path, and a half-working GPU path is worse than a reliable CPU one.
- Measured in the build environment: Whisper **tiny** (int8, 4 CPU threads) transcribed 7.25 s of speech in 0.29 s, about 25× faster than real time. Whisper small is several times heavier; on a 6-core Ryzen it is expected to stay faster than real time, but this has not been measured. Time a short video on your PC to see.
- Only one heavy model is loaded at a time: speech → freed → audio tagger → freed. The job queue runs one analysis or export at a time.

## Where models live

`%LOCALAPPDATA%\ClipForge\models\<model-id>\`. Remove a model from Settings, or delete the folder; the app notices.

## Attribution

- OpenAI Whisper (MIT); ONNX exports by the k2-fsa/sherpa-onnx project (Apache-2.0)
- faster-whisper and CTranslate2 conversions by SYSTRAN (MIT)
- CED audio tagging models by Xiaomi (Apache-2.0)
- Silero VAD (MIT)
- YuNet face detector, OpenCV Zoo (MIT)
- Caption fonts Poppins, Anton, Bebas Neue: SIL Open Font License (license files in `backend/clipforge/assets/fonts/`)
