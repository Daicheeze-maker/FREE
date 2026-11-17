import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";

// In development the UI runs on :5173 and proxies API calls to the Python backend.
export default defineConfig({
  plugins: [react(), tailwind()],
  server: { port: 5173, proxy: { "/api": { target: "http://127.0.0.1:8756", changeOrigin: false } } },
  build: { outDir: "dist", sourcemap: false },
});
