from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import paths

log = logging.getLogger("clipforge")


def setup_logging() -> None:
    paths.ensure()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    log.setLevel(logging.INFO)
    for h in list(log.handlers):
        log.removeHandler(h)
    fh = RotatingFileHandler(paths.logs / "clipforge.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(sh)


def tail(lines: int = 300) -> str:
    f = paths.logs / "clipforge.log"
    if not f.exists():
        return ""
    data = f.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(data[-lines:])
