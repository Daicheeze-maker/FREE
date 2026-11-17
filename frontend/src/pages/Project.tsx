import { AlertTriangle, CheckCircle2, Circle, Download, Pause, Pencil, Play, Plus, RotateCw, Search, Sparkles, ThumbsDown, Undo2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Thumb } from "../components/ProjectCard";
import { Badge, Button, Empty, Field, IconButton, Input, Modal, Notice, PageHeader, Panel, Progress, Segmented, Select, Slider, Spinner, Stat, Toggle, cx } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api, media } from "../lib/api";
import { LANG_NAMES, fmtBytes, fmtDuration, fmtEta, fmtTime } from "../lib/format";
import type { Candidate, Job, Project } from "../lib/types";
import { toastError, useApp } from "../store";

export default function ProjectPage() {
  const { id = "" } = useParams();
  const project = usePoll<Project>(() => api.get(`/projects/${id}`), 1500, [id]);
  const [showSettings, setShowSettings] = useState(false);
  const p = project.data;
  if (project.error && !p) return <Notice tone="danger">{project.error} <Link className="underline" to="/library">Back to the library</Link></Notice>;
  if (!p || !p.source) return <Spinner />;

  const job = p.active_job;
  const analyzing = job?.type === "analysis";
  const last = p.last_analysis;
  const failed = !analyzing && last && ["failed", "cancelled", "interrupted"].includes(last.status) && p.status !== "analyzed";

  return (
    <div className="space-y-4">
      <PageHeader title={p.name}
        subtitle={<span className="tnum">{fmtDuration(p.source.duration)} · {p.source.width}×{p.source.height} · {p.source.fps} fps · {p.source.has_audio ? `${p.source.audio_codec} audio` : "no audio"} · {fmtBytes(p.source.size_bytes)}</span>}
        actions={p.status === "analyzed" && !analyzing && <Button icon={<RotateCw size={14} />} onClick={() => setShowSettings(true)}>Re-analyze</Button>} />
      {p.source_missing && <Notice tone="danger">The source video is no longer at <span className="font-mono">{p.source.path}</span>. Move it back to preview, analyze or export.</Notice>}
      {job?.type === "proxy" && (
        <Notice>Creating a preview copy because this format cannot be played directly ({Math.round(job.progress * 100)}%). Analysis and exports always use the original file.</Notice>
      )}

      {analyzing ? <AnalysisView project={p} job={job!} />
        : p.status === "analyzed" && !showSettings ? <Results project={p} />
        : (
          <>
            {failed && last && <FailedNotice job={last} onRetry={project.reload} />}
            <SourceInfo project={p} />
            <AnalysisSettings project={p} onStarted={() => { setShowSettings(false); project.reload(); }} onCancel={p.status === "analyzed" ? () => setShowSettings(false) : undefined} />
          </>
        )}
    </div>
  );
}

function FailedNotice({ job, onRetry }: { job: Job; onRetry: () => void }) {
  const done = job.completed_stages.length;
  return (
    <Notice tone={job.status === "failed" ? "danger" : "warn"}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium">{job.status === "failed" ? "The last analysis failed" : job.status === "cancelled" ? "The last analysis was cancelled" : "The last analysis was interrupted"}{job.stage ? ` during ${job.stage.replace(/_/g, " ")}` : ""}.</p>
          {job.error && <p className="mt-0.5 break-words text-muted">{job.error}</p>}
        </div>
        <Button size="sm" icon={<RotateCw size={13} />} onClick={() => api.post(`/jobs/${job.id}/retry`).then(onRetry).catch(toastError)}>
          {done > 1 ? `Resume (${done} stages already done)` : "Retry"}
        </Button>
      </div>
    </Notice>
  );
}

