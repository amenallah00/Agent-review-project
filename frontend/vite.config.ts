import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Proxies API/auth/webhook calls to the FastAPI backend during `npm run dev`
// (port 8000 by default — override with VITE_BACKEND_URL). In production the
// built bundle (`npm run build` -> dist/) is served directly by FastAPI, so
// no proxy is involved there — see app/main.py.
const BACKEND = process.env.VITE_BACKEND_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": BACKEND,
      "/auth": BACKEND,
      "/webhook": BACKEND,
      "/health": BACKEND,
    },
  },
  build: {
    outDir: "dist",
  },
});
