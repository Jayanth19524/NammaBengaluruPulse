"""Render the live-architecture animation as MP4 + GIF from a REAL FloodLens run.

It calls the running services (FloodLens /investigate with the what-if preset, and each service's /health), turns the
run's own trace into steps, and animates the same diagram as the app's Architecture tab: flowing data along the active
edges, a travelling packet, pulsing nodes, a typed caption and a progress bar. Nothing is typed in by hand.

    python scripts/render_architecture_video.py [--host http://127.0.0.1] [--out docs]
Needs Pillow and ffmpeg. FloodLens (8005) must be running; the other services (8002-8004) only feed the status dots.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

W1, H1 = 1600, 1000                 # output size
SS = 2                              # supersampling
U = SS * W1 / 1200                  # diagram unit -> pixels (1200 x 620 diagram viewBox)
TOP = 64 * SS                       # top bar height
FPS = 25
STEP_S, INTRO_S, OUTRO_S = 2.8, 1.6, 2.4

BG, SURF, BORDER = (14, 16, 19), (21, 24, 28), (42, 47, 54)
TEXT, TEXT2, TEXT3 = (232, 234, 237), (160, 167, 176), (114, 122, 133)
ACCENT, OK, BAD = (91, 155, 255), (47, 158, 91), (209, 43, 43)

HELV, MENLO = "/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Menlo.ttc"
def font(path, size, idx=0):
    return ImageFont.truetype(path, int(size), index=idx)
F_TT, F_SS, F_TAG = font(HELV, 12.5 * U, 1), font(HELV, 10.5 * U), font(MENLO, 8.5 * U)
F_COL, F_BAR, F_CAP, F_CAPS = font(HELV, 11 * U, 1), font(HELV, 15 * U, 1), font(HELV, 16 * U), font(MENLO, 11 * U)

# id: (x, y, w, h, title, tag)  -- keep identical to apps/web/src/screens/Architecture.tsx
NODES = {
    "routes": (24, 70, 210, 66, "Monitored routes", "INPUT"),
    "forecast": (24, 160, 210, 66, "Rainfall forecast", "INPUT · OPEN-METEO"),
    "elevation": (24, 250, 210, 66, "Terrain elevation", "INPUT · OPEN-METEO DEM"),
    "reports": (24, 340, 210, 66, "Community reports", "INPUT"),
    "model": (330, 160, 210, 66, "Flood-risk model", "FLOODLENS · DETERMINISTIC"),
    "grid": (330, 250, 210, 66, "Terrain grid & relief", "FLOODLENS"),
    "cluster": (330, 340, 210, 66, "Areas touching routes", "FLOODLENS"),
    "agent": (630, 70, 230, 66, "Language-model agent", "FLOODLENS · LLM + TOOLS"),
    "guard": (630, 340, 230, 66, "Completeness guard", "FLOODLENS · POLICY"),
    "map": (930, 160, 246, 66, "3D flood map", "OUTPUT"),
    "findings": (930, 340, 246, 66, "Findings & advice", "OUTPUT"),
    "orch": (930, 450, 246, 66, "Orchestrator", "LANGGRAPH · ALERT POLICY"),
    "roadtrust": (630, 450, 230, 56, "RoadTrust", "OTHER AGENT"),
    "tripcast": (630, 520, 230, 56, "TripCast", "OTHER AGENT"),
}
EDGES = [("elevation", "grid"), ("forecast", "model"), ("reports", "model"), ("grid", "model"), ("model", "cluster"),
         ("routes", "cluster"), ("agent", "model"), ("cluster", "guard"), ("agent", "guard"), ("model", "map"),
         ("guard", "findings"), ("findings", "orch"), ("roadtrust", "orch"), ("tripcast", "orch")]
SVC = {"model": "FloodLens", "grid": "FloodLens", "cluster": "FloodLens", "guard": "FloodLens", "agent": "FloodLens",
       "roadtrust": "RoadTrust", "tripcast": "TripCast", "orch": "Orchestrator"}
ALWAYS = {"map", "findings", "orch", "roadtrust", "tripcast"}


def http(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def to_step(t):
    k, m = t["kind"], t["message"].lower()
    if k == "fetch" and "rainfall" in m: return (["forecast", "model"], [("forecast", "model")])
    if k == "fetch": return (["elevation", "grid"], [("elevation", "grid")])
    if k in ("scenario", "forecast"): return (["forecast", "model"], [("forecast", "model")])
    if k == "terrain": return (["grid", "model", "reports"], [("grid", "model"), ("reports", "model")])
    if k == "assess": return (["model", "cluster", "routes"], [("model", "cluster"), ("routes", "cluster")])
    if k == "done": return (["cluster", "guard", "findings", "map", "model"], [("cluster", "guard"), ("guard", "findings"), ("model", "map")])
    if k in ("agent_tool_call", "agent_tool_result"): return (["agent", "model"], [("agent", "model")])
    if k == "agent_reasoning": return (["agent"], [])
    if k == "agent_final": return (["agent", "guard"], [("agent", "guard")])
    if k == "agent_policy": return (["guard", "cluster"], [("cluster", "guard")])
    if "error" in k: return (["forecast" if "forecast" in m else "elevation" if "elevation" in m else "agent"], [])
    return ([], [])


def center(n, side):
    x, y, w, h = NODES[n][:4]
    return {"r": (x + w, y + h / 2), "l": (x, y + h / 2), "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[side]


def curve(a, b, n=48):
    A, B = NODES[a], NODES[b]
    if A[0] == B[0]:
        up, dn = (a, b) if A[1] < B[1] else (b, a)
        p0, p1 = center(up, "b"), center(dn, "t")
        pts = [(p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n) for i in range(n + 1)]
        return pts if (up, dn) == (a, b) else pts[::-1]
    s, t = (a, b) if A[0] < B[0] else (b, a)
    p0, p1 = center(s, "r"), center(t, "l")
    mx = (p0[0] + p1[0]) / 2
    pts = []
    for i in range(n + 1):
        u = i / n
        x = (1 - u) ** 3 * p0[0] + 3 * (1 - u) ** 2 * u * mx + 3 * (1 - u) * u ** 2 * mx + u ** 3 * p1[0]
        y = (1 - u) ** 3 * p0[1] + 3 * (1 - u) ** 2 * u * p0[1] + 3 * (1 - u) * u ** 2 * p1[1] + u ** 3 * p1[1]
        pts.append((x, y))
    return pts if (s, t) == (a, b) else pts[::-1]


def px(p):
    return (p[0] * U, TOP + p[1] * U)


def arclen(pts):
    d = [0.0]
    for p, q in zip(pts, pts[1:]):
        d.append(d[-1] + math.dist(p, q))
    return d


def at(pts, d, frac):
    target = d[-1] * frac
    for i in range(1, len(d)):
        if d[i] >= target:
            f = (target - d[i - 1]) / ((d[i] - d[i - 1]) or 1)
            return (pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f)
    return pts[-1]


def draw_edge(dr, a, b, active, t, direction=None):
    pts = curve(a, b)
    if direction == (b, a):
        pts = pts[::-1]
    P = [px(p) for p in pts]
    if not active:
        dr.line(P, fill=BORDER, width=int(1.6 * SS), joint="curve")
        return
    d = arclen(P)
    dash, gap, off = 15 * SS, 12 * SS, (t * 80 * SS) % (27 * SS)
    pos = -off
    while pos < d[-1]:
        s, e = max(pos, 0), min(pos + dash, d[-1])
        if e > s:
            seg = [at(P, d, s / d[-1])] + [P[i] for i in range(len(P)) if s < d[i] < e] + [at(P, d, e / d[-1])]
            dr.line(seg, fill=ACCENT, width=int(3 * SS), joint="curve")
        pos += dash + gap


def render(frame_t, steps, info, sub, stepi, tin, intro, outro):
    img = Image.new("RGB", (W1 * SS, H1 * SS), BG)
    dr = ImageDraw.Draw(img, "RGBA")
    dr.rectangle([0, 0, W1 * SS, TOP], fill=SURF)
    dr.line([0, TOP, W1 * SS, TOP], fill=BORDER, width=SS)
    dr.text((24 * SS, TOP / 2), "NammaPulse · Live architecture", font=F_BAR, fill=TEXT, anchor="lm")
    dr.text((W1 * SS - 24 * SS, TOP / 2), "Replay of FloodLens's last real run · every step comes from its own trace", font=F_SS, fill=TEXT2, anchor="rm")
    for x, label in ((24, "Data in"), (330, "FloodLens engine"), (630, "Agent and guard"), (930, "Output")):
        dr.text(px((x, 22)), label.upper(), font=F_COL, fill=TEXT3)
    cur = steps[stepi] if (steps and stepi is not None) else None
    active_edges = set(cur["edges"]) if cur else set()
    used = {n for s in steps for n in s["nodes"]}
    for a, b in EDGES:
        on = (a, b) in active_edges or (b, a) in active_edges
        if not on:
            draw_edge(dr, a, b, False, frame_t)
    for a, b in EDGES:
        for e in ([(a, b)] if (a, b) in active_edges else [(b, a)] if (b, a) in active_edges else []):
            draw_edge(dr, a, b, True, frame_t, e)
            pts = [px(p) for p in curve(*e)]
            d = arclen(pts)
            prog = min(1.0, tin / 1.3)
            for k in range(3):  # travelling packets
                f = prog - k * 0.07
                if 0 <= f <= 1:
                    cx, cy = at(pts, d, f)
                    r = (7 - k * 1.5) * SS
                    dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT + (255 - k * 80,))
    pulse = 0.5 + 0.5 * math.sin(frame_t * 5)
    for nid, (x, y, w, h, title, tag) in NODES.items():
        on = cur is not None and nid in cur["nodes"]
        dim = (nid not in used) and (nid not in ALWAYS) and not intro
        bad = cur is not None and on and cur.get("bad")
        X, Y, X2, Y2 = x * U, TOP + y * U, (x + w) * U, TOP + (y + h) * U
        if on:
            for g in range(3, 0, -1):
                dr.rounded_rectangle([X - g * 5 * SS, Y - g * 5 * SS, X2 + g * 5 * SS, Y2 + g * 5 * SS], radius=(8 + g * 4) * SS,
                                     outline=ACCENT + (int((30 + 40 * pulse) / g),), width=2 * SS)
        fill = (24, 33, 48) if on else SURF
        outline = BAD if bad else ACCENT if on else BORDER
        dr.rounded_rectangle([X, Y, X2, Y2], radius=8 * SS, fill=fill, outline=outline, width=(2 if on else 1) * SS)
        a = 110 if dim else 255
        dr.text((X + 12 * U, Y + 17 * U), tag, font=F_TAG, fill=TEXT3 + (a,), anchor="lm")
        dr.text((X + 12 * U, Y + 37 * U), title, font=F_TT, fill=TEXT + (a,), anchor="lm")
        s = sub(nid)
        if s:
            dr.text((X + 12 * U, Y + 55 * U), s[:40], font=F_SS, fill=TEXT2 + (a,), anchor="lm")
        svc = SVC.get(nid)
        if svc and svc in info["health"]:
            c = OK if info["health"][svc]["ok"] else BAD
            r = 4 * SS
            dr.ellipse([X2 - 14 * SS - r, Y + 14 * SS - r, X2 - 14 * SS + r, Y + 14 * SS + r], fill=c)
    # caption
    cy0 = TOP + 620 * U
    dr.rectangle([0, cy0, W1 * SS, H1 * SS], fill=SURF)
    dr.line([0, cy0, W1 * SS, cy0], fill=BORDER, width=SS)
    n = len(steps)
    if cur:
        t0 = steps[0]["t"]
        head = f"step {stepi + 1} of {n} · {cur['kind']} · +{cur['t'] - t0:.1f} s"
        msg = cur["msg"]
        shown = msg[: int(len(msg) * min(1.0, tin / 1.4))]
        dr.text((24 * SS, cy0 + 22 * SS), head, font=F_CAPS, fill=TEXT3)
        dr.text((24 * SS, cy0 + 52 * SS), shown, font=F_CAP, fill=TEXT)
        dr.rectangle([0, H1 * SS - 6 * SS, W1 * SS * ((stepi + min(1, tin / STEP_S)) / n), H1 * SS], fill=ACCENT)
    else:
        dr.text((24 * SS, cy0 + 40 * SS), "Replaying the last real FloodLens run…" if intro else "Run complete.", font=F_CAP, fill=TEXT2)
    return img.resize((W1, H1), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1", help="host of the running services (their own ports are used)")
    ap.add_argument("--out", default="docs")
    a = ap.parse_args()
    body = {"routes": [{"id": "demo-a", "name": "Demo route A", "geometry": [[77.615, 12.9177], [77.635, 12.9177]]},
                       {"id": "demo-b", "name": "Demo route B", "geometry": [[77.6245, 12.93], [77.6245, 12.94]]}],
            "use_preset_scenario": True}
    res = http(f"{a.host}:8005/investigate", body)
    health = {}
    for name, port in (("FloodLens", 8005), ("RoadTrust", 8002), ("TripCast", 8003), ("Orchestrator", 8004)):
        try:
            h = http(f"{a.host}:{port}/health")
            mode = h.get("agent_mode") or h.get("mode")
            health[name] = {"ok": True, "detail": f"AI agent ({h.get('model')})" if mode == "llm" else "no AI model configured" if mode else "running"}
        except Exception:
            health[name] = {"ok": False, "detail": "not reachable"}
    steps = []
    for t in res["trace"]:
        nodes, edges = to_step(t)
        steps.append({"nodes": nodes, "edges": edges, "msg": t["message"], "kind": t["kind"], "bad": "error" in t["kind"],
                      "t": datetime.fromisoformat(t["at"]).timestamp()})
    f, ag = res["forecast"], res["agent"]
    cells = res["risk_map"]["features"]
    subs = {
        "routes": f"{res['audit']['routes']} route(s)",
        "forecast": "what-if scenario, not a forecast" if f["is_scenario"] else f"{f.get('accum_6h_mm')} mm in 6 h · peak {f.get('peak_mm_h')} mm/h",
        "elevation": f"{res['audit']['cells']} grid cells read",
        "reports": "",
        "model": f"{sum(c['properties']['risk'] >= 0.25 for c in cells)} cells above alert level",
        "grid": f"{sum(c['properties']['relief_m'] >= 3 for c in cells)} low-lying cells",
        "cluster": f"{len(res['responses'])} area(s) on your routes",
        "agent": f"{ag.get('model')} · {ag.get('steps')} steps" if ag["mode"] == "llm" else "not used: no AI model configured",
        "guard": "reports every at-risk area, even if the model skips it",
        "map": f"{len(cells)} cells drawn", "findings": f"{len(res['responses'])} finding(s)",
    }
    def sub(n):
        return subs.get(n) or (health.get(SVC.get(n, ""), {}).get("detail", "") if n in SVC else "")
    info = {"health": health}
    frames = int(INTRO_S * FPS) + int(len(steps) * STEP_S * FPS) + int(OUTRO_S * FPS)
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W1}x{H1}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", f"{a.out}/architecture_animated.mp4"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(frames):
        t = i / FPS
        if t < INTRO_S:
            img = render(t, steps, info, sub, None, 0, True, False)
        elif t < INTRO_S + len(steps) * STEP_S:
            k, tin = divmod(t - INTRO_S, STEP_S)
            img = render(t, steps, info, sub, int(k), tin, False, False)
        else:
            img = render(t, steps, info, sub, None, 0, False, True)
        p.stdin.write(img.tobytes())
    p.stdin.close()
    p.wait()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", f"{a.out}/architecture_animated.mp4", "-vf",
                    "fps=12,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", f"{a.out}/architecture_animated.gif"], check=True)
    print("wrote", f"{a.out}/architecture_animated.mp4", f"{a.out}/architecture_animated.gif", f"({len(steps)} steps, {frames / FPS:.1f}s)")


if __name__ == "__main__":
    main()
