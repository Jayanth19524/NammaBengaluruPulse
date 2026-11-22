import dotenv from "dotenv";
dotenv.config();

import express from "express";
import cors from "cors";
import rateLimit from "express-rate-limit";

import { pool } from "./db/pool";
import { runMigrations, runSeeds } from "./db/migrate";
import { scanRouter } from "./routes/water/scan";
import { incidentsRouter } from "./routes/water/incidents";
import { reportRouter } from "./routes/water/report";
import { sensorRouter } from "./routes/water/sensor";
import { notificationsRouter } from "./routes/notifications";
import { log } from "./core/logger";

const PORT = parseInt(process.env.PORT ?? "4000", 10);
const CORS_ORIGIN = process.env.CORS_ORIGIN ?? "http://localhost:5173";

const app = express();

// --- Middleware ---
app.use(cors({ origin: CORS_ORIGIN }));
app.use(express.json());

const limiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 60,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests, please slow down." },
});
app.use("/api", limiter);

// --- Routes ---
app.use("/api/water/scan", scanRouter);
app.use("/api/water/incidents", incidentsRouter);
app.use("/api/water/report", reportRouter);
app.use("/api/water/sensor", sensorRouter);
app.use("/api/notifications", notificationsRouter);

// SSE stream for live incident updates
app.get("/api/water/stream", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  // Keep-alive ping every 15 s
  const ping = setInterval(() => res.write("event: ping\ndata: {}\n\n"), 15000);
  req.on("close", () => clearInterval(ping));
});

// Health
app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "nammapulse-api" });
});

// 404 fallback
app.use((_req, res) => {
  res.status(404).json({ error: "Not found" });
});

// --- Startup ---
async function start(): Promise<void> {
  try {
    await runMigrations(pool);
    await runSeeds(pool);
  } catch (err: unknown) {
    log("warn", "[startup] DB migration/seed error — continuing without DB", {
      err: String(err),
    });
  }

  app.listen(PORT, () => {
    log("info", `[api] NammaPulse API listening on http://localhost:${PORT}`);
  });
}

start();
