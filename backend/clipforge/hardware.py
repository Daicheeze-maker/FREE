"""Hardware and acceleration detection. Every probe is best-effort and never raises."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys

from .media import ffmpeg as ff

_cache: dict | None = None


def _run(cmd: list[str], timeout: int = 15) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              creationflags=ff.NO_WINDOW).stdout
    except Exception:  # noqa: BLE001
        return ""


def _gpus() -> list[dict]:
    gpus: list[dict] = []
    if sys.platform == "win32":
        out = _run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json"])
        try:
            data = json.loads(out) if out.strip() else []
            for g in data if isinstance(data, list) else [data]:
                # AdapterRAM is a 32-bit field and under-reports cards above 4 GB, so it is not shown as VRAM.
                gpus.append({"name": g.get("Name"), "driver": g.get("DriverVersion")})
        except ValueError:
            pass
    elif sys.platform == "darwin":
        for line in _run(["system_profiler", "SPDisplaysDataType"]).splitlines():
            if "Chipset Model" in line:
                gpus.append({"name": line.split(":", 1)[1].strip()})
    else:
        for line in _run(["lspci"]).splitlines():
            if any(k in line for k in ("VGA", "3D controller", "Display controller")):
                gpus.append({"name": line.split(":", 2)[-1].strip()})
    for g in gpus:
        n = (g.get("name") or "").lower()
        g["vendor"] = ("amd" if any(k in n for k in ("amd", "radeon")) else
                       "nvidia" if any(k in n for k in ("nvidia", "geforce")) else
                       "intel" if "intel" in n else "other")
    return gpus


def detect(refresh: bool = False) -> dict:
    global _cache
    if _cache is not None and not refresh:
        return {**_cache, "memory": _memory()}
    gpus = _gpus()
    ort_providers: list[str] = []
    try:
        import onnxruntime as ort

        ort_providers = list(ort.get_available_providers())
    except Exception:  # noqa: BLE001
        pass
    encoders = {}
    try:
        for name in ("libx264", "libx265", "h264_amf", "hevc_amf", "h264_nvenc", "hevc_nvenc", "h264_qsv", "hevc_qsv"):
            software = name.startswith("lib")
            encoders[name] = ff.has_encoder(name) if software else ff.encoder_works(name)
    except Exception:  # noqa: BLE001
        pass
    vendors = {g["vendor"] for g in gpus}
    notes = []
    if "amd" in vendors:
        notes.append("AMD GPU detected. CUDA is not used. Speech and audio models run on the CPU; "
                     "the optional vision/language model runs on the GPU through a Vulkan build of llama.cpp. "
                     "Video encoding uses AMF when the installed FFmpeg supports it.")
    if not gpus:
        notes.append("No GPU detected. Everything runs on the CPU.")
    _cache = {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor() or platform.machine(),
        "cpu_threads": os.cpu_count() or 1,
        "gpus": gpus,
        "onnxruntime_providers": ort_providers,
        "directml": "DmlExecutionProvider" in ort_providers,
        "cuda": "CUDAExecutionProvider" in ort_providers,
        "vulkan_tools": bool(shutil.which("vulkaninfo")),
        "encoders": encoders,
        "hardware_encoder": next((e for e in ("h264_amf", "h264_nvenc", "h264_qsv") if encoders.get(e)), None),
        "notes": notes,
    }
    return {**_cache, "memory": _memory()}


def _memory() -> dict:
    try:
        import psutil

        vm = psutil.virtual_memory()
        return {"total_gb": round(vm.total / 2**30, 1), "available_gb": round(vm.available / 2**30, 1),
                "process_gb": round(psutil.Process().memory_info().rss / 2**30, 2),
                "cpu_percent": psutil.cpu_percent(interval=None)}
    except Exception:  # noqa: BLE001
        return {}


def disk(path) -> dict:
    try:
        u = shutil.disk_usage(path)
        return {"total_gb": round(u.total / 2**30, 1), "free_gb": round(u.free / 2**30, 1)}
    except Exception:  # noqa: BLE001
        return {}


def threads() -> int:
    from . import settings

    n = int(settings.get("cpu_threads") or 0)
    return n if n > 0 else max(1, min(8, (os.cpu_count() or 2) - 1))
