/* Record the full app flow as a sharp video using a real Chrome (Playwright).
 *   npm i playwright-core        (anywhere; e.g. in a temp folder)
 *   NODE_PATH=<that>/node_modules node scripts/record_walkthrough.cjs [--url http://127.0.0.1:5173] [--out docs]
 * Needs the web dev server and the services running, plus Google Chrome and ffmpeg. */
const { chromium } = require("playwright-core");
const { execFileSync } = require("child_process");
const fs = require("fs");
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const URL = arg("--url", "http://127.0.0.1:5173"), OUT = arg("--out", "docs");
const W = 1440, H = 900;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function seed() { // two clearly labelled demo reports so the flow has something to show
  const f = new FormData();
  [["lat", "12.91775"], ["lon", "77.6238"], ["kind", "pothole"], ["severity", "high"], ["reporter_id", "demo-walkthrough"], ["description", "Demo walkthrough report"]].forEach(([k, v]) => f.set(k, v));
  await fetch("http://127.0.0.1:8002/reports", { method: "POST", body: f }).catch(() => {});
  await fetch("http://127.0.0.1:8005/reports", { method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ lat: 12.9315, lon: 77.6265, reporter_id: "demo-walkthrough", note: "Demo walkthrough report" }) }).catch(() => {});
}

(async () => {
  await seed();
  const browser = await chromium.launch({ channel: "chrome", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, recordVideo: { dir: "/tmp/np-video", size: { width: W, height: H } } });
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    window.addEventListener("DOMContentLoaded", () => {
      const c = document.createElement("div");
      c.id = "fakecursor";
      c.style.cssText = "position:fixed;z-index:99999;width:18px;height:18px;border-radius:50%;background:rgba(91,155,255,.55);border:2px solid #fff;pointer-events:none;transform:translate(-50%,-50%);left:-50px;top:-50px;transition:left .02s,top .02s";
      const cap = document.createElement("div");
      cap.id = "cap";
      cap.style.cssText = "position:fixed;z-index:99998;left:0;right:0;bottom:0;height:52px;box-sizing:border-box;padding:13px 28px;background:#111;color:#fff;font:500 20px Inter,system-ui,sans-serif;pointer-events:none";
      const st = document.createElement("style");
      st.textContent = ".app{height:calc(100dvh - 52px)!important} .arch{bottom:0}";   // leave room so the caption bar covers nothing
      document.head.append(st);
      document.body.append(c, cap);
      window.addEventListener("mousemove", (e) => { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }, true);
    });
  });
  const caption = (t) => page.evaluate((t) => { const c = document.getElementById("cap"); if (c) c.textContent = t; }, t);
  const click = async (loc) => {
    const b = await loc.boundingBox();
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 25 });
    await sleep(250); await page.mouse.down(); await page.mouse.up();
  };
  const tab = (n) => page.getByRole("tab", { name: n, exact: true });
  const clickAt = async (x, y) => { await page.mouse.move(x, y, { steps: 30 }); await sleep(200); await page.mouse.down(); await page.mouse.up(); };

  await page.goto(URL); await page.waitForLoadState("networkidle").catch(() => {});
  await caption("NammaPulse: a 3D map of road incidents on the routes you watch"); await sleep(6000);

  await caption("Open an incident: reported by the community, not verified, with advice");
  await click(page.locator(".row").first()); await sleep(5000);

  await caption("Trip planner: pick a start and end on the map");
  await click(tab("Trip")); await sleep(800);
  await click(page.getByRole("button", { name: "Set on map" }).first()); await clickAt(820, 560); await sleep(500); await clickAt(1130, 330); await sleep(800);
  await caption("Real road route, expected time (with traffic building along the way) and best time to leave");
  await click(page.getByRole("button", { name: "Find routes" })); await sleep(10000);

  await caption("Watch this trip, then Alerts: nothing on it needs attention, so no alert");
  await click(page.getByRole("button", { name: "Watch this trip" })); await click(tab("Alerts")); await sleep(14000);
  await caption("The demo commute passes a reported pothole: an alert, with the reasons");
  await click(page.getByRole("button", { name: "Remove" })); await sleep(500);
  await click(page.getByRole("button", { name: "Run check now" })); await sleep(18000);
  await page.getByText("Why am I seeing this?").first().click().catch(() => {}); await sleep(3500);
  await page.getByText(/Decision log/).click().catch(() => {}); await sleep(1200);
  await page.locator(".panel-body").evaluate((e) => e.scrollTo({ top: 99999, behavior: "smooth" })); await sleep(5000);

  await caption("FloodLens: real elevation and rainfall forecast; no rain today, but a reported waterlogging spot still shows");
  await click(tab("Flood")); await sleep(16000);
  await caption("What-if heavy rain (a scenario, not a forecast): predicted flood areas in 3D");
  await click(page.getByLabel(/What-if/)); await sleep(500);
  await click(page.getByRole("button", { name: "Run FloodLens" })); await sleep(15000);
  await click(page.getByRole("button", { name: "View on map" }).first()); await sleep(5000);

  await caption("Live architecture: replays FloodLens's real run step by step");
  await click(tab("Architecture")); await sleep(16000);

  await caption("RoadTrust agent: live log and the health of each data source");
  await click(tab("Agent")); await sleep(7000);

  const vid = await page.video().path();
  await ctx.close(); await browser.close();
  fs.mkdirSync(OUT, { recursive: true });
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-i", vid, "-c:v", "libx264", "-crf", "24", "-preset", "slow", "-pix_fmt", "yuv420p", `${OUT}/nammapulse-walkthrough.mp4`]);
  console.log("wrote", `${OUT}/nammapulse-walkthrough.mp4`);
})().catch((e) => { console.error(e); process.exit(1); });
