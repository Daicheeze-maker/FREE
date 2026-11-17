export type Json = Record<string, any>;

export interface Source {
  id: string; project_id: string; path: string; filename: string; origin: string; origin_url: string | null;
  size_bytes: number; duration: number; width: number; height: number; fps: number;
  video_codec: string | null; audio_codec: string | null; has_audio: boolean;
  sample_rate: number | null; channels: number | null; bitrate: number | null; proxy_path: string | null;
}
export interface Job {
  id: string; type: string; project_id: string | null; clip_id: string | null; status: string;
  stage: string | null; progress: number; stage_progress: number; message: string | null; error: string | null;
  params: Json; result: Json; completed_stages: string[]; eta_seconds: number | null;
  created_at: string; started_at: string | null; finished_at: string | null;
}
export interface Project {
  id: string; name: string; status: string; settings: Json; notice: string | null;
  created_at: string; updated_at: string; source: Source | null; clip_count: number; export_count: number;
  active_job: Job | null; source_missing: boolean;
  transcript?: { language: string | null; provider: string; model: string; word_timing: string } | null;
  last_analysis?: Job | null; counts?: { segments: number; scenes: number; events: number };
}
export interface Candidate {
  id: string; project_id: string; rank: number; title: string; start: number; end: number; duration: number;
  category: string; score: number; confidence: number; reason: string; scores: Record<string, number>;
  transcript_text: string; status: string; source: string; low_confidence: boolean;
  clip_id: string | null; exports: number; aspect?: string;
}
export interface Word { w: string; start: number; end: number }
export interface Cue { id: string; start: number; end: number; text: string; speaker: string; words: Word[] }
export interface CaptionStyle {
  preset: string; font: string; weight: number; size: number; color: string; highlight_color: string;
  outline_color: string; outline: number; shadow: number; background: boolean; background_color: string;
  background_opacity: number; position_y: number; align: "left" | "center" | "right"; max_words: number;
  uppercase: boolean; animation: "none" | "fade" | "pop"; highlight: "none" | "word" | "single";
  safe_margin: number; speaker_labels: boolean;
}
export interface ExportSettings {
  preset: string; resolution: string; fps: string | number; codec: string; quality: string; video_bitrate: number;
  audio_bitrate: number; normalize: boolean; burn_captions: boolean; sidecar_srt: boolean; sidecar_vtt: boolean;
  filename: string; output_dir: string;
}
export interface Clip {
  id: string; project_id: string; candidate_id: string | null; title: string; start: number; end: number;
  aspect: string; crop_mode: string; crop: { x: number; y: number; zoom: number }; volume: number; mute: boolean;
  music_path: string | null; music_volume: number; captions_enabled: boolean; style: CaptionStyle;
  export_settings: ExportSettings;
}
export interface ExportRow {
  id: string; clip_id: string; project_id: string; job_id: string; path: string | null; status: string;
  settings: Json; validation: { ok?: boolean; checks?: { name: string; ok: boolean; detail: string }[]; info?: Json };
  size_bytes: number | null; duration: number | null; created_at: string; title?: string; exists?: boolean;
}
export interface CropPlan {
  mode: string; effective: string; box: [number, number]; keys: [number, number, number][]; note: string; cuts?: number[];
}
export interface ModelInfo {
  id: string; name: string; version: string; purpose: string; provider: string; description: string;
  size_bytes: number; ram_gb: number; runtime: string; license: string; license_url: string; compat: string;
  timing?: string; status: string; bytes_done: number; bytes_total: number; verified_at: string | null;
  error: string | null; active: boolean; selected: boolean;
}
export interface Meta {
  categories: Record<string, string>; score_labels: Record<string, string>;
  caption_presets: Record<string, CaptionStyle>; fonts: Record<string, number[]>;
  platform_presets: Record<string, Json>; export_defaults: ExportSettings; analysis_defaults: Json;
  stages: { id: string; label: string }[]; video_extensions: string[]; profiles: string[];
}
export interface TimelineData {
  events: { id: string; kind: string; modality: string; start: number; end: number; intensity: number; label: string }[];
  scenes: { start: number; end: number }[]; peaks: number[];
}
