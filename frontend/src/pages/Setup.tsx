import { CheckCircle2, Cpu, HardDrive, ShieldCheck, XCircle } from "lucide-react";
import { useState } from "react";
import { ModelsPanel } from "../components/ModelsPanel";
import { Button, Field, Input, Notice, Spinner, cx } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api } from "../lib/api";
import { toastError } from "../store";

const STEPS = ["Welcome", "Environment", "AI models", "Storage"];

/** First-run setup: explains local processing, verifies the environment, and lets the user choose models. */
export default function Setup({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const status = usePoll<any>(() => api.get(`/system/status${step === 1 ? "?refresh=true" : ""}`), step === 2 ? 2000 : null, [step]);
  const st = status.data;
  const [outDir, setOutDir] = useState("");
  const [ffmpegPath, setFfmpegPath] = useState("");
  const [saving, setSaving] = useState(false);

  async function finish() {
    setSaving(true);
    try {
      await api.put("/settings", { setup_complete: true, ...(outDir.trim() ? { output_dir: outDir.trim() } : {}) });
      onDone();
    } catch (e) { toastError(e); } finally { setSaving(false); }
  }
  async function saveFfmpeg() {
    try {
      const dir = ffmpegPath.trim();  // the backend accepts either the folder or the executable itself
      await api.put("/settings", { ffmpeg_path: dir, ffprobe_path: dir.replace(/ffmpeg(\.exe)?$/i, "ffprobe$1") });
      status.reload();
    } catch (e) { toastError(e); }
  }
  const toolsOk = st?.tools.ffmpeg.found && st?.tools.ffprobe.found;

  return (
    <div className="flex h-full items-start justify-center overflow-y-auto p-4 sm:items-center">
      <div className="w-full max-w-2xl rounded-lg border border-line bg-surface">
        <ol className="flex border-b border-line">
          {STEPS.map((s, i) => (
            <li key={s} className={cx("flex-1 border-b-2 px-2 py-2.5 text-center text-xs font-medium", i === step ? "border-accent text-text" : i < step ? "border-transparent text-ok" : "border-transparent text-faint")}>
              <span className="hidden sm:inline">{i + 1}. </span>{s}
            </li>
          ))}
        </ol>
        <div className="space-y-4 p-5">
          {step === 0 && (
            <>
              <h1 className="text-xl font-semibold tracking-tight">Welcome to ClipForge AI</h1>
              <p className="text-[13px] leading-relaxed text-muted">ClipForge watches and listens to your long videos, finds the moments worth sharing, and turns them into captioned short clips.</p>
              <div className="space-y-2.5">
                <Point icon={<ShieldCheck size={16} />} title="Everything runs on this computer">Your videos, audio and transcripts are processed locally. Nothing is uploaded, and there is no telemetry. Cloud AI is off and can only be turned on by you.</Point>
                <Point icon={<Cpu size={16} />} title="Works without an NVIDIA GPU">Speech and audio models run on your CPU. An optional vision-language model can use an AMD, Intel or NVIDIA GPU through a local server you control.</Point>
                <Point icon={<HardDrive size={16} />} title="You choose what gets downloaded">AI models are only downloaded when you press Download, and each one shows its size and license first.</Point>
              </div>
            </>
          )}
          {step === 1 && (
            <>
              <h1 className="text-base font-semibold">Environment check</h1>
              {!st ? <Spinner /> : (
                <div className="space-y-2">
                  <Check ok={st.tools.ffmpeg.found} label="FFmpeg" detail={st.tools.ffmpeg.version ?? st.tools.ffmpeg.error} />
                  <Check ok={st.tools.ffprobe.found} label="FFprobe" detail={st.tools.ffprobe.version ?? st.tools.ffprobe.error} />
                  {!toolsOk && (
                    <Notice tone="warn">
                      FFmpeg is required. On Windows run <code className="font-mono">winget install Gyan.FFmpeg</code> in a terminal and restart ClipForge, or enter the folder that contains ffmpeg.exe:
                      <div className="mt-2 flex gap-2"><Input placeholder="C:\ffmpeg\bin" value={ffmpegPath} onChange={(e) => setFfmpegPath(e.target.value)} /><Button onClick={saveFfmpeg} disabled={!ffmpegPath.trim()}>Use</Button></div>
                    </Notice>
                  )}
                  <Check ok label="Processor" detail={`${st.hardware.cpu} · ${st.hardware.cpu_threads} threads · ${st.hardware.memory.total_gb ?? "?"} GB RAM`} />
                  <Check ok={st.hardware.gpus.length > 0} neutral label="Graphics" detail={st.hardware.gpus.length ? st.hardware.gpus.map((g: any) => g.name).join(", ") : "No GPU detected — the CPU will be used"} />
                  <Check ok={!!st.hardware.hardware_encoder} neutral label="Hardware video encoding" detail={st.hardware.hardware_encoder ? `${st.hardware.hardware_encoder} is available` : "Not available in this FFmpeg build — software encoding (libx264) will be used"} />
                  <Check ok={st.disk.free_gb > 10} label="Free disk space" detail={`${st.disk.free_gb} GB free in ${st.data_dir}`} />
                  {st.hardware.notes.map((n: string) => <Notice key={n}>{n}</Notice>)}
                  <Button size="sm" onClick={() => status.reload()}>Check again</Button>
                </div>
              )}
            </>
          )}
          {step === 2 && (
            <>
              <h1 className="text-base font-semibold">Choose AI models</h1>
              <p className="text-xs leading-relaxed text-muted">These four are the recommended starting set (about 670 MB in total). A speech model is required to analyze videos with talking; the others improve results and can be added later in Settings, where larger and more accurate models are also listed.</p>
              <ModelsPanel onlyIds={st?.recommended_models} onChange={status.reload} />
              {st && !st.models_ready.asr && <Notice tone="warn">No speech model is installed yet. You can continue, but analysis of videos with speech will ask you to install one.</Notice>}
            </>
          )}
          {step === 3 && (
            <>
              <h1 className="text-base font-semibold">Storage</h1>
              <Field label="Where exported clips are saved" hint={`Leave empty to use ${st?.output_dir ?? "the default folder"}`}>
                <Input placeholder={st?.output_dir} value={outDir} onChange={(e) => setOutDir(e.target.value)} />
              </Field>
              <p className="text-xs leading-relaxed text-muted">Projects, transcripts and models are stored in <span className="font-mono text-[11px] text-text">{st?.data_dir}</span>. Imported videos are used where they are; only uploads and link imports are copied into that folder.</p>
            </>
          )}
        </div>
        <footer className="flex justify-between border-t border-line px-5 py-3">
          <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
          {step < STEPS.length - 1
            ? <Button variant="primary" onClick={() => setStep(step + 1)} disabled={step === 1 && !toolsOk}>Continue</Button>
            : <Button variant="primary" loading={saving} onClick={finish}>Open ClipForge</Button>}
        </footer>
      </div>
    </div>
  );
}

function Point({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 rounded-md border border-line bg-bg p-3">
      <div className="mt-0.5 text-accent">{icon}</div>
      <div><p className="text-[13px] font-medium">{title}</p><p className="mt-0.5 text-xs leading-relaxed text-muted">{children}</p></div>
    </div>
  );
}

export function Check({ ok, label, detail, neutral }: { ok: boolean; label: string; detail?: string; neutral?: boolean }) {
  return (
    <div className="flex items-start gap-2.5 rounded-md border border-line bg-bg px-3 py-2">
      {ok ? <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-ok" /> : <XCircle size={15} className={cx("mt-0.5 shrink-0", neutral ? "text-faint" : "text-danger")} />}
      <div className="min-w-0"><p className="text-[13px]">{label}</p>{detail && <p className="break-words text-[11px] text-muted">{detail}</p>}</div>
    </div>
  );
}
