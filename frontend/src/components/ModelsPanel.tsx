import { Check, Download, Pause, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { usePoll } from "../hooks/usePoll";
import { api } from "../lib/api";
import { fmtBytes, fmtDate } from "../lib/format";
import type { ModelInfo } from "../lib/types";
import { toastError, useApp } from "../store";
import { Badge, Button, Notice, Progress, Spinner } from "./ui";

const PURPOSE: Record<string, string> = {
  asr: "Speech recognition", audio_tagging: "Audio event detection", vad: "Speech segmentation", face: "Face detection",
};

/** Model manager: nothing downloads unless the user presses Download. */
export function ModelsPanel({ onlyIds, onChange }: { onlyIds?: string[]; onChange?: () => void }) {
  const toast = useApp((s) => s.toast);
  const { data, reload } = usePoll<{ models: ModelInfo[]; external: any[]; models_dir: string }>(() => api.get("/models"), 1500);
  const [busy, setBusy] = useState<string | null>(null);
  if (!data) return <div className="flex justify-center p-6"><Spinner /></div>;

  const act = async (id: string, fn: () => Promise<any>, okMsg?: string) => {
    setBusy(id);
    try { await fn(); if (okMsg) toast("ok", okMsg); await reload(); onChange?.(); } catch (e) { toastError(e); await reload(); } finally { setBusy(null); }
  };
  const groups = Object.keys(PURPOSE).map((p) => ({ purpose: p, models: data.models.filter((m) => m.purpose === p && (!onlyIds || onlyIds.includes(m.id))) })).filter((g) => g.models.length);

  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <div key={g.purpose}>
          <h3 className="mb-1.5 text-xs font-semibold text-text">{PURPOSE[g.purpose]}</h3>
          <ul className="divide-y divide-line rounded-md border border-line">
            {g.models.map((m) => (
              <li key={m.id} className="space-y-2 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[13px] font-medium">{m.name}</span>
                      <span className="text-[11px] text-faint">{m.version}</span>
                      {m.status === "installed" && <Badge tone="ok">installed</Badge>}
                      {m.active && <Badge tone="accent">in use</Badge>}
                      {m.status === "paused" && <Badge tone="warn">paused</Badge>}
                      {m.status === "error" && <Badge tone="danger">error</Badge>}
                      {m.timing === "word" && <Badge tone="info">word-level timing</Badge>}
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-muted">{m.description}</p>
                    <p className="tnum mt-1 text-[11px] text-faint">
                      {fmtBytes(m.size_bytes)} download · ~{m.ram_gb} GB RAM · {m.runtime} · {m.compat}
                    </p>
                    <p className="text-[11px] text-faint">
                      License: <a className="underline hover:text-text" href={m.license_url} target="_blank" rel="noreferrer">{m.license}</a>
                      {m.verified_at && <> · verified {fmtDate(m.verified_at)}</>}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-1.5">
                    {(m.status === "not_installed" || m.status === "error") &&
                      <Button size="sm" variant="primary" icon={<Download size={13} />} loading={busy === m.id}
                        onClick={() => act(m.id, () => api.post(`/models/${m.id}/download`))}>Download {fmtBytes(m.size_bytes)}</Button>}
                    {m.status === "paused" &&
                      <Button size="sm" variant="primary" icon={<Download size={13} />} onClick={() => act(m.id, () => api.post(`/models/${m.id}/download`))}>Resume</Button>}
                    {m.status === "downloading" &&
                      <Button size="sm" icon={<Pause size={13} />} onClick={() => act(m.id, () => api.post(`/models/${m.id}/pause`))}>Pause</Button>}
                    {m.status === "installed" && !m.active && SELECTABLE.includes(m.purpose) &&
                      <Button size="sm" icon={<Check size={13} />} onClick={() => act(m.id, () => api.post(`/models/${m.id}/select`), `${m.name} is now in use.`)}>Use</Button>}
                    {m.status === "installed" &&
                      <Button size="sm" variant="ghost" icon={<ShieldCheck size={13} />} loading={busy === m.id + "v"}
                        onClick={async () => { setBusy(m.id + "v"); try { await api.post(`/models/${m.id}/verify`); toast("ok", `${m.name} loaded and ran a test inference.`); } catch (e) { toastError(e); } finally { setBusy(null); reload(); } }}>Verify</Button>}
                    {(m.status === "installed" || m.status === "paused") &&
                      <Button size="sm" variant="ghost" icon={<Trash2 size={13} />} onClick={() => act(m.id, () => api.del(`/models/${m.id}`), "Model removed.")}>Remove</Button>}
                  </div>
                </div>
                {m.status === "downloading" && (
                  <div className="space-y-1">
                    <Progress value={m.bytes_total ? m.bytes_done / m.bytes_total : 0} />
                    <p className="tnum text-[11px] text-faint">{fmtBytes(m.bytes_done)} of {fmtBytes(m.bytes_total)}</p>
                  </div>
                )}
                {m.error && <Notice tone="danger">{m.error}</Notice>}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {!onlyIds && <p className="font-mono text-[11px] text-faint">Models folder: {data.models_dir}</p>}
    </div>
  );
}

const SELECTABLE = ["asr", "audio_tagging", "face"];
