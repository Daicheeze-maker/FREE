"""Background job queue.

One worker thread runs heavy jobs (analysis, export) one at a time so two large
models are never loaded together. Network jobs (downloads) get their own threads.
Progress written here is always a measured fraction supplied by the running stage.
"""
from __future__ import annotations

import threading
import time
import traceback
from typing import Callable

from ..db import session
from ..errors import CancelledError, ClipForgeError
from ..logging_setup import log
from ..models import Job, now

Handler = Callable[["JobContext"], dict | None]


class JobContext:
    def __init__(self, job_id: str, params: dict, stages: list[tuple[str, float]] | None = None):
        self.job_id = job_id
        self.params = params
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()
        self.stages = stages or []
        self._weights = dict(self.stages)
        self._total = sum(self._weights.values()) or 1.0
        self._done_weight = 0.0
        self._stage = None
        self._last_write = 0.0
        self._t0 = time.time()

    # -- cooperative control -------------------------------------------------
    def check(self) -> None:
        """Call at safe points: honours cancel, and blocks while paused."""
        if self.cancel_event.is_set():
            raise CancelledError()
        if self.pause_event.is_set():
            self._write(status="paused")
            while self.pause_event.is_set():
                if self.cancel_event.is_set():
                    raise CancelledError()
                time.sleep(0.2)
            self._write(status="running")

    def check_cancel_only(self) -> None:
        """For downloads: pausing stops the transfer (it resumes later with an HTTP Range request)."""
        if self.cancel_event.is_set() or self.pause_event.is_set():
            raise CancelledError()

    # -- progress ------------------------------------------------------------
    def start_stage(self, stage: str, message: str = "") -> None:
        self._stage = stage
        self._write(stage=stage, stage_progress=0.0, message=message, force=True)
        log.info("job %s stage %s %s", self.job_id, stage, message)

    def progress(self, frac: float, message: str | None = None) -> None:
        self.check()
        frac = min(1.0, max(0.0, frac))
        overall = (self._done_weight + self._weights.get(self._stage or "", 0) * frac) / self._total
        fields = {"stage_progress": frac, "progress": overall}
        elapsed = time.time() - self._t0
        # An ETA is only shown once there is enough measured progress to extrapolate from.
        fields["eta_seconds"] = elapsed * (1 - overall) / overall if overall > 0.05 and elapsed > 5 else None
        if message is not None:
            fields["message"] = message
        self._write(**fields)

    def finish_stage(self) -> None:
        stage = self._stage
        self._done_weight += self._weights.get(stage or "", 0)
        with session() as s:
            job = s.get(Job, self.job_id)
            if job and stage and stage not in job.completed_stages:
                job.completed_stages = [*job.completed_stages, stage]
            if job:
                job.stage_progress = 1.0
                job.progress = self._done_weight / self._total

    def skip_stage(self, stage: str) -> None:
        self._done_weight += self._weights.get(stage, 0)

    def message(self, text: str) -> None:
        self._write(message=text, force=True)

    def _write(self, force: bool = False, **fields) -> None:
        t = time.time()
        if not force and "status" not in fields and t - self._last_write < 0.25:
            return
        self._last_write = t
        with session() as s:
            job = s.get(Job, self.job_id)
            if job:
                for k, v in fields.items():
                    setattr(job, k, v)


class JobManager:
    def __init__(self) -> None:
        self.handlers: dict[str, tuple[Handler, bool, list[tuple[str, float]]]] = {}
        self.contexts: dict[str, JobContext] = {}
        self._wake = threading.Event()
        self._worker: threading.Thread | None = None
        self._stop = False
        self._lock = threading.Lock()

    def register(self, type_: str, handler: Handler, heavy: bool = True,
                 stages: list[tuple[str, float]] | None = None) -> None:
        self.handlers[type_] = (handler, heavy, stages or [])

    def start(self) -> None:
        self.recover()
        self._stop = False
        self._worker = threading.Thread(target=self._loop, name="clipforge-worker", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop = True
        for ctx in list(self.contexts.values()):
            ctx.cancel_event.set()
        self._wake.set()

    def recover(self) -> None:
        """Jobs that were mid-flight when the app closed are marked interrupted (retryable)."""
        with session() as s:
            for job in s.query(Job).filter(Job.status.in_(["running", "paused"])).all():
                job.status = "interrupted"
                job.error = "The application closed while this job was running. Retry to continue."
                job.finished_at = now()
            # light jobs cannot be resumed by the heavy worker; queued ones are restarted below
            for job in s.query(Job).filter(Job.status == "queued").all():
                if job.type in self.handlers and not self.handlers[job.type][1]:
                    job.status = "interrupted"
                    job.error = "Interrupted by restart."

    def submit(self, type_: str, params: dict, project_id: str | None = None, clip_id: str | None = None,
               completed_stages: list | None = None) -> str:
        if type_ not in self.handlers:
            raise ClipForgeError(f"Unknown job type {type_}")
        with session() as s:
            job = Job(type=type_, params=params, project_id=project_id, clip_id=clip_id,
                      completed_stages=completed_stages or [])
            s.add(job)
            s.flush()
            job_id = job.id
        if self.handlers[type_][1]:
            self._wake.set()
        else:
            threading.Thread(target=self._run, args=(job_id,), daemon=True).start()
        return job_id

    def cancel(self, job_id: str) -> None:
        ctx = self.contexts.get(job_id)
        if ctx:
            ctx.cancel_event.set()
            return
        with session() as s:
            job = s.get(Job, job_id)
            if job and job.status in ("queued", "paused"):
                job.status = "cancelled"
                job.finished_at = now()

    def pause(self, job_id: str) -> None:
        ctx = self.contexts.get(job_id)
        if ctx:
            ctx.pause_event.set()

    def resume(self, job_id: str) -> None:
        ctx = self.contexts.get(job_id)
        if ctx:
            ctx.pause_event.clear()

    def _loop(self) -> None:
        while not self._stop:
            job_id = None
            with session() as s:
                heavy = [t for t, h in self.handlers.items() if h[1]]
                job = (s.query(Job).filter(Job.status == "queued", Job.type.in_(heavy))
                       .order_by(Job.created_at, Job.id).first())
                if job:
                    job_id = job.id
            if job_id:
                self._run(job_id)
            else:
                self._wake.wait(timeout=1.0)
                self._wake.clear()

    def _run(self, job_id: str) -> None:
        with session() as s:
            job = s.get(Job, job_id)
            if not job or job.status != "queued":
                return
            job.status, job.started_at = "running", now()
            type_, params = job.type, dict(job.params)
        handler, _, stages = self.handlers[type_]
        ctx = JobContext(job_id, params, stages)
        self.contexts[job_id] = ctx
        status, error, result = "completed", None, {}
        try:
            result = handler(ctx) or {}
        except CancelledError:
            status = "cancelled"
        except ClipForgeError as e:
            status, error = "failed", str(e)
            log.warning("job %s failed: %s", job_id, e)
        except Exception as e:  # noqa: BLE001 - a job must never take the worker down
            status, error = "failed", f"Unexpected error: {e}"
            log.error("job %s crashed:\n%s", job_id, traceback.format_exc())
        finally:
            self.contexts.pop(job_id, None)
        with session() as s:
            job = s.get(Job, job_id)
            if job:
                job.status, job.error, job.finished_at = status, error, now()
                job.eta_seconds = None
                if status == "completed":
                    job.progress = 1.0
                    job.result = result


manager = JobManager()
