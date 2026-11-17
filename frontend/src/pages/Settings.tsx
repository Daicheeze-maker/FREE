import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useSession } from "../App";
import { ModelsPanel } from "../components/ModelsPanel";
import { Badge, Button, Field, Input, Notice, PageHeader, Panel, Select, Spinner, Stat, Toggle, cx } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api } from "../lib/api";
import { fmtBytes } from "../lib/format";
import { toastError, useApp } from "../store";
import { Check } from "./Setup";

const TABS = [
  ["models", "AI models"], ["hardware", "Hardware & processing"], ["storage", "Storage"],
  ["export", "Export"], ["privacy", "Privacy & devices"], ["logs", "Logs"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function SettingsPage() {
  const { local } = useSession();
  const toast = useApp((s) => s.toast);
  const [tab, setTab] = useState<Tab>("models");
  const [cfg, setCfg] = useState<any>(null);
  const status = usePoll<any>(() => api.get("/system/status"), tab === "hardware" ? 3000 : null, [tab]);
  useEffect(() => { api.get("/settings").then(setCfg).catch(toastError); }, []);

  async function save(values: Record<string, unknown>) {
    try { setCfg(await api.put("/settings", values)); } catch (e) { toastError(e); }
  }
  if (!cfg) return <Spinner />;
  const st = status.data;

  return (
    <div>
      <PageHeader title="Settings" />
      <div className="grid gap-4 md:grid-cols-[180px_1fr]">
        <nav className="flex gap-1 overflow-x-auto md:flex-col">
          {TABS.map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)}
              className={cx("h-8 shrink-0 rounded-md px-2.5 text-left text-[13px]", tab === id ? "bg-hover text-text" : "text-muted hover:text-text")}>{label}</button>
          ))}
        </nav>
        <div className="min-w-0 space-y-4">
          {tab === "models" && (
            <>
              <Panel title="Downloadable models"><div className="p-3"><ModelsPanel /></div></Panel>
              <LlmPanel cfg={cfg} save={save} />
            </>
          )}

          {tab === "hardware" && (
            <>
              <Panel title="Detected hardware" actions={<Button size="sm" icon={<RefreshCw size={13} />} onClick={() => api.get("/system/status?refresh=true").then(status.setData)}>Re-detect</Button>}>
                {!st ? <div className="p-4"><Spinner /></div> : (
                  <div className="space-y-3 p-3">
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      <Stat label="CPU threads" value={st.hardware.cpu_threads} />
                      <Stat label="RAM" value={`${st.hardware.memory.available_gb ?? "?"} / ${st.hardware.memory.total_gb ?? "?"} GB free`} />
                      <Stat label="ClipForge memory" value={`${st.hardware.memory.process_gb ?? "?"} GB`} />
                      <Stat label="CPU load" value={`${st.hardware.memory.cpu_percent ?? "?"}%`} />
                    </div>
                    <Check ok={st.hardware.gpus.length > 0} neutral label="GPU" detail={st.hardware.gpus.map((g: any) => `${g.name}${g.driver ? ` (driver ${g.driver})` : ""}`).join(", ") || "None detected"} />
                    <Check ok={!!st.hardware.hardware_encoder} neutral label="Hardware video encoder" detail={Object.entries(st.hardware.encoders).filter(([, v]) => v).map(([k]) => k).join(", ") || "none"} />
                    <Check ok neutral label="AI runtimes" detail={`ONNX Runtime providers: ${st.hardware.onnxruntime_providers.join(", ") || "not found"}. CUDA is ${st.hardware.cuda ? "available" : "not used"}.`} />
                    {st.hardware.notes.map((n: string) => <Notice key={n}>{n}</Notice>)}
                    <p className="text-[11px] text-faint">GPU memory and utilisation are not shown because there is no reliable cross-vendor way to read them; use Task Manager → Performance → GPU.</p>
                  </div>
                )}
              </Panel>
              <Panel title="Processing">
                <div className="grid gap-4 p-3 sm:grid-cols-2">
                  <Field label="Performance profile" hint="Performance: fewer frames inspected, fastest. Quality: denser frame and audio sampling, slowest.">
                    <Select value={cfg.performance_profile} onChange={(e) => save({ performance_profile: e.target.value })}
                      options={[{ value: "performance", label: "Performance" }, { value: "balanced", label: "Balanced" }, { value: "quality", label: "Quality" }]} />
                  </Field>
                  <Field label="CPU threads for AI" hint="0 = automatic (leaves one core free so the app stays responsive).">
                    <Input type="number" min={0} max={64} value={cfg.cpu_threads} onChange={(e) => save({ cpu_threads: Number(e.target.value) || 0 })} />
                  </Field>
                  <Field label="Video encoder" hint="Software (libx264) gives the most predictable quality. Hardware uses AMD AMF / NVENC / Quick Sync when the installed FFmpeg supports it, and falls back to software otherwise.">
                    <Select value={cfg.video_encoder} onChange={(e) => save({ video_encoder: e.target.value })}
                      options={[{ value: "auto", label: "Automatic (software)" }, { value: "software", label: "Software" }, { value: "hardware", label: "Hardware when available" }]} />
                  </Field>
                </div>
              </Panel>
              <Panel title="FFmpeg">
                <div className="space-y-3 p-3">
                  {st && <Check ok={st.tools.ffmpeg.found} label="FFmpeg" detail={st.tools.ffmpeg.found ? `${st.tools.ffmpeg.version} — ${st.tools.ffmpeg.path}` : st.tools.ffmpeg.error} />}
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="ffmpeg path (optional)"><TextSetting value={cfg.ffmpeg_path} placeholder="found automatically" onSave={(v) => save({ ffmpeg_path: v }).then(() => status.reload())} /></Field>
                    <Field label="ffprobe path (optional)"><TextSetting value={cfg.ffprobe_path} placeholder="found automatically" onSave={(v) => save({ ffprobe_path: v }).then(() => status.reload())} /></Field>
                  </div>
                </div>
              </Panel>
            </>
          )}

          {tab === "storage" && (
            <Panel title="Storage">
              <div className="space-y-4 p-3">
                <Field label="Export folder" hint={`Empty = ${status.data?.data_dir ?? "data folder"}/exports/<project>`}>
                  <TextSetting value={cfg.output_dir} placeholder="default" onSave={(v) => save({ output_dir: v })} />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Stat label="Data folder" value={<span className="font-mono text-[11px]">{status.data?.data_dir}</span>} />
                  <Stat label="Free space" value={status.data ? `${status.data.disk.free_gb} GB` : "–"} />
                </div>
                <Field label="Keep temporary files" row hint={undefined}>
                  <Toggle label="Keep temporary files" checked={cfg.keep_temp_files} onChange={(v) => save({ keep_temp_files: v })} />
                </Field>
                <p className="text-[11px] text-faint">Off (recommended): the extracted analysis audio and render work folders are deleted when a job finishes.</p>
                <Button onClick={() => api.post("/system/cleanup").then((r) => toast("ok", `Freed ${fmtBytes(r.freed_bytes)}.`)).catch(toastError)}>Delete temporary files now</Button>
                <p className="text-xs text-muted">To delete a project and its data, use Library → Delete.</p>
              </div>
            </Panel>
          )}

          {tab === "export" && (
            <Panel title="Export defaults">
              <div className="grid gap-4 p-3 sm:grid-cols-2">
                <Field label="Codec" hint="H.264 plays everywhere. H.265 is smaller but not accepted by every app.">
                  <Select value={cfg.export_codec} onChange={(e) => save({ export_codec: e.target.value })}
                    options={[{ value: "h264", label: "H.264 (MP4)" }, { value: "h265", label: "H.265 / HEVC (MP4)" }]} />
                </Field>
                <Field label="Quality">
                  <Select value={cfg.export_quality} onChange={(e) => save({ export_quality: e.target.value })}
                    options={[{ value: "draft", label: "Draft (fast, smaller)" }, { value: "standard", label: "Standard" }, { value: "high", label: "High" }]} />
                </Field>
              </div>
              <p className="px-3 pb-3 text-[11px] text-faint">Each clip can override these in the editor's Export panel.</p>
            </Panel>
          )}

          {tab === "privacy" && <PrivacyPanel cfg={cfg} save={save} local={local} />}
          {tab === "logs" && <LogsPanel />}
        </div>
      </div>
    </div>
  );
}

