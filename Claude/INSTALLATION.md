---
tags: [clipforge, setup]
---
# Installation

Back to [[Home]] · Next: [[MODEL_SETUP]]

There are three ways to run ClipForge. Most people want option A.

## A. Windows: run from the source folder (recommended today)

Works on Windows 10/11, including the target machine (Ryzen 5 7500F, Radeon RX 9060 XT, 16 GB RAM). No NVIDIA GPU and no Rust are needed.

1. **Get the code.** On GitHub, open the repository, switch to the branch, choose **Code → Download ZIP**, and unzip it, for example to `C:\ClipForge`. (Or `git clone` it.)
2. **Run the setup once.** In the folder, right-click `scripts\setup-windows.ps1` → **Run with PowerShell**.
   It installs, using `winget` where missing:
   - Python 3.12
   - Node.js LTS
   - FFmpeg (the Gyan.FFmpeg build, which includes `libass` for burned-in captions and AMD AMF encoders)

   Then it creates `backend\.venv`, installs the Python packages from `backend\requirements.txt`, and builds the interface.
   If it says a tool "is not on PATH yet", close the window and run it again.
3. **Start ClipForge.** Double-click **`Start ClipForge.bat`**. A console window runs the engine, and your browser opens `http://127.0.0.1:8756`. Keep the console open while you work; close it to quit.
4. **First-run setup** walks you through the environment check and the model download. See [[MODEL_SETUP]].

> [!note] If PowerShell refuses to run the script
> Open PowerShell in the folder and run
> `powershell -ExecutionPolicy Bypass -File scripts\setup-windows.ps1`

## B. Windows: build the desktop app (installer)

This produces `ClipForge AI_0.1.0_x64-setup.exe`, a normal desktop app with its own window that starts and stops the engine for you.

Extra prerequisites:
- Rust: `winget install Rustlang.Rustup`
- Visual Studio Build Tools with **Desktop development with C++**: `winget install Microsoft.VisualStudio.2022.BuildTools` (then tick that workload)
- WebView2: already part of Windows 11

Then, after option A's setup:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```
The installer appears in `src-tauri\target\release\bundle\nsis\`. It contains the packaged engine (PyInstaller) and the interface. FFmpeg is **not** bundled; it is found on PATH or set in Settings → Hardware & processing.

> [!warning] Not yet built on Windows
> The installer build was verified on Linux (the desktop app and the packaged engine both run there), but it has not been built on Windows yet. If it fails, use option A and report the error, see [[TROUBLESHOOTING]].

## C. Development (Windows, Linux or macOS)

```bash
scripts/setup-dev.sh            # Linux/macOS; on Windows use setup-windows.ps1
cd backend && .venv/bin/python -m clipforge.main      # engine + built UI on :8756
cd frontend && npm run dev       # optional: hot-reload UI on :5173 (proxies /api to :8756)
npm install && npm run desktop:dev   # optional: the Tauri window, from the repo root
```

Run the tests: see [[Testing]].

## Using it from your phone

ClipForge can be opened from a phone's browser on the same Wi-Fi. The PC still does all the work. See [[User Guide#Phone access]].

## Where things are stored

| What | Where |
|---|---|
| Database, projects, models, logs | `%LOCALAPPDATA%\ClipForge` (override with the `CLIPFORGE_DATA` environment variable) |
| Exported clips | `%LOCALAPPDATA%\ClipForge\exports\<project>` by default; change it in Settings → Storage |
| Imported videos | Used where they are. Only uploads and YouTube imports are copied into the data folder. |

## Updating

Download or pull the new code, then run `scripts\setup-windows.ps1` again. Your data folder is not touched.
