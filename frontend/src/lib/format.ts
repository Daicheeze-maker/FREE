export function fmtTime(t: number, withMs = false): string {
  if (!isFinite(t)) return "–";
  const s = Math.max(0, t);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  const ss = withMs ? sec.toFixed(1).padStart(4, "0") : String(Math.floor(sec)).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}
export function fmtDuration(t: number): string {
  if (t < 60) return `${t.toFixed(t < 10 ? 1 : 0)}s`;
  return fmtTime(t);
}
export function fmtBytes(n: number | null | undefined): string {
  if (n == null) return "–";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${u[i]}`;
}
export function fmtEta(s: number | null | undefined): string {
  if (s == null || !isFinite(s)) return "";
  if (s < 60) return `about ${Math.max(1, Math.round(s))}s left`;
  return `about ${Math.round(s / 60)} min left`;
}
export function fmtDate(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
export const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
export const LANG_NAMES: Record<string, string> = { en: "English", tl: "Tagalog / Filipino", es: "Spanish", ja: "Japanese", ko: "Korean", zh: "Chinese" };
