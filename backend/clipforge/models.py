"""Database models. Large media stays on disk; only paths and metadata live here."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _Dict:
    def to_dict(self) -> dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}  # type: ignore[attr-defined]


def _pk() -> Mapped[str]:
    return mapped_column(String(12), primary_key=True, default=new_id)


def _project_fk() -> Mapped[str]:
    return mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)


class Project(Base, _Dict):
    __tablename__ = "projects"
    id: Mapped[str] = _pk()
    name: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="imported")  # imported|analyzing|analyzed|failed
    settings: Mapped[dict] = mapped_column(JSON, default=dict)  # last analysis settings
    notice: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. "no strong moments found"
    created_at: Mapped[str] = mapped_column(String(32), default=now)
    updated_at: Mapped[str] = mapped_column(String(32), default=now, onupdate=now)


class SourceVideo(Base, _Dict):
    __tablename__ = "source_videos"
    __table_args__ = (UniqueConstraint("fingerprint"),)  # prevents duplicate imports
    id: Mapped[str] = _pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    path: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(400))
    origin: Mapped[str] = mapped_column(String(12), default="local")  # local|upload|youtube
    origin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    managed: Mapped[bool] = mapped_column(Boolean, default=False)  # file owned by the app (deleted with project)
    fingerprint: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[float] = mapped_column(Float, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0)
    video_codec: Mapped[str | None] = mapped_column(String(40), nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(40), nullable=True)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proxy_path: Mapped[str | None] = mapped_column(Text, nullable=True)  # browser-playable copy when needed
    thumb_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class Job(Base, _Dict):
    """Analysis, export, download and import jobs share one queue table."""

    __tablename__ = "jobs"
    id: Mapped[str] = _pk()
    type: Mapped[str] = mapped_column(String(20))  # analysis|export|youtube|model_download|search
    project_id: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    clip_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    status: Mapped[str] = mapped_column(String(14), default="queued")
    # queued|running|paused|completed|failed|cancelled|interrupted
    stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0)  # overall 0..1, measured
    stage_progress: Mapped[float] = mapped_column(Float, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    completed_stages: Mapped[list] = mapped_column(JSON, default=list)
    eta_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=now)
    started_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Transcript(Base, _Dict):
    __tablename__ = "transcripts"
    id: Mapped[str] = _pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    language: Mapped[str | None] = mapped_column(String(12), nullable=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    word_timing: Mapped[str] = mapped_column(String(12))  # "word" (from the model) | "estimated"


class Speaker(Base, _Dict):
    __tablename__ = "speakers"
    id: Mapped[str] = _pk()
    project_id: Mapped[str] = _project_fk()
    label: Mapped[str] = mapped_column(String(80))


class TranscriptSegment(Base, _Dict):
    __tablename__ = "transcript_segments"
    id: Mapped[str] = _pk()
    project_id: Mapped[str] = _project_fk()
    idx: Mapped[int] = mapped_column(Integer)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(12), nullable=True)
    speaker_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    words: Mapped[list] = mapped_column(JSON, default=list)  # [{w, start, end}]


class Scene(Base, _Dict):
    __tablename__ = "scenes"
    id: Mapped[str] = _pk()
    project_id: Mapped[str] = _project_fk()
    idx: Mapped[int] = mapped_column(Integer)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)


class DetectedEvent(Base, _Dict):
    __tablename__ = "detected_events"
    id: Mapped[str] = _pk()
    project_id: Mapped[str] = _project_fk()
    kind: Mapped[str] = mapped_column(String(40))
    modality: Mapped[str] = mapped_column(String(10))  # audio|visual|speech
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    intensity: Mapped[float] = mapped_column(Float, default=0)  # 0..1
    confidence: Mapped[float] = mapped_column(Float, default=0)  # 0..1
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class ClipCandidate(Base, _Dict):
    __tablename__ = "clip_candidates"
    id: Mapped[str] = _pk()
    project_id: Mapped[str] = _project_fk()
    rank: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(300))
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(Float)  # 0..100 estimated content interest
    confidence: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)  # explainable sub-scores
    transcript_text: Mapped[str] = mapped_column(Text, default="")
    thumb_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="suggested")  # suggested|accepted|rejected
    source: Mapped[str] = mapped_column(String(12), default="signals")  # signals|llm|search
    low_confidence: Mapped[bool] = mapped_column(Boolean, default=False)


class GeneratedClip(Base, _Dict):
    """Editable clip state. Everything here feeds the renderer."""

    __tablename__ = "generated_clips"
    id: Mapped[str] = _pk()
    project_id: Mapped[str] = _project_fk()
    candidate_id: Mapped[str | None] = mapped_column(String(12), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(300))
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    aspect: Mapped[str] = mapped_column(String(8), default="9:16")
    crop_mode: Mapped[str] = mapped_column(String(12), default="smart")  # smart|face|center|manual|original|fit_blur
    crop: Mapped[dict] = mapped_column(JSON, default=dict)  # manual: {x, y, zoom}
    volume: Mapped[float] = mapped_column(Float, default=1.0)
    mute: Mapped[bool] = mapped_column(Boolean, default=False)
    music_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_volume: Mapped[float] = mapped_column(Float, default=0.25)
    captions_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    style: Mapped[dict] = mapped_column(JSON, default=dict)  # full caption style used for this clip
    export_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(32), default=now)
    updated_at: Mapped[str] = mapped_column(String(32), default=now, onupdate=now)


class CaptionTrack(Base, _Dict):
    __tablename__ = "caption_tracks"
    id: Mapped[str] = _pk()
    clip_id: Mapped[str] = mapped_column(ForeignKey("generated_clips.id", ondelete="CASCADE"), unique=True)
    # cues are in SOURCE time so trimming never desyncs them: [{id,start,end,text,speaker,words:[{w,start,end}]}]
    cues: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str | None] = mapped_column(String(12), nullable=True)
    word_timing: Mapped[str] = mapped_column(String(12), default="estimated")
    edited: Mapped[bool] = mapped_column(Boolean, default=False)


class CaptionStyle(Base, _Dict):
    __tablename__ = "caption_styles"
    id: Mapped[str] = _pk()
    name: Mapped[str] = mapped_column(String(80), unique=True)
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class ExportJob(Base, _Dict):
    __tablename__ = "export_jobs"
    id: Mapped[str] = _pk()
    clip_id: Mapped[str] = mapped_column(ForeignKey("generated_clips.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(String(12), index=True)
    job_id: Mapped[str] = mapped_column(String(12))
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="queued")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default=now)


class AIModel(Base, _Dict):
    __tablename__ = "ai_models"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)  # catalog id
    status: Mapped[str] = mapped_column(String(14), default="not_installed")
    # not_installed|downloading|paused|installed|error
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    bytes_done: Mapped[int] = mapped_column(Integer, default=0)
    bytes_total: Mapped[int] = mapped_column(Integer, default=0)
    verified_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppSetting(Base, _Dict):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