function SourceInfo({ project: p }: { project: Project }) {
  const s = p.source!;
  return (
    <Panel title="Source video">
      <div className="grid gap-3 p-3 sm:grid-cols-[240px_1fr]">
        <video src={media.video(p.id)} poster={media.projectThumb(p.id)} controls preload="metadata" className="aspect-video w-full rounded-md bg-black" />
        <div className="grid grid-cols-2 content-start gap-3 sm:grid-cols-3">
          <Stat label="Duration" value={fmtTime(s.duration)} />
          <Stat label="Resolution" value={`${s.width}×${s.height}`} />
          <Stat label="Frame rate" value={`${s.fps} fps`} />
          <Stat label="Video" value={s.video_codec ?? "–"} />
          <Stat label="Audio" value={s.has_audio ? `${s.audio_codec} · ${s.sample_rate} Hz · ${s.channels} ch` : "none"} />
          <Stat label="File size" value={fmtBytes(s.size_bytes)} />
          <div className="col-span-full"><Stat label={s.origin === "youtube" ? "Imported from" : "File"} value={<span className="font-mono text-[11px]">{s.origin === "youtube" ? s.origin_url : s.path}</span>} /></div>
        </div>
      </div>
    </Panel>
  );
}

function AnalysisSettings({ project: p, onStarted, onCancel }: { project: Project; onStarted: () => void; onCancel?: () => void }) {
  const meta = useApp((s) => s.meta)!;
  const [cfg, setCfg] = useState<any>({ ...meta.analysis_defaults, ...(p.settings ?? {}) });
  const [busy, setBusy] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const status = usePoll<any>(() => api.get("/system/status"), null);
  const set = (k: string, v: any) => setCfg((c: any) => ({ ...c, [k]: v }));
  const cats = Object.entries(meta.categories).filter(([k]) => k !== "custom");
  const st = status.data;

  async function start() {
    setBusy(true);
    try { await api.post(`/projects/${p.id}/analyze`, { settings: cfg }); onStarted(); } catch (e) { toastError(e); } finally { setBusy(false); }
  }
  const needsAsr = p.source!.has_audio && st && !st.models_ready.asr;

  return (
    <Panel title="Analysis settings">
      <div className="space-y-4 p-3">
        <div>
          <p className="mb-1.5 text-xs text-muted">What to look for</p>
          <div className="flex flex-wrap gap-1.5">
            {cats.map(([k, label]) => {
              const on = cfg.categories.includes(k);
              return (
                <button key={k} type="button" aria-pressed={on}
                  onClick={() => set("categories", on ? cfg.categories.filter((c: string) => c !== k) : [...cfg.categories, k])}
                  className={cx("h-7 rounded-md border px-2.5 text-xs font-medium transition-colors", on ? "border-accent bg-accent-soft text-accent" : "border-line text-muted hover:text-text")}>
                  {label}
                </button>
              );
            })}
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Shortest clip"><Slider value={cfg.min_len} min={5} max={60} onChange={(v) => setCfg((c: any) => ({ ...c, min_len: v, max_len: Math.max(c.max_len, v + 5) }))} format={(v) => `${v}s`} /></Field>
          <Field label="Longest clip"><Slider value={cfg.max_len} min={10} max={180} step={5} onChange={(v) => setCfg((c: any) => ({ ...c, max_len: v, min_len: Math.min(c.min_len, v - 5) }))} format={(v) => `${v}s`} /></Field>
          <Field label="Number of suggestions"><Slider value={cfg.count} min={1} max={30} onChange={(v) => set("count", v)} /></Field>
          <Field label="Aspect ratio">
            <Segmented value={cfg.aspect} onChange={(v) => set("aspect", v)} options={[{ value: "9:16", label: "9:16 Vertical" }, { value: "1:1", label: "1:1 Square" }, { value: "16:9", label: "16:9 Wide" }]} />
          </Field>
          <Field label="Spoken language" hint="Captions keep the original language — Tagalog and Taglish are never translated.">
            <Select value={cfg.language} onChange={(e) => set("language", e.target.value)}
              options={[{ value: "auto", label: "Detect automatically" }, { value: "en", label: "English" }, { value: "tl", label: "Filipino / Tagalog / Taglish" }, { value: "es", label: "Spanish" }, { value: "ja", label: "Japanese" }, { value: "ko", label: "Korean" }]} />
          </Field>
          <Field label="Caption style">
            <Select value={cfg.caption_preset} onChange={(e) => set("caption_preset", e.target.value)}
              options={["dynamic", "minimal", "gaming", "podcast"].map((k) => ({ value: k, label: k[0].toUpperCase() + k.slice(1) }))} />
          </Field>
          <Field label="Analysis intensity" hint="How densely frames and audio are inspected.">
            <Segmented value={cfg.profile} onChange={(v) => set("profile", v)} options={[{ value: "performance", label: "Performance" }, { value: "balanced", label: "Balanced" }, { value: "quality", label: "Quality" }]} />
          </Field>
        </div>
        <button type="button" className="text-xs text-muted underline hover:text-text" onClick={() => setAdvanced(!advanced)}>{advanced ? "Hide" : "Show"} advanced model settings</button>
        {advanced && st && (
          <div className="space-y-3 rounded-md border border-line bg-bg p-3">
            <Field label="Normalize audio before analysis" row hint={undefined}><Toggle label="Normalize audio" checked={cfg.normalize_audio} onChange={(v) => set("normalize_audio", v)} /></Field>
            <p className="-mt-2 text-[11px] text-faint">Evens out very quiet or uneven recordings so speech recognition hears them better. Loudness-based signals become less distinct.</p>
            <Field label="Use the local vision/context model" row><Toggle label="Use local AI model" checked={cfg.use_llm && st.llm.enabled} disabled={!st.llm.enabled} onChange={(v) => set("use_llm", v)} /></Field>
            {!st.llm.enabled && <p className="-mt-2 text-[11px] text-faint">Not configured. Set it up in Settings → AI models to add frame descriptions and conversation-level judgement.</p>}
            <div className="flex flex-wrap gap-1.5 text-[11px]">
              <Badge tone={st.models_ready.asr ? "ok" : "danger"}>Speech model {st.models_ready.asr ? "ready" : "missing"}</Badge>
              <Badge tone={st.models_ready.audio_tagging ? "ok" : "warn"}>Audio events {st.models_ready.audio_tagging ? "ready" : "off"}</Badge>
              <Badge tone={st.models_ready.vad ? "ok" : "warn"}>Silero VAD {st.models_ready.vad ? "ready" : "off"}</Badge>
              <Badge tone={st.models_ready.face ? "ok" : "warn"}>Face detector {st.models_ready.face ? "ready" : "off"}</Badge>
            </div>
          </div>
        )}
        {needsAsr && <Notice tone="warn">No speech recognition model is installed, so this video cannot be transcribed. <Link to="/settings" className="underline">Download one in Settings → AI models</Link>.</Notice>}
        <div className="flex gap-2">
          <Button variant="primary" icon={<Sparkles size={14} />} loading={busy} disabled={!cfg.categories.length || p.source_missing || !!needsAsr} onClick={start}>Analyze video</Button>
          {onCancel && <Button onClick={onCancel}>Back to results</Button>}
        </div>
      </div>
    </Panel>
  );
}

