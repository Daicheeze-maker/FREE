"""End-to-end tests through the HTTP API with real (small) models and real FFmpeg renders."""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import pytest
from conftest import install_models, needs_models, wait_job


def _import(client, path) -> dict:
    r = client.post("/api/import/path", json={"path": str(path)})
    assert r.status_code == 200, r.text
    return r.json()


def _analyze(client, pid, **settings) -> dict:
    r = client.post(f"/api/projects/{pid}/analyze", json={"settings": {"min_len": 8, "max_len": 30, **settings}})
    assert r.status_code == 200, r.text
    return wait_job(client, r.json()["job_id"])


# ---------------------------------------------------------------- access control
def test_api_requires_session_and_rejects_foreign_origins(data_dir):
    from fastapi.testclient import TestClient

    from clipforge.main import create_app

    app = create_app()
    with TestClient(app, client=("192.168.1.50", 40000)) as phone:  # another device on the network
        assert phone.get("/api/projects").status_code == 401
        assert phone.get("/api/session").json()["needs_pin"] is True
        assert phone.post("/api/pair", json={"pin": "000000"}).status_code == 403  # LAN access is off by default
        assert phone.get("/api/settings/pairing").status_code == 403
    with TestClient(app, client=("127.0.0.1", 40000)) as pc:
        assert pc.get("/api/session").json()["authenticated"] is True
        assert pc.get("/api/projects").status_code == 200
        assert pc.get("/api/projects", headers={"origin": "https://evil.example"}).status_code == 403
        assert pc.get("/api/projects", headers={"host": "evil.example"}).status_code == 403
        pin = pc.get("/api/settings/pairing").json()["pin"]
        pc.put("/api/settings", json={"lan_access": True})
    with TestClient(app, client=("192.168.1.50", 40001)) as phone:
        assert phone.post("/api/pair", json={"pin": "999999" if pin != "999999" else "111111"}).status_code == 403
        assert phone.post("/api/pair", json={"pin": pin}).status_code == 200
        assert phone.get("/api/projects").status_code == 200


def test_settings_never_expose_secrets(client):
    client.put("/api/settings", json={"llm_api_key": "sk-secret-value", "performance_profile": "quality"})
    s = client.get("/api/settings").json()
    assert s["llm_api_key"] is True and s["auth_token"] is True and s["performance_profile"] == "quality"
    assert "sk-secret-value" not in client.get("/api/settings").text
    assert client.put("/api/settings", json={"nonsense": 1}).status_code == 400


