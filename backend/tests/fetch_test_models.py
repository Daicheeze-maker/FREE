"""Download the small real models used by the test suite (~150 MB) into backend/tests/models.

    python backend/tests/fetch_test_models.py
"""
from __future__ import annotations

import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clipforge.ai.catalog import BY_ID  # noqa: E402

DEST = Path(__file__).parent / "models"
WANTED = {"whisper-tiny": None, "ced-tiny": None, "silero-vad": "silero_vad.onnx", "yunet-face": "yunet.onnx"}

if __name__ == "__main__":
    DEST.mkdir(exist_ok=True)
    for mid, rename in WANTED.items():
        url = BY_ID[mid]["url"]
        name = url.rsplit("/", 1)[1]
        target = DEST / (rename or BY_ID[mid]["archive_dir"])
        if target.exists():
            print("have", target.name)
            continue
        print("downloading", url)
        tmp = DEST / name
        urllib.request.urlretrieve(url, tmp)
        if name.endswith(".tar.bz2"):
            with tarfile.open(tmp) as tf:
                tf.extractall(DEST, filter="data")
            tmp.unlink()
        else:
            tmp.rename(target)
    print("done:", DEST)
