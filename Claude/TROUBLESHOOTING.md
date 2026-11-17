---
tags: [clipforge, support]
---
# Troubleshooting

Back to [[Home]] · See also [[Known Limitations]]

**First, look at the log:** Settings → Logs shows recent jobs with their errors and the application log (`%LOCALAPPDATA%\ClipForge\logs\clipforge.log`). **Copy** puts it on the clipboard for a bug report.

## Starting
| Symptom | Fix |
|---|---|
| "ClipForge's local engine is not responding" | The console window from `Start ClipForge.bat` must stay open. If it closed with an error, run the .bat again and read the message. |
| "ClipForge is not set up yet" | Run `scripts\setup-windows.ps1` first ([[INSTALLATION]]). |
| PowerShell will not run the setup script | `powershell -ExecutionPolicy Bypass -File scripts\setup-windows.ps1` |
| "Address already in use" / port 8756 busy | Another ClipForge is running (check Task Manager for `python.exe` or `clipforge-engine.exe`), or start on another port: `.venv\Scripts\python.exe -m clipforge.main --port 8760` |
| `pip install` fails building a package | Use Python 3.12 (`py -3.12`). Very new Python versions may not have prebuilt wheels for every package yet. |

## FFmpeg
| Symptom | Fix |
|---|---|
| "FFmpeg was not found" | `winget install Gyan.FFmpeg`, then restart ClipForge. Or Settings → Hardware & processing → FFmpeg path: the `bin` folder or `ffmpeg.exe` itself. |
| Captions are missing from exports but visible in the preview | Your FFmpeg lacks `libass`. Check with `ffmpeg -filters | findstr ass`. The Gyan builds include it. |
| "H.265 was requested but this FFmpeg build has no H.265 encoder" | Pick H.264, or install a full FFmpeg build. |
| Hardware encoding not offered | AMF needs a recent AMD driver and an FFmpeg built with AMF. ClipForge runs a real test encode and only offers what works. Software encoding is the default anyway. |

## Importing
| Symptom | Fix |
|---|---|
| "could not be read as a video" | The file is damaged or incomplete (e.g. a stream recording that was cut off). Try remuxing: `ffmpeg -i in.mkv -c copy out.mp4`. |
| Preview is black or does not play | For MKV/HEVC/10-bit files a preview copy is created first; wait for "Creating a preview copy" to finish. |
| "This video has already been imported" | It opens the existing project. Delete that project in the Library to import fresh. |
| YouTube: "Could not reach YouTube" | Check the internet connection, VPN or firewall. Local import still works. |
| YouTube: unavailable / private / sign-in | ClipForge does not log in or bypass restrictions. Download the video yourself if you own it, then import the file. |
| YouTube imports broke after working before | YouTube changes often. Update yt-dlp: `backend\.venv\Scripts\python.exe -m pip install -U yt-dlp` |

## Analysis
| Symptom | Fix |
|---|---|
| "No speech recognition model is installed" | Settings → AI models → download a Whisper model, then **Resume** the analysis (finished stages are kept). |
| Transcript has the wrong language or gibberish | Set the spoken language explicitly in Analysis settings (e.g. Filipino/Tagalog), and use Whisper small or medium. |
| Words in Taglish are wrong | Use Whisper medium or a faster-whisper model; edit captions in the editor's *Captions* tab. |
| "No interesting moments were found" | The audio/visual signals were flat. Lower the shortest clip length, use *Custom AI search*, enable the vision model, or make a *Manual clip*. |
| Warnings like "audio tagging model is not installed" | Install CED-tiny for laughter/scream/cheer detection, and Silero VAD for cleaner speech splitting. |
| Analysis is slow | Settings → Hardware: *Performance* profile; smaller Whisper; leave CPU threads at 0 (auto). Close other heavy apps. |
| "Not enough disk space" | Analysis needs roughly 115 MB per hour of audio (temporary), plus exports. Free space, or Settings → Storage → *Delete temporary files now*. |
| A job says *interrupted* | The app closed mid-job. Press **Resume/Retry**. |
| Vision model: "Could not reach the local AI server" | Start `llama-server` / LM Studio / Ollama first, check the address and port, then **Save and test connection**. |
| Vision model: "did not return valid JSON" | Use an instruction-tuned model (e.g. Qwen2.5-VL Instruct). Very small models may not follow the format; analysis continues without the model in that case. |

## Exporting
| Symptom | Fix |
|---|---|
| "failed validation" | The report lists which check failed (duration, streams, decode). Usually a damaged section in the source. Try trimming a little, or remux the source. |
| "The background music file no longer exists" | Remove it in the Audio tab and add it again. |
| Can't find the file | Library → Exported clips → *Show in folder*, or Settings → Storage for the export folder. |

## Phone
| Symptom | Fix |
|---|---|
| Page does not open on the phone | 1) Phone access on and ClipForge restarted; 2) same Wi-Fi; 3) Windows Firewall: allow Python / ClipForge on **Private** networks; 4) use the IP shown in Settings, not `localhost`. |
| "Phone access is turned off" | Turn it on in Settings → Privacy & devices on the PC. |
| PIN rejected | Use the current PIN shown on the PC. |

## Starting over
Close ClipForge and delete (or rename) `%LOCALAPPDATA%\ClipForge`. Your original videos are not stored there, but uploads, YouTube imports, models and default exports are.
