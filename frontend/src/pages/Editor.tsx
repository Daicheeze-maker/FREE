import { ArrowLeft, Check } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AudioPanel, CaptionStylePanel, CaptionTextPanel, ClipInfo, ExportPanel, VisualPanel } from "../components/editor/Panels";
import { Preview } from "../components/editor/Preview";
import { Timeline } from "../components/editor/Timeline";
import { Notice, Spinner, cx } from "../components/ui";
import { api } from "../lib/api";
import type { Clip, CropPlan, Cue, ExportRow, Job, Source, TimelineData } from "../lib/types";
import { toastError, useApp } from "../store";

interface ClipData { clip: Clip; captions: { cues: Cue[]; word_timing: string }; candidate: any; source: Source; exports: ExportRow[] }

/** Video editor. Every change is saved to the backend (debounced) and that saved state is exactly what export renders. */
export default function Editor() {
  const { id = "" } = useParams();
  const toast = useApp((s) => s.toast);
  const [data, setData] = useState<ClipData | null>(null);
  const [clip, setClip] = useState<Clip | null>(null);
  const [cues, setCuesState] = useState<Cue[]>([]);
  const [plan, setPlan] = useState<CropPlan | null>(null);
  const [tl, setTl] = useState<TimelineData | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [left, setLeft] = useState<"info" | "captions" | "text" | "visual" | "audio">("captions");
  const [mobileTab, setMobileTab] = useState<"edit" | "export">("edit");
  const [activeCue, setActiveCue] = useState<string | null>(null);
  const [saving, setSaving] = useState<"idle" | "saving" | "saved">("idle");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const pending = useRef<Partial<Clip>>({});
  const timer = useRef<number | undefined>(undefined);
  const cueTimer = useRef<number | undefined>(undefined);

  const load = useCallback(async () => {
    try {
      const d = await api.get<ClipData>(`/clips/${id}`);
      setData(d); setClip(d.clip); setCuesState(d.captions.cues);
      api.get(`/projects/${d.clip.project_id}/timeline`).then(setTl).catch(() => {});
      const running = await api.get<Job[]>(`/jobs?project_id=${d.clip.project_id}&active=true`);
      setJob(running.find((j) => j.type === "export" && j.clip_id === id) ?? null);
    } catch (e: any) { setError(e.message); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  // crop path preview follows unsaved edits immediately
  useEffect(() => {
    if (!clip) return;
    const q = new URLSearchParams({ mode: clip.crop_mode, aspect: clip.aspect, start: String(clip.start), end: String(clip.end), x: String(clip.crop.x), y: String(clip.crop.y), zoom: String(clip.crop.zoom) });
    const t = setTimeout(() => api.get<CropPlan>(`/clips/${clip.id}/crop-plan?${q}`).then(setPlan).catch(() => {}), 150);
    return () => clearTimeout(t);
  }, [clip?.id, clip?.crop_mode, clip?.aspect, clip?.start, clip?.end, clip?.crop.x, clip?.crop.y, clip?.crop.zoom]);

  // export progress
  useEffect(() => {
    if (!job || !["queued", "running", "paused"].includes(job.status)) return;
    const t = setInterval(async () => {
      const j = await api.get<Job>(`/jobs/${job.id}`);
      setJob(j);
      if (j.status === "completed") { toast("ok", "Export finished and validated."); load(); }
      if (j.status === "failed") toast("error", j.error ?? "Export failed.");
    }, 700);
    return () => clearInterval(t);
  }, [job, load, toast]);

  const flush = useCallback(async () => {
    if (!clip || !Object.keys(pending.current).length) return;
    const body = pending.current;
    pending.current = {};
    setSaving("saving");
    try { await api.patch(`/clips/${clip.id}`, body); setSaving("saved"); } catch (e) { toastError(e); setSaving("idle"); }
  }, [clip]);

  const patch = useCallback((p: Partial<Clip>) => {
    setClip((c) => (c ? { ...c, ...p } : c));
    pending.current = { ...pending.current, ...p };
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(flush, 400);
  }, [flush]);

  const setCues = useCallback((next: Cue[]) => {
    setCuesState(next);
    window.clearTimeout(cueTimer.current);
    setSaving("saving");
    cueTimer.current = window.setTimeout(async () => {
      try { const r = await api.put(`/clips/${id}/captions`, { cues: next }); setCuesState(r.cues); setSaving("saved"); } catch (e) { toastError(e); }
    }, 600);
  }, [id]);

  const regroup = useCallback(async (n: number, fromTranscript = false) => {
    await flush();
    try { const r = await api.post(`/clips/${id}/captions/rebuild`, { max_words: n, from_transcript: fromTranscript }); setCuesState(r.cues); } catch (e) { toastError(e); }
  }, [id, flush]);

  const seek = useCallback((t: number) => { const v = videoRef.current; if (v) v.currentTime = t; setTime(t); }, []);

  async function exportNow() {
    await flush();
    window.clearTimeout(cueTimer.current);
    try {
      await api.put(`/clips/${id}/captions`, { cues });
      const r = await api.post(`/clips/${id}/export`, { settings: clip!.export_settings });
      setJob(await api.get(`/jobs/${r.job_id}`));
    } catch (e) { toastError(e); }
  }

  if (error) return <div className="p-6"><Notice tone="danger">{error}</Notice></div>;
  if (!data || !clip) return <div className="flex h-full items-center justify-center"><Spinner /></div>;
  const source = data.source;

  const leftPanel = (
    <div className="p-3">
      {left === "info" && <ClipInfo clip={clip} patch={patch} candidate={data.candidate} source={source} />}
      {left === "captions" && <CaptionStylePanel clip={clip} patch={patch} onRegroup={(n) => regroup(n)} onApplyAll={async () => { await flush(); const r = await api.post(`/clips/${id}/style/apply-all`); toast("ok", `Style applied to ${r.updated} clips.`); }} />}
      {left === "text" && <CaptionTextPanel cues={cues} setCues={setCues} time={time} activeCue={activeCue} setActiveCue={setActiveCue} seek={seek} wordTiming={data.captions.word_timing} clip={clip} onReset={() => regroup(clip.style.max_words, true)} />}
      {left === "visual" && <VisualPanel clip={clip} patch={patch} plan={plan} />}
      {left === "audio" && <AudioPanel clip={clip} patch={patch} source={source}
        onMusic={async (f) => { try { const r = await api.upload(`/clips/${id}/music`, f); setClip((c) => c && { ...c, music_path: r.music_path }); } catch (e) { toastError(e); } }}
        onRemoveMusic={async () => { await api.del(`/clips/${id}/music`); setClip((c) => c && { ...c, music_path: null }); }} />}
    </div>
  );
  const rightPanel = <div className="p-3"><ExportPanel clip={clip} patch={patch} exports={data.exports} job={job} onExport={exportNow} /></div>;

  return (
    <div className="flex min-h-full flex-col lg:h-full lg:min-h-0">
      <header className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2">
        <Link to={`/project/${clip.project_id}`} className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-hover hover:text-text" aria-label="Back to project"><ArrowLeft size={16} /></Link>
        <h1 className="min-w-0 flex-1 truncate text-[13px] font-semibold">{clip.title}</h1>
        <span className="flex items-center gap-1 text-[11px] text-faint">{saving === "saving" ? <><Spinner size={12} />Saving</> : saving === "saved" ? <><Check size={12} className="text-ok" />Saved</> : null}</span>
      </header>

      <div className="flex flex-1 flex-col lg:min-h-0 lg:flex-row">
        {/* LEFT: clip info, captions, visual, audio */}
        <aside className="order-2 flex min-h-0 flex-col border-line lg:order-1 lg:w-80 lg:shrink-0 lg:border-r">
          <div className="flex overflow-x-auto border-b border-line px-1 lg:hidden">
            {(["edit", "export"] as const).map((t) => <button key={t} onClick={() => setMobileTab(t)} className={cx("h-9 px-3 text-xs font-medium capitalize", mobileTab === t ? "text-accent" : "text-muted")}>{t}</button>)}
          </div>
          <nav className={cx("flex gap-0.5 overflow-x-auto border-b border-line p-1", mobileTab === "export" && "hidden lg:flex")}>
            {([["info", "Clip"], ["captions", "Style"], ["text", "Captions"], ["visual", "Crop"], ["audio", "Audio"]] as const).map(([k, l]) => (
              <button key={k} onClick={() => setLeft(k)} className={cx("h-7 shrink-0 rounded-sm px-2.5 text-xs", left === k ? "bg-hover text-text" : "text-muted hover:text-text")}>{l}</button>
            ))}
          </nav>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className={cx(mobileTab === "export" && "hidden lg:block")}>{leftPanel}</div>
            <div className={cx("lg:hidden", mobileTab !== "export" && "hidden")}>{rightPanel}</div>
          </div>
        </aside>

        {/* CENTER: preview + BOTTOM: timeline */}
        <section className="order-1 flex min-h-0 min-w-0 flex-col lg:order-2 lg:flex-1">
          <div className="h-[46dvh] min-h-0 bg-bg lg:h-auto lg:flex-1">
            <Preview clip={clip} source={source} cues={cues} plan={plan} videoRef={videoRef} onTime={setTime} onPlaying={setPlaying} playing={playing} hasMusic={!!clip.music_path} />
          </div>
          <Timeline duration={source.duration} start={clip.start} end={clip.end} time={time} cues={cues} data={tl} showCaptions={clip.captions_enabled}
            onSeek={seek} onTrim={(s, e) => patch({ start: Math.round(s * 100) / 100, end: Math.round(e * 100) / 100 })}
            onSelectCue={(cid) => { setActiveCue(cid); setLeft("text"); }} activeCue={activeCue} />
        </section>

        {/* RIGHT: export, clip info, AI suggestion */}
        <aside className="order-3 hidden min-h-0 w-80 shrink-0 overflow-y-auto border-l border-line lg:block">{rightPanel}</aside>
      </div>
    </div>
  );
}
