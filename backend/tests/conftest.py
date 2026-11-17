"""Shared fixtures.

Tests that need AI models use small real models (Whisper tiny, CED-tiny, Silero VAD, YuNet).
Point CLIPFORGE_TEST_MODELS at a folder prepared by `python backend/tests/fetch_test_models.py`.
Without it, model-dependent tests are skipped — they are never faked.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
MODELS_SRC = Path(os.environ.get("CLIPFORGE_TEST_MODELS", Path(__file__).parent / "models"))
MODEL_FILES = {
    "whisper-tiny": "sherpa-onnx-whisper-tiny",
    "ced-tiny": "sherpa-onnx-ced-tiny-audio-tagging-2024-04-19",
    "silero-vad": "silero_vad.onnx",
    "yunet-face": "yunet.onnx",
}


def models_available() -> bool:
    return all((MODELS_SRC / f).exists() for f in MODEL_FILES.values())


needs_models = pytest.mark.skipif(not models_available(),
                                  reason="test models not downloaded (run tests/fetch_test_models.py)")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    if not (FIXTURES / "speech_scene.mp4").exists():
        from make_fixture import make

        make(FIXTURES)
    return FIXTURES


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """A fresh, isolated data directory + database for each test."""
    from clipforge import config, db, settings

    config.set_data_dir(tmp_path / "data")
    db.init_db()
    settings.ensure_secrets()
    yield tmp_path / "data"
    from clipforge.jobs.manager import manager

    manager.stop()
    time.sleep(0.1)


def install_models() -> None:
    from clipforge.config import paths
    from clipforge.db import session
    from clipforge.models import AIModel

    for mid, name in MODEL_FILES.items():
        d = paths.models / mid
        d.mkdir(parents=True, exist_ok=True)
        dst = d / name
        if not dst.exists():
            try:
                os.symlink(MODELS_SRC / name, dst)
            except OSError:  # Windows without symlink rights
                (shutil.copytree if (MODELS_SRC / name).is_dir() else shutil.copy)(MODELS_SRC / name, dst)
        with session() as s:
            s.merge(AIModel(id=mid, status="installed", path=str(d)))


@pytest.fixture()
def client(data_dir):
    """API client that looks like a browser on this computer (so it is signed in automatically)."""
    from fastapi.testclient import TestClient

    from clipforge.main import create_app

    with TestClient(create_app(), client=("127.0.0.1", 50000)) as c:
        assert c.get("/api/session").json()["authenticated"]
        yield c


def wait_job(client, job_id: str, timeout: float = 300) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("completed", "failed", "cancelled", "interrupted"):
            return j
        time.sleep(0.2)
    raise TimeoutError(f"job {job_id} did not finish")
