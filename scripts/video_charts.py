"""Animated charts for the submission video (feedback notes 3-7, docs/video_feedback_notes.md), drawn with PIL from the
committed CSVs in video/scene_plan/data/ (scripts/make_scene_plan.py), so the numbers cannot drift from the artifacts.
Each chart is a function (t, dur) -> 1920x1080 RGB frame. Style follows the user's engine-cost reference: light panel,
one chart per shot, values at the bar ends, FP16 green, the key line as a pill at the lower right."""
import csv, math
from PIL import Image, ImageDraw, ImageFont
W, H = 1920, 1080
BG, PANEL, INK, INK2, GRID = (16, 20, 19), (246, 247, 248), (24, 32, 40), (96, 106, 116), (226, 230, 234)
GREEN, GREEN_L, TEAL, GREY = (64, 168, 104), (214, 240, 222), (24, 152, 166), (128, 136, 144)
F = lambda s, b=False: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if b else ""), s)
D = "video/scene_plan/data"
rows = lambda name: list(csv.DictReader(open(f"{D}/{name}", encoding="utf-8-sig")))
ease = lambda x: 0.0 if x <= 0 else (1.0 if x >= 1 else 1 - (1 - x) ** 3)
ramp = lambda t, a, b: ease((t - a) / max(b - a, 1e-6))

TITLE_END = [0]
def frame(kicker, title, sub):
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im); TITLE_END[0] = 120 + d.textlength(title, font=F(54, True))
    d.rounded_rectangle((60, 110, W - 60, H - 70), 24, fill=PANEL)
    d.text((120, 150), kicker.upper(), font=F(24, True), fill=INK2); d.text((120, 192), title, font=F(54, True), fill=INK); d.text((122, 262), sub, font=F(26), fill=INK2)
    return im, d

