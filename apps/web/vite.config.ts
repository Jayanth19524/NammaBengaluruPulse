import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api/* is proxied to the RoadTrust FastAPI service.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: process.env.ROADTRUST_URL ?? "http://localhost:8002", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