function TextSetting({ value, placeholder, onSave }: { value: string; placeholder?: string; onSave: (v: string) => void }) {
  const [v, setV] = useState(value ?? "");
  useEffect(() => setV(value ?? ""), [value]);
  return (
    <div className="flex gap-2">
      <Input value={v} placeholder={placeholder} onChange={(e) => setV(e.target.value)} />
      <Button disabled={v === (value ?? "")} onClick={() => onSave(v.trim())}>Save</Button>
    </div>
  );
}

function LlmPanel({ cfg, save }: { cfg: any; save: (v: Record<string, unknown>) => Promise<void> }) {
  const [url, setUrl] = useState(cfg.llm_base_url);
  const [model, setModel] = useState(cfg.llm_model);
  const [key, setKey] = useState("");
  const [test, setTest] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const isLocal = /^https?:\/\/(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[::1\])/i.test(url);
  async function run() {
    setBusy(true); setTest(null);
    try {
      await save({ llm_base_url: url.trim(), llm_model: model.trim(), ...(key ? { llm_api_key: key } : {}) });
      setTest(await api.post("/settings/llm-test"));
    } catch (e) { toastError(e); } finally { setBusy(false); }
  }
  return (
    <Panel title="Vision-language & context model (optional)">
      <div className="space-y-3 p-3">
        <p className="text-xs leading-relaxed text-muted">
          Adds frame descriptions (expressions, on-screen text, gameplay events) and conversation-level judgement. ClipForge talks to a model you run yourself through any OpenAI-compatible local server — llama.cpp <span className="font-mono">llama-server</span> (Vulkan build for AMD GPUs), LM Studio or Ollama. See MODEL_SETUP.md. Without it, clips are chosen from audio, motion, face and transcript signals.
        </p>
        <Field label="Use the local AI model" row><Toggle label="Use the local AI model" checked={cfg.llm_enabled} onChange={(v) => save({ llm_enabled: v })} /></Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Server address"><Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://127.0.0.1:8080/v1" /></Field>
          <Field label="Model name" hint="As listed by the server; may be empty for llama.cpp."><Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="qwen2.5-vl-7b" /></Field>
          <Field label="API key (only if your server needs one)" hint={cfg.llm_api_key ? "A key is saved. It is stored on this PC and never shown again." : "Stored on this PC only."}>
            <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={cfg.llm_api_key ? "••••••••" : ""} autoComplete="off" />
          </Field>
          <Field label="Model accepts images" row><Toggle label="Model accepts images" checked={cfg.llm_vision} onChange={(v) => save({ llm_vision: v })} /></Field>
        </div>
        {!isLocal && url && (
          <Notice tone="warn">This address is not on your computer or home network. Frames and transcripts would leave this PC. It stays blocked unless you turn on “Allow cloud AI” under Privacy &amp; devices.</Notice>
        )}
        <Button onClick={run} loading={busy}>Save and test connection</Button>
        {test && (test.ok
          ? <Notice tone="ok">Connected{test.local ? " (local)" : " (external service)"}. Models: {test.models.join(", ") || "not listed"}. Reply: “{test.reply}”.</Notice>
          : <Notice tone="danger">{test.error}</Notice>)}
      </div>
    </Panel>
  );
}

