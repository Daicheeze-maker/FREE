import { create } from "zustand";
import type { Meta } from "./lib/types";

export interface Toast { id: number; kind: "ok" | "error" | "info"; text: string }

interface AppState {
  meta: Meta | null;
  setMeta: (m: Meta) => void;
  toasts: Toast[];
  toast: (kind: Toast["kind"], text: string) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;
export const useApp = create<AppState>((set, get) => ({
  meta: null,
  setMeta: (meta) => set({ meta }),
  toasts: [],
  toast: (kind, text) => {
    const id = nextId++;
    set({ toasts: [...get().toasts, { id, kind, text }] });
    setTimeout(() => get().dismiss(id), kind === "error" ? 8000 : 4000);
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}));

export const toastError = (e: unknown) => useApp.getState().toast("error", e instanceof Error ? e.message : String(e));