function AnalysisView({ project: p, job }: { project: Project; job: Job }) {
  const meta = useApp((s) => s.meta)!;
  const pastTranscription = job.completed_stages.includes("transcription") || job.stage === "transcription";
  const transcript = usePoll<any>(() => api.get(`/projects/${p.id}/transcript`), job.completed_stages.includes("transcription") ? null : 2500, [job.completed_stages.length]);
  const segs: any[] = transcript.data?.segments ?? [];
  const idx = meta.stages.findIndex((s) => s.id === job.stage);

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <Panel title="AI analysis" actions={
        <>
          {job.status === "paused"
            ? <Button size="sm" icon={<Play size={13} />} onClick={() => api.post(`/jobs/${job.id}/resume`).catch(toastError)}>Resume</Button>
            : <Button size="sm" icon={<Pause size={13} />} disabled={job.status !== "running"} onClick={() => api.post(`/jobs/${job.id}/pause`).catch(toastError)}>Pause</Button>}
          <Button size="sm" variant="danger" icon={<X size={13} />} onClick={() => api.post(`/jobs/${job.id}/cancel`).catch(toastError)}>Cancel</Button>
        </>}>
        <div className="space-y-3 p-3">
          <div>
            <div className="mb-1 flex justify-between text-xs"><span className="text-text">{job.status === "queued" ? "Waiting for another job to finish" : job.status === "paused" ? "Paused" : "Working"}</span>
              <span className="tnum text-muted">{Math.round(job.progress * 100)}% {fmtEta(job.eta_seconds)}</span></div>
            <Progress value={job.progress} />
          </div>
          <ol className="space-y-1">
            {meta.stages.map((s, i) => {
              const done = job.completed_stages.includes(s.id);
              const active = s.id === job.stage && !done;
              return (
                <li key={s.id} className={cx("rounded-md px-2 py-1.5", active && "bg-raised")}>
                  <div className="flex items-center gap-2 text-[13px]">
                    {done ? <CheckCircle2 size={14} className="text-ok" /> : active ? <Spinner size={14} /> : <Circle size={14} className="text-faint" />}
                    <span className={cx(done || active ? "text-text" : "text-faint")}>{i + 1}. {s.label}</span>
                    {active && <span className="tnum ml-auto text-xs text-muted">{Math.round(job.stage_progress * 100)}%</span>}
                  </div>
                  {active && (
                    <div className="mt-1.5 pl-6">
                      <Progress value={job.stage_progress} />
                      {job.message && <p className="mt-1 truncate text-[11px] text-muted">{job.message}</p>}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
          <p className="text-[11px] leading-relaxed text-faint">Percentages are measured from the work completed. Stages 9–10 (rendering and validation) run when you export a clip.{idx >= 0 && job.eta_seconds == null ? " A time estimate appears once enough has been processed." : ""}</p>
          <div className="grid grid-cols-3 gap-2 border-t border-line pt-3">
            <Stat label="Sentences" value={p.counts?.segments ?? 0} />
            <Stat label="Scenes" value={p.counts?.scenes ?? 0} />
            <Stat label="Events" value={p.counts?.events ?? 0} />
          </div>
        </div>
      </Panel>
      <Panel title={`Transcript preview${transcript.data?.info?.language ? ` · ${LANG_NAMES[transcript.data.info.language] ?? transcript.data.info.language}` : ""}`}>
        {segs.length ? (
          <ul className="max-h-[60dvh] space-y-1 overflow-y-auto p-3">
            {segs.map((s) => <li key={s.idx} className="flex gap-3 text-[13px]"><span className="tnum w-12 shrink-0 text-xs text-faint">{fmtTime(s.start)}</span><span>{s.text}</span></li>)}
          </ul>
        ) : (
          <Empty title={pastTranscription && job.stage === "transcription" ? "Transcribing…" : pastTranscription ? "No speech was found" : "The transcript appears here after transcription"}>
            {job.stage === "transcription" && job.message}
          </Empty>
        )}
      </Panel>
    </div>
  );
}

function scoreTone(score: number, low: boolean): "ok" | "accent" | "neutral" {
  return low ? "neutral" : score >= 55 ? "ok" : "accent";
}

function Results({ project: p }: { project: Project }) {
  const meta = useApp((s) => s.meta)!;
  const toast = useApp((s) => s.toast);
  const nav = useNavigate();
  const cands = usePoll<Candidate[]>(() => api.get(`/projects/${p.id}/candidates`), 4000, [p.id]);
  const [cat, setCat] = useState("all");
  const [showRejected, setShowRejected] = useState(false);
  const [preview, setPreview] = useState<Candidate | null>(null);
  const [query, setQuery] = useState("");
  const [searchJob, setSearchJob] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const [exporting, setExporting] = useState<Record<string, string>>({});
  const warnings: string[] = p.last_analysis?.result?.warnings ?? [];
  const all = cands.data ?? [];
  const visible = all.filter((c) => (showRejected ? c.status === "rejected" : c.status !== "rejected") && (cat === "all" || c.category === cat));
  const cats = [...new Set(all.map((c) => c.category))];

  useEffect(() => {
    if (!searchJob) return;
    const t = setInterval(async () => {
      const j = await api.get<Job>(`/jobs/${searchJob}`);
      if (j.status === "completed") {
        setSearchJob(null); cands.reload(); setCat("custom");
        toast(j.result.found ? "ok" : "info", j.result.found ? `Found ${j.result.found} matching moment${j.result.found === 1 ? "" : "s"}${j.result.method === "text" ? " (transcript text match)" : ""}.` : "Nothing matching was found.");
      } else if (j.status === "failed" || j.status === "cancelled") { setSearchJob(null); toast("error", j.error ?? "Search was cancelled."); }
    }, 800);
    return () => clearInterval(t);
  }, [searchJob]);

  const setStatus = (c: Candidate, status: string) => api.patch(`/candidates/${c.id}`, { status }).then(cands.reload).catch(toastError);
  async function quickExport(c: Candidate) {
    try {
      const r = await api.post(`/clips/${c.clip_id}/export`, {});
      setExporting((e) => ({ ...e, [c.id]: r.job_id }));
      toast("info", "Export started. Progress is shown in the sidebar.");
    } catch (e) { toastError(e); }
  }

  return (
    <div className="space-y-3">
      {p.notice && <Notice tone="warn">{p.notice}</Notice>}
      {warnings.map((w) => <Notice key={w} tone="info"><AlertTriangle size={12} className="mr-1 inline text-warn" />{w}</Notice>)}
      <div className="flex flex-wrap items-center gap-2">
        <Segmented value={cat} onChange={setCat} size="sm"
          options={[{ value: "all", label: `All (${all.filter((c) => c.status !== "rejected").length})` }, ...cats.map((c) => ({ value: c, label: meta.categories[c] ?? c }))]} />
        <label className="flex items-center gap-1.5 text-xs text-muted"><input type="checkbox" className="accent-[var(--color-accent)]" checked={showRejected} onChange={(e) => setShowRejected(e.target.checked)} />Rejected</label>
        <form className="ml-auto flex min-w-56 flex-1 gap-2 sm:max-w-sm" onSubmit={(e) => { e.preventDefault(); if (query.trim().length > 1) api.post(`/projects/${p.id}/search`, { query }).then((r) => setSearchJob(r.job_id)).catch(toastError); }}>
          <div className="relative flex-1"><Search size={14} className="pointer-events-none absolute left-2.5 top-2.5 text-faint" />
            <Input className="pl-8" placeholder="Custom AI search: “when he talks about the boss fight”" value={query} onChange={(e) => setQuery(e.target.value)} /></div>
          <Button type="submit" loading={!!searchJob} disabled={query.trim().length < 2}>Find</Button>
        </form>
        <Button icon={<Plus size={14} />} onClick={() => setManual(true)}>Manual clip</Button>
      </div>
      <p className="text-[11px] text-faint">Scores estimate how interesting the content is based on detected signals. They do not predict views or virality.{p.transcript?.word_timing === "estimated" && " Caption word timing is estimated from sentence timing with this speech model."}</p>

      {!cands.data ? <Spinner /> : visible.length === 0 ? (
        <Panel><Empty title={showRejected ? "No rejected suggestions" : "No suggestions to show"}>{!showRejected && "Create a manual clip, try a custom search, or re-analyze with different settings."}</Empty></Panel>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((c) => (
            <article key={c.id} className={cx("flex flex-col overflow-hidden rounded-lg border bg-surface", c.status === "accepted" ? "border-ok/40" : "border-line")}>
              <button className="group relative aspect-video" onClick={() => setPreview(c)} aria-label={`Preview ${c.title}`}>
                <Thumb src={media.candidateThumb(c.id)} className="h-full w-full" />
                <span className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/35"><Play size={28} className="text-white opacity-0 transition-opacity group-hover:opacity-100" /></span>
                <span className="tnum absolute bottom-1 right-1 rounded-sm bg-black/75 px-1 text-[11px]">{fmtDuration(c.duration)}</span>
                {c.source !== "manual" && <span className="tnum absolute left-1 top-1 rounded-sm bg-black/75 px-1.5 py-0.5 text-xs font-semibold">{Math.round(c.score)}</span>}
              </button>
              <div className="flex flex-1 flex-col gap-2 p-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone={scoreTone(c.score, c.low_confidence)}>{meta.categories[c.category] ?? c.category}</Badge>
                  {c.low_confidence && <Badge tone="warn">low confidence</Badge>}
                  {c.source === "llm" && <Badge tone="info">language model</Badge>}
                  {c.status === "accepted" && <Badge tone="ok">kept</Badge>}
                  {c.exports > 0 && <Badge>exported</Badge>}
                </div>
                <h3 className="line-clamp-2 text-[13px] font-medium leading-snug">{c.title}</h3>
                <p className="tnum text-[11px] text-faint">{fmtTime(c.start)} – {fmtTime(c.end)}{c.source !== "manual" && ` · confidence ${Math.round(c.confidence * 100)}%`}</p>
                <p className="line-clamp-3 text-xs leading-relaxed text-muted">{c.reason}</p>
                <div className="mt-auto flex items-center gap-1.5 pt-1">
                  <Button size="sm" variant="primary" icon={<Pencil size={13} />} disabled={!c.clip_id} onClick={() => nav(`/clip/${c.clip_id}`)}>Edit</Button>
                  <Button size="sm" icon={<Download size={13} />} disabled={!c.clip_id || !!exporting[c.id]} onClick={() => quickExport(c)}>Export</Button>
                  <span className="flex-1" />
                  {c.status === "rejected"
                    ? <IconButton label="Restore" onClick={() => setStatus(c, "suggested")}><Undo2 size={14} /></IconButton>
                    : <IconButton label="Reject suggestion" onClick={() => setStatus(c, "rejected")}><ThumbsDown size={14} /></IconButton>}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      {preview && <PreviewModal project={p} cand={preview} onClose={() => setPreview(null)} />}
      {manual && <ManualClip project={p} onClose={() => setManual(false)} onCreated={(c) => nav(`/clip/${c.clip_id}`)} />}
    </div>
  );
}

function PreviewModal({ project: p, cand: c, onClose }: { project: Project; cand: Candidate; onClose: () => void }) {
  const meta = useApp((s) => s.meta)!;
  const nav = useNavigate();
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    const start = () => { v.currentTime = c.start; v.play().catch(() => {}); };
    const tick = () => { if (v.currentTime >= c.end) { v.pause(); v.currentTime = c.start; } };
    v.addEventListener("loadedmetadata", start);
    v.addEventListener("timeupdate", tick);
    return () => { v.removeEventListener("loadedmetadata", start); v.removeEventListener("timeupdate", tick); };
  }, [c]);
  return (
    <Modal title={c.title} onClose={onClose} wide
      footer={<><Button onClick={onClose}>Close</Button><Button variant="primary" icon={<Pencil size={13} />} disabled={!c.clip_id} onClick={() => nav(`/clip/${c.clip_id}`)}>Open in editor</Button></>}>
      <div className="space-y-3">
        <video ref={ref} src={media.video(p.id)} controls playsInline className="max-h-[45dvh] w-full rounded-md bg-black" />
        <p className="tnum text-xs text-muted">{fmtTime(c.start, true)} – {fmtTime(c.end, true)} · {fmtDuration(c.duration)} · {meta.categories[c.category]}</p>
        <p className="text-xs leading-relaxed">{c.reason}</p>
        {Object.keys(c.scores).length > 0 && (
          <div className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
            {Object.entries(meta.score_labels).map(([k, label]) => (
              <div key={k} className="flex items-center gap-2 text-[11px]"><span className="w-40 shrink-0 text-muted">{label}</span><Progress value={c.scores[k] ?? 0} /><span className="tnum w-7 text-right text-faint">{Math.round((c.scores[k] ?? 0) * 100)}</span></div>
            ))}
          </div>
        )}
        {c.transcript_text && <blockquote className="border-l-2 border-line-strong pl-3 text-xs leading-relaxed text-muted">{c.transcript_text}</blockquote>}
      </div>
    </Modal>
  );
}

function ManualClip({ project: p, onClose, onCreated }: { project: Project; onClose: () => void; onCreated: (c: Candidate) => void }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(Math.min(30, p.source!.duration));
  const [title, setTitle] = useState("Manual clip");
  const [busy, setBusy] = useState(false);
  const now = () => ref.current?.currentTime ?? 0;
  async function create() {
    setBusy(true);
    try { onCreated(await api.post(`/projects/${p.id}/clips`, { start, end, title })); } catch (e) { toastError(e); } finally { setBusy(false); }
  }
  return (
    <Modal title="Create a clip manually" onClose={onClose} wide
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={busy} disabled={end - start < 0.5} onClick={create}>Create and edit</Button></>}>
      <div className="space-y-3">
        <video ref={ref} src={media.video(p.id)} controls playsInline className="max-h-[40dvh] w-full rounded-md bg-black" />
        <div className="flex flex-wrap items-end gap-2">
          <Button onClick={() => setStart(Math.min(now(), end - 0.5))}>Set start here</Button>
          <Button onClick={() => setEnd(Math.max(now(), start + 0.5))}>Set end here</Button>
          <span className="tnum text-xs text-muted">{fmtTime(start, true)} – {fmtTime(end, true)} ({fmtDuration(end - start)})</span>
        </div>
        <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
      </div>
    </Modal>
  );
}