function PrivacyPanel({ cfg, save, local }: { cfg: any; save: (v: Record<string, unknown>) => Promise<void>; local: boolean }) {
  const [pair, setPair] = useState<any>(null);
  useEffect(() => { if (local) api.get("/settings/pairing").then(setPair).catch(() => setPair(null)); }, [local, cfg.lan_access]);
  return (
    <>
      <Panel title="Privacy">
        <div className="space-y-3 p-3">
          <div className="flex flex-wrap gap-1.5"><Badge tone="ok">Local processing</Badge><Badge tone="ok">No telemetry</Badge><Badge tone={cfg.allow_cloud_ai ? "warn" : "ok"}>{cfg.allow_cloud_ai ? "Cloud AI allowed" : "Cloud AI blocked"}</Badge></div>
          <p className="text-xs leading-relaxed text-muted">Videos, audio and transcripts are processed on this computer. ClipForge connects to the internet only when you download a model or import a link.</p>
          <Field label="Allow cloud AI" row><Toggle label="Allow cloud AI" checked={cfg.allow_cloud_ai} onChange={(v) => save({ allow_cloud_ai: v })} /></Field>
          <p className="text-[11px] text-faint">Only matters if you enter a non-local server address for the vision/context model. When on, sampled frames and transcript text are sent to that service.</p>
        </div>
      </Panel>
      <Panel title="Use ClipForge from your phone">
        <div className="space-y-3 p-3">
          <p className="text-xs leading-relaxed text-muted">Your phone can open this same studio in its browser over your home Wi-Fi. All processing still happens on this PC; the phone is a remote screen. Keep this off on networks you do not trust.</p>
          <Field label="Allow devices on my network" row><Toggle label="Allow devices on my network" disabled={!local} checked={cfg.lan_access} onChange={(v) => save({ lan_access: v })} /></Field>
          {!local && <p className="text-[11px] text-faint">This can only be changed on the PC itself.</p>}
          {cfg.lan_access && pair && (
            <div className="space-y-2 rounded-md border border-line bg-bg p-3">
              <p className="text-xs text-muted">1. Restart ClipForge once after turning this on. 2. On your phone, open:</p>
              <p className="font-mono text-sm text-text">http://{pair.ip ?? "<this PC's IP address>"}:8756</p>
              <p className="text-xs text-muted">3. Enter this PIN:</p>
              <p className="font-mono text-2xl tracking-[0.3em] text-accent">{pair.pin}</p>
              <p className="text-[11px] text-faint">If the page does not open, allow ClipForge (Python) through Windows Firewall for Private networks.</p>
            </div>
          )}
        </div>
      </Panel>
    </>
  );
}