# ---------------------------------------------------------------- importing
def test_import_upload_metadata_and_errors(client, fixtures_dir):
    with open(fixtures_dir / "no_audio.mp4", "rb") as f:
        r = client.post("/api/import/upload", files={"file": ("../../evil name.mp4", f, "video/mp4")})
    assert r.status_code == 200, r.text
    src = r.json()["source"]
    assert src["origin"] == "upload" and src["managed"] and (src["width"], src["height"]) == (320, 180)
    assert Path(src["path"]).parent.name == r.json()["project"]["id"], "uploads stay inside the project folder"

    with open(fixtures_dir / "corrupted.mp4", "rb") as f:
        r = client.post("/api/import/upload", files={"file": ("broken.mp4", f, "video/mp4")})
    assert r.status_code == 400 and "could not be read" in r.json()["detail"]
    r = client.post("/api/import/upload", files={"file": ("doc.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 400 and "not a supported video type" in r.json()["detail"]
    assert len(client.get("/api/projects").json()) == 1  # failed imports leave nothing behind

    r = client.post("/api/import/path", json={"path": str(fixtures_dir / "no_audio.mp4")})
    assert r.status_code == 409 and r.json()["detail"]["project_id"]


def test_youtube_url_validation_and_unavailable_video(client):
    r = client.post("/api/import/youtube/info", json={"url": "https://example.com/watch?v=abc"})
    assert r.status_code == 400 and "valid YouTube" in r.json()["detail"]
    r = client.post("/api/import/youtube", json={"url": "https://youtu.be/abc", "authorized": False})
    assert r.status_code == 400 and "permission" in r.json()["detail"]
    # A video id that does not exist (or no network at all) must produce a readable error, not a crash.
    r = client.post("/api/import/youtube", json={"url": "https://www.youtube.com/watch?v=00000000000",
                                                "authorized": True})
    j = wait_job(client, r.json()["job_id"], timeout=120)
    assert j["status"] == "failed" and j["error"]
    assert any(k in j["error"] for k in ("unavailable", "Could not reach YouTube", "YouTube import failed"))
    assert client.get("/api/projects").json() == []


def test_video_stream_supports_seeking(client, fixtures_dir):
    pid = _import(client, fixtures_dir / "no_audio.mp4")["project"]["id"]
    r = client.get(f"/api/media/video/{pid}", headers={"range": "bytes=100-199"})
    assert r.status_code == 206 and len(r.content) == 100
    assert client.get(f"/api/media/thumb/project/{pid}").content[:2] == b"\xff\xd8"
    assert client.get("/api/fonts/Poppins-Bold.ttf").status_code == 200
    assert client.get("/api/fonts/..%2F..%2Fconfig.py").status_code == 404


# ---------------------------------------------------------------- analysis
def test_analysis_without_speech_model_fails_clearly(client, fixtures_dir):
    pid = _import(client, fixtures_dir / "speech_scene.mp4")["project"]["id"]
    j = _analyze(client, pid)
    assert j["status"] == "failed" and "No speech recognition model is installed" in j["error"]
    assert "ingestion" in j["completed_stages"] and "audio_extraction" in j["completed_stages"]


@needs_models
def test_full_workflow_import_analyze_edit_export_reopen(client, fixtures_dir, data_dir):
    install_models()
    pid = _import(client, fixtures_dir / "speech_scene.mp4")["project"]["id"]
    job = _analyze(client, pid)
    assert job["status"] == "completed", job["error"]
    assert job["completed_stages"] == ["ingestion", "audio_extraction", "transcription", "visual_analysis",
                                       "event_detection", "context_analysis", "clip_generation", "captions"]

    # transcription: real words at the right times
    tr = client.get(f"/api/projects/{pid}/transcript").json()
    assert tr["info"]["language"] == "en" and tr["info"]["word_timing"] == "estimated"
    text = " ".join(s["text"] for s in tr["segments"]).lower()
    assert "fridge" in text and "important tip" in text
    fridge = next(s for s in tr["segments"] if "fridge" in s["text"].lower())
    assert 1.0 <= fridge["start"] <= 9.0 and fridge["end"] <= 9.5

    # scene detection + events
    tl = client.get(f"/api/projects/{pid}/timeline").json()
    assert [round(s["start"]) for s in tl["scenes"]] == [0, 14, 26]
    kinds = {e["kind"] for e in tl["events"]}
    assert "energy_spike" in kinds and "speech_educational" in kinds
    assert any(34.5 <= e["start"] <= 35.5 for e in tl["events"] if e["kind"] == "energy_spike")
    assert len(tl["peaks"]) > 100

    # candidates: explainable, inside the video, no sentence cut in half
    cands = client.get(f"/api/projects/{pid}/candidates").json()
    assert 1 <= len(cands) <= 10
    for c in cands:
        assert 0 <= c["start"] < c["end"] <= 42.01 and 0 < c["score"] <= 100 and c["reason"] and c["title"]
        assert client.get(f"/api/media/thumb/candidate/{c['id']}").content[:2] == b"\xff\xd8"
        for s in tr["segments"]:
            assert not (s["start"] + 0.2 < c["start"] < s["end"] - 0.2)
            assert not (s["start"] + 0.2 < c["end"] < s["end"] - 0.2)
    tip = next(c for c in cands if "tip" in c["transcript_text"].lower())
    assert tip["category"] == "educational"

    # editor: change boundaries, crop, style and a caption; all persist
    clip_id = tip["clip_id"]
    data = client.get(f"/api/clips/{clip_id}").json()
    cues = data["captions"]["cues"]
    assert cues and all(tip["start"] - 0.5 <= c["start"] < c["end"] <= tip["end"] + 0.5 for c in cues)
    new_start, new_end = tip["start"] + 0.2, tip["end"] - 0.3
    style = {**data["clip"]["style"], "preset": "gaming", "font": "Anton", "highlight_color": "#39FF6A",
             "max_words": 3, "uppercase": True, "highlight": "word"}
    r = client.patch(f"/api/clips/{clip_id}", json={"start": new_start, "end": new_end, "aspect": "9:16",
                                                    "crop_mode": "manual", "crop": {"x": 0.8, "y": 0.5, "zoom": 1.2},
                                                    "volume": 0.8, "style": style, "title": "My tip clip"})
    assert r.status_code == 200, r.text
    cues[0]["text"] = "Here is an IMPORTANT tip"
    r = client.put(f"/api/clips/{clip_id}/captions", json={"cues": cues})
    assert r.status_code == 200 and r.json()["edited"] is True
    plan = client.get(f"/api/clips/{clip_id}/crop-plan").json()
    assert plan["effective"] == "manual" and plan["keys"][0][1] > 0.6
    srt = client.get(f"/api/clips/{clip_id}/subtitles.srt").text
    assert "Here is an IMPORTANT tip" in srt and srt.startswith("1\n00:00:0")

    # export: a real, validated MP4
    r = client.post(f"/api/clips/{clip_id}/export", json={"settings": {"resolution": "720p", "quality": "draft",
                                                                       "sidecar_srt": True}})
    ej = wait_job(client, r.json()["job_id"])
    assert ej["status"] == "completed", ej["error"]
    exp = client.get(f"/api/projects/{pid}/exports").json()[0]
    out = Path(exp["path"])
    assert out.is_file() and out.with_suffix(".srt").is_file() and exp["validation"]["ok"]
    assert {c["name"] for c in exp["validation"]["checks"]} >= {"Video stream", "Audio stream", "Duration",
                                                              "Full decode (playback validity)", "Caption timing"}
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,codec_name:format=duration", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True).stdout.split()
    assert probe[0] == "h264,720,1280"
    assert abs(float(probe[1]) - (new_end - new_start)) < 0.3
    assert client.get(f"/api/media/export/{exp['id']}").status_code == 200

    # captions are actually burned in: the same render without captions differs in the caption area
    client.patch(f"/api/clips/{clip_id}", json={"captions_enabled": False})
    r = client.post(f"/api/clips/{clip_id}/export", json={"settings": {"resolution": "720p", "quality": "draft"}})
    assert wait_job(client, r.json()["job_id"])["status"] == "completed"
    plain = Path(client.get(f"/api/projects/{pid}/exports").json()[0]["path"])
    assert _frame_bytes(out, 1.0) != _frame_bytes(plain, 1.0)

    # reopen: a fresh app instance on the same data directory keeps everything
    from fastapi.testclient import TestClient

    from clipforge.main import create_app

    with TestClient(create_app(), client=("127.0.0.1", 50001)) as c2:
        c2.get("/api/session")
        again = c2.get(f"/api/clips/{clip_id}").json()
        assert again["clip"]["title"] == "My tip clip" and again["clip"]["crop_mode"] == "manual"
        assert abs(again["clip"]["start"] - new_start) < 1e-3 and again["clip"]["style"]["font"] == "Anton"
        assert again["captions"]["cues"][0]["text"] == "Here is an IMPORTANT tip"
        assert len(again["exports"]) == 2
        assert c2.get(f"/api/projects/{pid}").json()["status"] == "analyzed"
        # re-analysis keeps the clip the user edited
        assert _analyze(c2, pid)["status"] == "completed"
        assert c2.get(f"/api/clips/{clip_id}").status_code == 200


def _frame_bytes(path: Path, t: float) -> bytes:
    return subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                           "-vf", "crop=iw:ih/3:0:ih*0.55,scale=64:36", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                          capture_output=True).stdout


@needs_models
def test_video_with_no_audio_and_video_with_nothing_interesting(client, fixtures_dir):
    install_models()
    pid = _import(client, fixtures_dir / "no_audio.mp4")["project"]["id"]
    j = _analyze(client, pid)
    assert j["status"] == "completed", j["error"]
    assert any("no audio track" in w for w in j["result"]["warnings"])
    assert client.get(f"/api/projects/{pid}/transcript").json()["segments"] == []

    pid2 = _import(client, fixtures_dir / "boring.mp4")["project"]["id"]
    j = _analyze(client, pid2)
    assert j["status"] == "completed", j["error"]
    assert client.get(f"/api/projects/{pid2}/candidates").json() == []
    assert "No interesting moments" in client.get(f"/api/projects/{pid2}").json()["notice"]

    # a manual clip can still be made and exported from a video with no audio (silent track is added)
    c = client.post(f"/api/projects/{pid}/clips", json={"start": 1.0, "end": 4.0, "title": "Manual"}).json()
    r = client.post(f"/api/clips/{c['clip_id']}/export", json={"settings": {"quality": "draft", "resolution": "720p"}})
    ej = wait_job(client, r.json()["job_id"])
    assert ej["status"] == "completed", ej["error"]


@needs_models
def test_cancel_then_retry_resumes_without_redoing_finished_stages(client, fixtures_dir):
    install_models()
    pid = _import(client, fixtures_dir / "speech_scene.mp4")["project"]["id"]
    job_id = client.post(f"/api/projects/{pid}/analyze", json={"settings": {"min_len": 8, "max_len": 30}}).json()["job_id"]
    t0 = time.time()
    while time.time() - t0 < 60:  # cancel as soon as transcription is done
        j = client.get(f"/api/jobs/{job_id}").json()
        if "transcription" in j["completed_stages"] or j["status"] != "running" and j["status"] != "queued":
            break
        time.sleep(0.05)
    client.post(f"/api/jobs/{job_id}/cancel")
    j = wait_job(client, job_id)
    if j["status"] == "completed":
        pytest.skip("machine too fast to cancel mid-analysis")
    assert j["status"] == "cancelled"
    assert client.get(f"/api/projects/{pid}").json()["status"] == "imported"
    done_before = j["completed_stages"]
    assert "transcription" in done_before

    r = client.post(f"/api/jobs/{job_id}/retry")
    j2 = wait_job(client, r.json()["job_id"])
    assert j2["status"] == "completed", j2["error"]
    assert client.get(f"/api/projects/{pid}/candidates").json()


@needs_models
def test_restart_marks_running_jobs_interrupted(client, fixtures_dir):
    from clipforge.db import session
    from clipforge.jobs.manager import manager
    from clipforge.models import Job

    pid = _import(client, fixtures_dir / "no_audio.mp4")["project"]["id"]
    with session() as s:
        s.add(Job(id="deadbeef0001", type="analysis", project_id=pid, status="running",
                  params={"project_id": pid, "settings": {}}))
    manager.recover()  # what happens when the app starts again
    j = client.get("/api/jobs/deadbeef0001").json()
    assert j["status"] == "interrupted" and "Retry" in j["error"]
    install_models()
    j2 = wait_job(client, client.post("/api/jobs/deadbeef0001/retry").json()["job_id"])
    assert j2["status"] == "completed", j2["error"]


@needs_models
def test_export_with_music_mute_and_blur_fit(client, fixtures_dir, tmp_path):
    install_models()
    pid = _import(client, fixtures_dir / "speech_scene.mp4")["project"]["id"]
    c = client.post(f"/api/projects/{pid}/clips", json={"start": 14.5, "end": 19.0, "title": "Music test"}).json()
    music = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(music)],
                   check=True)
    with open(music, "rb") as f:
        assert client.post(f"/api/clips/{c['clip_id']}/music", files={"file": ("tone.wav", f)}).status_code == 200
    assert client.post(f"/api/clips/{c['clip_id']}/music", files={"file": ("x.wav", b"junk")}).status_code == 400
    client.patch(f"/api/clips/{c['clip_id']}", json={"mute": True, "music_volume": 0.5, "crop_mode": "fit_blur",
                                                     "aspect": "1:1"})
    r = client.post(f"/api/clips/{c['clip_id']}/export",
                    json={"settings": {"quality": "draft", "resolution": "720p", "normalize": True, "fps": 30}})
    ej = wait_job(client, r.json()["job_id"])
    assert ej["status"] == "completed", ej["error"]
    exp = client.get(f"/api/projects/{pid}/exports").json()[0]
    info = exp["validation"]["info"]
    assert (info["width"], info["height"], info["fps"]) == (720, 720, 30.0)
    # the 2 s tone is looped across the 4.5 s clip, so the tail is not silent
    vol = subprocess.run(["ffmpeg", "-v", "info", "-ss", "3.5", "-i", exp["path"], "-af", "volumedetect",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    mean = float(vol.split("mean_volume:")[1].split("dB")[0])
    assert mean > -40

    # deleting the project removes its data but export files only when asked
    assert client.delete(f"/api/projects/{pid}").status_code == 200
    assert Path(exp["path"]).is_file() and not (Path(str(tmp_path)) / "data" / "projects" / pid).exists()


@needs_models
@pytest.mark.slow
def test_long_video(client, fixtures_dir, tmp_path):
    """A 10-minute video (the fixture looped) analyses within memory and time limits."""
    install_models()
    long = tmp_path / "long.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "14", "-i", str(fixtures_dir / "speech_scene.mp4"),
                    "-c", "copy", str(long)], check=True)
    pid = _import(client, long)["project"]["id"]
    j = _analyze(client, pid, count=12)
    assert j["status"] == "completed", j["error"]
    cands = client.get(f"/api/projects/{pid}/candidates").json()
    assert 5 <= len(cands) <= 12
    assert max(c["end"] for c in cands) > 300, "moments are found across the whole video, not only the start"
    shutil.rmtree(tmp_path, ignore_errors=True)
