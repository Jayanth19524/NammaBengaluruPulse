import { Pool } from "pg";
import fs from "fs";
import path from "path";

const MIGRATIONS_DIR = path.join(__dirname, "migrations");
const SEEDS_DIR = path.join(__dirname, "seeds");

export async function runMigrations(pool: Pool): Promise<void> {
  // Ensure migrations tracking table exists
  await pool.query(`
    CREATE TABLE IF NOT EXISTS _migrations (
      id         SERIAL PRIMARY KEY,
      filename   TEXT UNIQUE NOT NULL,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `);

  const files = fs
    .readdirSync(MIGRATIONS_DIR)
    .filter((f) => f.endsWith(".sql"))
    .sort();

  for (const file of files) {
    const { rows } = await pool.query(
      "SELECT id FROM _migrations WHERE filename = $1",
      [file]
    );
    if (rows.length > 0) continue; // already applied

    const sql = fs.readFileSync(path.join(MIGRATIONS_DIR, file), "utf8");
    console.log(`[db] Applying migration: ${file}`);
    await pool.query(sql);
    await pool.query("INSERT INTO _migrations (filename) VALUES ($1)", [file]);
    console.log(`[db] Migration applied: ${file}`);
  }
}

export async function runSeeds(pool: Pool): Promise<void> {
  const { rows } = await pool.query(
    "SELECT id FROM _migrations WHERE filename = $1",
    ["seeds_waterwatch_demo"]
  );
  if (rows.length > 0) {
    console.log("[db] Seeds already applied, skipping.");
    return;
  }

  const seedFile = path.join(SEEDS_DIR, "waterwatch_demo.sql");
  if (!fs.existsSync(seedFile)) return;

  const sql = fs.readFileSync(seedFile, "utf8");
  console.log("[db] Applying demo seed data...");
  await pool.query(sql);
  await pool.query("INSERT INTO _migrations (filename) VALUES ($1)", [
    "seeds_waterwatch_demo",
  ]);
  console.log("[db] Demo seed data applied.");
}