function LogsPanel() {
  const logs = usePoll<{ text: string; path: string }>(() => api.get("/logs?lines=400"), 4000);
  const jobs = usePoll<any[]>(() => api.get("/jobs?limit=25"), 4000);
  return (
    <>
      <Panel title="Recent jobs">
        <ul className="divide-y divide-line">
          {(jobs.data ?? []).map((j) => (
            <li key={j.id} className="px-3 py-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="text-text">{j.type}{j.stage ? ` · ${j.stage.replace(/_/g, " ")}` : ""}</span>
                <Badge tone={j.status === "completed" ? "ok" : j.status === "failed" ? "danger" : j.status === "running" ? "accent" : "neutral"}>{j.status}</Badge>
              </div>
              {j.error && <p className="mt-1 break-words text-danger">{j.error}</p>}
              {j.result?.warnings?.map((w: string) => <p key={w} className="mt-1 text-warn">{w}</p>)}
            </li>
          ))}
          {!jobs.data?.length && <li className="px-3 py-4 text-xs text-muted">No jobs have run yet.</li>}
        </ul>
      </Panel>
      <Panel title="Application log" actions={<Button size="sm" onClick={() => navigator.clipboard?.writeText(logs.data?.text ?? "")}>Copy</Button>}>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-[11px] leading-relaxed text-muted">{logs.data?.text || "The log is empty."}</pre>
        <p className="border-t border-line px-3 py-2 font-mono text-[11px] text-faint">{logs.data?.path}</p>
      </Panel>
    </>
  );
}