def pill(im, d, text, sub, a):
    if a <= 0: return
    f, fs = F(40, True), F(24); w = max(d.textlength(text, font=f), d.textlength(sub or "", font=fs)) + 70; h = 76 + (34 if sub else 0)
    x1, y0 = W - 110, 140; x0, y1 = x1 - w, y0 + h   # top right, beside the title (burned-in subtitles use the bottom)
    assert x0 > TITLE_END[0] + 30, f"pill would cover the title: shorten the title or the key line ({text})"
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); o = ImageDraw.Draw(ov)
    o.rounded_rectangle((x0, y0, x1, y1), 20, fill=GREEN_L + (int(255 * a),), outline=GREEN + (int(255 * a),), width=3)
    o.text((x0 + 35, y0 + 16), text, font=f, fill=(30, 110, 60, int(255 * a)))
    if sub: o.text((x0 + 36, y0 + 70), sub, font=fs, fill=(60, 110, 80, int(255 * a)))
    im.paste(Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB"))

def hbars(d, items, x0, y0, bw, rh, vmax, prog, fmt, ticks):
    """items: (label, value, colour, highlight); prog: 0..1 per item."""
    for tk in ticks:
        x = x0 + bw * tk / vmax; d.line((x, y0 - 20, x, y0 + rh * len(items)), fill=GRID, width=2); d.text((x - 14, y0 + rh * len(items) + 8), f"{tk:g}", font=F(22), fill=INK2)
    for i, ((lab, v, col, hl), p) in enumerate(zip(items, prog)):
        y = y0 + i * rh; d.text((x0 - 30 - d.textlength(lab, font=F(30)), y + 10), lab, font=F(30, hl), fill=INK)
        L = bw * v / vmax * p
        if hl and p > 0: d.rounded_rectangle((x0 - 8, y - 6, x0 + L + 8, y + rh - 26), 14, fill=GREEN_L)
        if p > 0: d.rounded_rectangle((x0, y, x0 + max(L, 6), y + rh - 32), 10, fill=col)
        if p >= 0.98: d.text((x0 + L + 18, y + 8), fmt(v), font=F(32, True), fill=INK)

def engine_cost(t, dur):
    R = {r["engine"]: r for r in rows("01_engine_cost.csv")}
    int8 = [R[k] for k in ("VC-002", "VC-005", "VC-020")]
    def items(key, lo):
        i8 = min(float(r[key]) for r in int8); hi8 = max(float(r[key]) for r in int8)
        return [("FP16", float(R["VC-025"][key]), GREEN, True), ("INT8 · 3 builds", i8 if lo else hi8, TEAL, False), ("FP32", float(R["VC-000"][key]), GREY, False)]
    half = dur / 2
    if t < half:
        im, d = frame("Engine cost on the deployment target", "GPU compute", "median ms per inference · Jetson Orin Nano Super, 15 W, TensorRT")
        it = items("gpu_ms_median", True); pr = [ramp(t, 0.4 + 0.3 * i, 1.6 + 0.3 * i) for i in range(3)]
        hbars(d, it, 520, 360, 1180, 140, 60, pr, lambda v: f"{v:g} ms", [0, 20, 40, 60]); pill(im, d, "FP16 is the fastest", None, ramp(t, 2.6, 3.1))
    else:
        u = t - half; im, d = frame("Engine cost on the deployment target", "Energy", "energy per inference above idle (mJ)")
        it = items("energy_mJ_per_inference", True); pr = [ramp(u, 0.4 + 0.3 * i, 1.6 + 0.3 * i) for i in range(3)]
        hbars(d, it, 520, 360, 1180, 140, 450, pr, lambda v: f"{v:g} mJ", [0, 150, 300, 450]); pill(im, d, "FP16 is the cheapest", "energy per inference", ramp(u, 2.6, 3.1))
    return im

def g6_success(t, dur):
    R = rows("02_g6_success_by_cell.csv"); R = sorted(R, key=lambda r: (r["cell"] == "VC-000", r["cell"]))
    im, d = frame("Blinded real-arm trials · G6, 245 trials", "Closed-loop success by cell", "successes / trials per engine (FP32 reference in grey) · Wilson 95% interval")
    n = len(R); rh = 44; x0, y0, bw = 420, 320, 1100
    for tk in (0, 25, 50, 75, 100):
        x = x0 + bw * tk / 100; d.line((x, y0 - 14, x, y0 + rh * n), fill=GRID, width=2); d.text((x - 18, y0 + rh * n + 8), f"{tk}%", font=F(22), fill=INK2)
    for i, r in enumerate(R):
        p = ramp(t, 0.3 + 0.12 * i, 1.2 + 0.12 * i); y = y0 + i * rh; k, m = int(r["successes"]), int(r["trials"]); v = k / m
        lab = "FP32 (VC-000)" if r["cell"] == "VC-000" else r["cell"]; d.text((x0 - 24 - d.textlength(lab, font=F(24)), y + 4), lab, font=F(24), fill=INK)
        if p > 0: d.rounded_rectangle((x0, y + 4, x0 + bw * v * p, y + rh - 14), 8, fill=GREY if r["cell"] == "VC-000" else TEAL)
        if p >= 0.98:
            lo, hi = float(r["wilson95_lo_pct"]) / 100, float(r["wilson95_hi_pct"]) / 100; yc = y + (rh - 10) / 2
            d.line((x0 + bw * lo, yc, x0 + bw * hi, yc), fill=INK, width=3); d.text((x0 + bw * 1.0 + 20, y + 4), f"{k}/{m}", font=F(24, True), fill=INK)
    rates = [int(r["successes"]) / int(r["trials"]) * 100 for r in R]
    pill(im, d, f"Every cell: {min(rates):.0f}–{max(rates):.0f}% on the arm", "25 trials per cell cannot tell them apart", ramp(t, 0.3 + 0.12 * n + 1.0, 0.3 + 0.12 * n + 1.5))
    return im

def cost_vs_success(t, dur):
    R = rows("03_cost_vs_success.csv")
    im, d = frame("Cost and evidence, side by side", "Cost vs success", "each point: an engine; vertical line: Wilson 95% interval of its success")
    x0, y0, x1, y1 = 300, 330, 1560, 790; X = lambda ms: x0 + (x1 - x0) * ms / 60; Y = lambda pct: y1 - (y1 - y0) * (pct - 50) / 50
    for v in (50, 75, 100): d.line((x0, Y(v), x1, Y(v)), fill=GRID, width=2); d.text((x0 - 80, Y(v) - 14), f"{v}%", font=F(24), fill=INK2)
    for ms in (0, 20, 40, 60): d.text((X(ms) - 14, y1 + 14), f"{ms}", font=F(24), fill=INK2)
    d.text(((x0 + x1) / 2 - 230, y1 + 50), "GPU ms per inference (lower is cheaper)", font=F(24), fill=INK2)
    groups = [("FP32", [r for r in R if r["candidate"] == "VC-000"], GREY, 0.3), ("INT8 · G6 cells", [r for r in R if r["candidate"] in ("VC-002", "VC-020", "VC-005")], TEAL, 1.3),
              ("FP16", [r for r in R if r["candidate"] == "VC-025"], GREEN, 2.3)]
    for name, rs, col, ts in groups:
        a = ramp(t, ts, ts + 0.6)
        if a <= 0: continue
        for j, r in enumerate(rs):
            ms = float(r["gpu_ms"]) + (j - (len(rs) - 1) / 2) * 0.9; pct = float(r["success_pct"]); lo, hi = float(r["wilson95_lo_pct"]), float(r["wilson95_hi_pct"])
            yy = Y(pct) + (1 - a) * 40; d.line((X(ms), Y(max(lo, 50)), X(ms), Y(hi)), fill=col, width=4); d.ellipse((X(ms) - 13, yy - 13, X(ms) + 13, yy + 13), fill=col)
        lx = X(float(rs[0]["gpu_ms"])); ly = Y(float(rs[0]["success_pct"])); label = name + ("  " + rs[0]["successes"] + "/" + rs[0]["trials"] if len(rs) == 1 else "")
        fl = F(28, True); tw = d.textlength(label, font=fl)
        pos = {"FP16": (lx - 30 - tw, ly - 16), "INT8 · G6 cells": (lx + 40, ly - 16), "FP32": (lx - 30 - tw, ly - 16)}[name]
        d.text(pos, label, font=fl, fill=col)
    pill(im, d, "FP16: cheapest engine, 19/20 on the arm", None, ramp(t, 3.2, 3.7))
    return im

def audit_vs_random(t, dur):
    R = rows("04_audit_vs_random.csv")
    im, d = frame("Does the offline audit pick better cells?", "Audit vs random picks", "real-arm successes, three cells per group (G6)")
    items = [("audit top picks", float(R[0]["success_pct"]), TEAL, False), ("random picks", float(R[1]["success_pct"]), GREY, False)]
    pr = [ramp(t, 0.2, 1.4)] * 2
    hbars(d, items, 560, 440, 1100, 170, 100, pr, lambda v: "", [0, 50, 100])
    for i, r in enumerate(R):
        if pr[i] >= 0.98: d.text((560 + 1100 * float(r["success_pct"]) / 100 + 18, 448 + i * 170), f'{r["successes"]}/{r["trials"]}', font=F(32, True), fill=INK)
    pill(im, d, "Same result: 73/75 vs 73/75", "the offline score did not predict the arm", ramp(t, 1.6, 2.0))
    return im

def ft_position(t, dur):
    R = rows("05_position_finetune.csv"); by = {(r["start"], r["block"]): r for r in R}
    sel = [("+3 cm", by[("+3 cm", "T1")]), ("−3 cm", by[("-3 cm", "T2")]), ("training mark", by[("0 cm (training mark)", "T0 + T0R pooled")])]
    im, d = frame("Position fine-tune · blinded, interleaved", "Fixed where it failed", "old policy vs fine-tuned, successes / trials per start position")
    gx, gw, y1, hmax = 300, 440, 770, 380
    for v in (0, 50, 100): yy = y1 - hmax * v / 100; d.line((240, yy, 1700, yy), fill=GRID, width=2); d.text((180, yy - 14), f"{v}%", font=F(22), fill=INK2)
    for i, (lab, r) in enumerate(sel):
        p = ramp(t, 0.2 + 0.9 * i, 1.0 + 0.9 * i); cx = gx + i * gw + gw / 2
        for j, (k, n, col) in enumerate(((int(r["old_successes"]), int(r["old_trials"]), GREY), (int(r["ft_successes"]), int(r["ft_trials"]), GREEN))):
            x = cx + (j - 0.5) * 150 - 65; hh = hmax * k / n * p
            if p > 0: d.rounded_rectangle((x, y1 - hh, x + 130, y1), 10, fill=col)
            if p >= 0.98: d.text((x + 65 - d.textlength(f"{k}/{n}", font=F(30, True)) / 2, y1 - hh - 44), f"{k}/{n}", font=F(30, True), fill=INK)
        d.text((cx - d.textlength(lab, font=F(30, True)) / 2, y1 + 16), lab, font=F(30, True), fill=INK)
        if p >= 0.98: d.text((cx - d.textlength(r["reading"], font=F(22)) / 2, y1 + 56), r["reading"], font=F(22), fill=INK2)
    for j, (name, col) in enumerate((("old policy", GREY), ("fine-tuned", GREEN))):
        d.rounded_rectangle((1380 + j * 220, 268, 1408 + j * 220, 294), 6, fill=col); d.text((1418 + j * 220, 264), name, font=F(26), fill=INK)
    pill(im, d, "+3 cm 12/12 vs 3/12 · −3 cm 10/12 vs 2/12", "training mark (24 vs 24): still undecided", ramp(t, 3.0, 3.5))
    return im

CHARTS = {"engine_cost": engine_cost, "g6_success": g6_success, "cost_vs_success": cost_vs_success, "audit_vs_random": audit_vs_random, "ft_position": ft_position}
