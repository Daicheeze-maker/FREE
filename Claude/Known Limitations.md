---
tags: [clipforge, limitations]
---
# Known limitations

Back to [[Home]] · Practical fixes: [[TROUBLESHOOTING]]

Stated plainly so nothing is oversold.

## Not verified in the build environment
- **Windows.** All code paths account for Windows (paths, no console windows, `%LOCALAPPDATA%`, Explorer reveal, AMF detection), but everything ran on Linux. First run on Windows may surface issues.
- **AMD GPU paths.** Hardware encoding (AMF) is detected with a real test encode and is off by default. The llama.cpp Vulkan vision model setup is documented but untested here.
- **YouTube import.** YouTube was blocked by the build network; only validation and error handling were exercised.
- **faster-whisper models** (word-level timing). Hugging Face was blocked; the integration is written but not run.
- **Tagalog/Taglish recognition quality.** Depends on the Whisper size; *small* or *medium* is recommended. Not measured.

## Not implemented
- **Speaker identification (diarization).** Speaker labels can be typed per caption, and the Podcast preset shows them, but speakers are not detected automatically. sherpa-onnx has a diarization model that could be added later.
- **OCR as a separate model.** On-screen text is read only by the optional vision-language model (it reports `on_screen_text` per frame). There is no standalone OCR engine.
- **Pause/resume** pauses between processing steps; a single long FFmpeg step (such as a render) finishes before the pause applies. Cancel is immediate.
- **Hardware usage display** shows CPU, RAM and the app's own memory. GPU memory and utilization are not shown (no reliable cross-vendor API); use Task Manager.
- The **installer** does not bundle FFmpeg.

## By design
- Scores estimate content interest from detected signals. They do not predict virality.
- With sherpa-onnx Whisper, word highlight times inside a caption are **estimated**; the UI says so.
- Cloud AI is blocked unless you explicitly allow it.
