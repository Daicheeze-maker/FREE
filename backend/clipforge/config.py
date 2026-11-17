"""Paths and static configuration. All user data lives under one data directory."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ClipForge AI"
VERSION = "0.1.0"

PACKAGE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
REPO_DIR = PACKAGE_DIR.parent.parent
FRONTEND_DIST = Path(os.environ.get("CLIPFORGE_FRONTEND", REPO_DIR / "frontend" / "dist"))

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def default_data_dir() -> Path:
    env = os.environ.get("CLIPFORGE_DATA")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "ClipForge"
    return Path.home() / ".clipforge"


class Paths:
    """Resolved lazily so tests can point CLIPFORGE_DATA at a temp directory."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_data_dir()

    @property
    def db(self) -> Path:
        return self.root / "clipforge.db"

    @property
    def projects(self) -> Path:
        return self.root / "projects"

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def tmp(self) -> Path:
        return self.root / "tmp"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    def project(self, project_id: str) -> Path:
        p = self.projects / project_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ensure(self) -> None:
        for p in (self.root, self.projects, self.models, self.logs, self.tmp, self.exports):
            p.mkdir(parents=True, exist_ok=True)


paths = Paths()


def set_data_dir(root: Path) -> None:
    paths.root = Path(root)
    paths.ensure()
