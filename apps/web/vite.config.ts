import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api/* is proxied to the RoadTrust FastAPI service.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/flood": { target: process.env.FLOODLENS_URL ?? "http://127.0.0.1:8005", changeOrigin: true, rewrite: (p) => p.replace(/^\/flood/, "") },
      "/orch": { target: process.env.ORCHESTRATOR_URL ?? "http://127.0.0.1:8004", changeOrigin: true, rewrite: (p) => p.replace(/^\/orch/, "") },
      "/trip": { target: process.env.TRIPCAST_URL ?? "http://127.0.0.1:8003", changeOrigin: true, rewrite: (p) => p.replace(/^\/trip/, "") },
      "/api": { target: process.env.ROADTRUST_URL ?? "http://127.0.0.1:8002", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
