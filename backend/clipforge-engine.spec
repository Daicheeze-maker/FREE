# PyInstaller spec for the standalone engine used by the desktop installer.
#   cd backend && pyinstaller clipforge-engine.spec --distpath ../backend-dist --noconfirm
# Output: backend-dist/clipforge-engine/clipforge-engine(.exe) plus its _internal folder.
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = [("clipforge/assets", "clipforge/assets"), ("../frontend/dist", "ui")]
binaries, hidden = [], ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
                        "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on"]
for pkg in ("sherpa_onnx", "scenedetect", "faster_whisper", "ctranslate2", "yt_dlp"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    except Exception:
        pass
datas += collect_data_files("cv2")

a = Analysis(["engine_entry.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "matplotlib", "IPython"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="clipforge-engine", console=False,
          icon="../src-tauri/icons/icon.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="clipforge-engine")
