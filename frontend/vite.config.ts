import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: Vite on :5173 proxies API + WebSocket to FastAPI on :8000.
// Build: output goes straight into backend/static so FastAPI serves it.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: { outDir: "../backend/static", emptyOutDir: true },
});
