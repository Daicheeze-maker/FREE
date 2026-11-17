import { FolderOpen, Film, Link2, Upload, ChevronLeft, Folder } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { fmtBytes, fmtDuration } from "../lib/format";
import type { Job } from "../lib/types";
import { toastError, useApp } from "../store";
import { Button, Field, Input, Modal, Notice, Progress, Spinner, cx } from "./ui";

/** Local import (drag & drop, browse this computer, paste a path) and YouTube link import. */
export function ImportPanel({ isLocal, compact }: { isLocal: boolean; compact?: boolean }) {
  const nav = useNavigate();
  const meta = useApp((s) => s.meta);
  const toast = useApp((s) => s.toast);
  const fileRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [upload, setUpload] = useState<{ name: string; frac: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [browse, setBrowse] = useState(false);
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const exts = meta?.video_extensions ?? [".mp4", ".mov", ".mkv", ".webm", ".avi"];

  const done = (res: any) => nav(`/project/${res.project.id}`);
  const fail = (e: unknown) => {
    if (e instanceof ApiError && e.status === 409 && e.data?.project_id) {
      toast("info", "This video was already imported — opening the existing project.");
      nav(`/project/${e.data.project_id}`);
    } else setError(e instanceof Error ? e.message : String(e));
  };

  async function uploadFile(file: File) {
    setError(null);
    const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
    if (!exts.includes(ext)) {
      setError(`“${file.name}” is not a supported video type. Supported: ${exts.map((e) => e.slice(1).toUpperCase()).join(", ")}.`);
      return;
    }
    setUpload({ name: file.name, frac: 0 });
    try {
      done(await api.upload("/import/upload", file, (frac) => setUpload({ name: file.name, frac })));
    } catch (e) { fail(e); } finally { setUpload(null); }
  }

  async function importPath(p: string) {
    if (!p.trim()) return;
    setError(null); setBusy(true);
    try { done(await api.post("/import/path", { path: p })); } catch (e) { fail(e); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) uploadFile(f); }}
        className={cx("flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-4 text-center transition-colors",
          compact ? "py-6" : "py-10", drag ? "border-accent bg-accent-soft/40" : "border-line-strong bg-surface")}
      >
        {upload ? (
          <div className="w-full max-w-sm space-y-2">
            <p className="truncate text-sm">Copying {upload.name}</p>
            <Progress value={upload.frac} />
            <p className="tnum text-xs text-muted">{Math.round(upload.frac * 100)}%</p>
          </div>
        ) : (
          <>
            <Film size={28} className="text-faint" />
            <div>
              <p className="text-sm font-medium">Drop a video here</p>
              <p className="mt-0.5 text-xs text-muted">{exts.map((e) => e.slice(1).toUpperCase()).join(" · ")}</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {isLocal && <Button variant="primary" icon={<FolderOpen size={14} />} onClick={() => setBrowse(true)}>Browse this computer</Button>}
              <Button variant={isLocal ? "secondary" : "primary"} icon={<Upload size={14} />} onClick={() => fileRef.current?.click()}>
                {isLocal ? "Upload a copy" : "Choose a video"}
              </Button>
            </div>
            <p className="max-w-md text-[11px] text-faint">
              {isLocal
                ? "“Browse” uses the file where it is. Dropping or uploading stores a copy inside ClipForge's data folder."
                : "The video is sent over your local network to the PC running ClipForge. It never goes to the internet."}
            </p>
          </>
        )}
        <input ref={fileRef} type="file" accept={exts.join(",") + ",video/*"} className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadFile(f); e.target.value = ""; }} />
      </div>

      {isLocal && (
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); importPath(path); }}>
          <Input placeholder="…or paste a full file path, e.g. D:\Videos\stream.mp4" value={path} onChange={(e) => setPath(e.target.value)} />
          <Button type="submit" loading={busy} disabled={!path.trim()}>Import</Button>
        </form>
      )}
      {error && <Notice tone="danger">{error}</Notice>}
      <YouTubeImport />
      {browse && <FileBrowser onClose={() => setBrowse(false)} onPick={(p) => { setBrowse(false); importPath(p); }} />}
    </div>
  );
}

