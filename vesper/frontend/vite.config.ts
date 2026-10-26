import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The browser only ever talks to /api; Vite forwards it to FastAPI. No secrets reach the client.
  server: { proxy: { "/api": "http://localhost:8000" } },
  preview: { proxy: { "/api": "http://localhost:8000" } },
  test: { globals: true, environment: "jsdom", setupFiles: ["./src/test-setup.ts"] },
});