function FileBrowser({ onClose, onPick }: { onClose: () => void; onPick: (path: string) => void }) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = (p: string) => api.get(`/fs/list?path=${encodeURIComponent(p)}`).then((d) => { setData(d); setErr(null); }).catch((e) => setErr(e.message));
  useEffect(() => { load(""); }, []);
  return (
    <Modal title="Choose a video" onClose={onClose} wide>
      {!data ? <div className="flex justify-center py-8">{err ? <Notice tone="danger">{err}</Notice> : <Spinner />}</div> : (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {data.roots.map((r: any) => <Button key={r.path} size="sm" onClick={() => load(r.path)}>{r.name}</Button>)}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" icon={<ChevronLeft size={14} />} disabled={!data.parent} onClick={() => load(data.parent)}>Up</Button>
            <span className="min-w-0 truncate font-mono text-xs text-muted">{data.path}</span>
          </div>
          {err && <Notice tone="danger">{err}</Notice>}
          <ul className="max-h-[50dvh] overflow-y-auto rounded-md border border-line">
            {data.dirs.map((d: any) => (
              <li key={d.path}><button className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-hover" onClick={() => load(d.path)}>
                <Folder size={14} className="shrink-0 text-muted" /><span className="truncate">{d.name}</span></button></li>
            ))}
            {data.files.map((f: any) => (
              <li key={f.path}><button className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-hover" onClick={() => onPick(f.path)}>
                <Film size={14} className="shrink-0 text-accent" /><span className="min-w-0 flex-1 truncate">{f.name}</span>
                <span className="tnum text-xs text-faint">{fmtBytes(f.size)}</span></button></li>
            ))}
            {!data.dirs.length && !data.files.length && <li className="px-3 py-6 text-center text-xs text-muted">No folders or videos here.</li>}
          </ul>
        </div>
      )}
    </Modal>
  );
}

function YouTubeImport() {
  const nav = useNavigate();
  const [url, setUrl] = useState("");
  const [info, setInfo] = useState<any>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!job || ["completed", "failed", "cancelled", "interrupted"].includes(job.status)) return;
    const id = setInterval(async () => {
      try {
        const j = await api.get<Job>(`/jobs/${job.id}`);
        setJob(j);
        if (j.status === "completed") nav(`/project/${j.result.project_id}`);
        if (j.status === "failed") setError(j.error);
      } catch (e) { toastError(e); }
    }, 700);
    return () => clearInterval(id);
  }, [job, nav]);

  async function check() {
    setError(null); setInfo(null); setBusy(true);
    try { setInfo(await api.post("/import/youtube/info", { url })); } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }
  async function start() {
    setError(null);
    try { const r = await api.post("/import/youtube", { url, authorized: ok }); setJob(await api.get(`/jobs/${r.job_id}`)); } catch (e: any) { setError(e.message); }
  }
  const running = job && ["queued", "running"].includes(job.status);

  return (
    <details className="rounded-lg border border-line bg-surface">
      <summary className="flex cursor-pointer items-center gap-2 px-3 py-2.5 text-[13px] font-medium"><Link2 size={14} className="text-muted" /> Import from a YouTube link</summary>
      <div className="space-y-3 border-t border-line p-3">
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); check(); }}>
          <Input placeholder="https://www.youtube.com/watch?v=…" value={url} onChange={(e) => { setUrl(e.target.value); setInfo(null); }} disabled={!!running} />
          <Button type="submit" loading={busy} disabled={!url.trim() || !!running}>Check</Button>
        </form>
        {info && (
          <div className="flex gap-3 rounded-md border border-line bg-bg p-2">
            {info.thumbnail && <img src={info.thumbnail} alt="" referrerPolicy="no-referrer" className="h-16 w-28 shrink-0 rounded-sm object-cover" />}
            <div className="min-w-0 text-xs">
              <p className="truncate text-[13px] font-medium">{info.title}</p>
              <p className="text-muted">{info.uploader}{info.duration ? ` · ${fmtDuration(info.duration)}` : ""}{info.height ? ` · ${info.height}p` : ""}</p>
            </div>
          </div>
        )}
        {info && !running && (
          <>
            <Field label="" row>
              <span className="flex items-start gap-2 text-xs text-text">
                <input type="checkbox" className="mt-0.5 accent-[var(--color-accent)]" checked={ok} onChange={(e) => setOk(e.target.checked)} />
                I own this video or have permission to download and edit it.
              </span>
            </Field>
            <Button variant="primary" disabled={!ok} onClick={start}>Download and import</Button>
          </>
        )}
        {running && job && (
          <div className="space-y-1.5">
            <Progress value={job.progress} />
            <div className="flex items-center justify-between text-xs text-muted">
              <span className="tnum">{job.message ?? "Starting…"}</span>
              <Button size="sm" variant="ghost" onClick={() => api.post(`/jobs/${job.id}/cancel`)}>Cancel</Button>
            </div>
          </div>
        )}
        {error && <Notice tone="danger">{error}</Notice>}
        <p className="text-[11px] text-faint">Private, age-restricted, members-only and DRM-protected videos are not supported. Local import works even when link import is unavailable.</p>
      </div>
    </details>
  );
}
