"""Devpost gallery v4 (15 images, 3:2, 1800x1200 PNG) for the second submission, in the order of video v11: the real arm,
what QuantGate tells the developer, how it works, the product, the evidence, the fixes, the failures we publish.
Inputs: full-resolution frames of video v11 without subtitles (make_video.py with NARR=v9 PREVIEW=<dir> PREVIEW_FULL=1
PREVIEW_NOSUB=1) and dashboard captures (cap_*.png). Usage: python scripts/make_gallery_v4.py <frames 0.93> <frames 0.15> <captures> <out>"""
import os, sys
from PIL import Image, ImageDraw, ImageFont
VF, VF0, CAP, OUT = sys.argv[1:5]; os.makedirs(OUT, exist_ok=True)
W, H = 1800, 1200; BG, INK, INK2, ACC, PANEL = (16, 20, 19), (236, 240, 239), (170, 180, 179), (163, 230, 53), (241, 243, 242)
F = lambda s, b=False: ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-%s.ttc" % ("Bold" if b else "Regular"), s, index=1)
fit = lambda im, w, h: (lambda r: im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS))(min(w / im.width, h / im.height))
def slide(n, title, sub, parts, notes=()):
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((64, 46), title, font=F(54, True), fill=INK); fs = next(F(z) for z in range(27, 17, -1) if d.textlength(sub, font=F(z)) <= W - 130 or z == 18); d.text((66, 120), sub, font=fs, fill=INK2); d.rectangle((64, 170, 164, 175), fill=ACC)
    for src, x, y, w, h, panel in parts:
        p = Image.open(src).convert("RGB") if isinstance(src, str) else src
        pad = 24 if panel else 0; f = fit(p, w - 2 * pad, h - 2 * pad)
        if panel: d.rounded_rectangle((x, y, x + w, y + h), 14, fill=PANEL)
        im.paste(f, (x + (w - f.width) // 2, y + (h - f.height) // 2))
    for (x, y, s) in notes: d.text((x, y), s, font=F(30, True), fill=INK)
    d.text((64, H - 52), "QuantGate · evidence before deployment · Nebius × NVIDIA, Physical AI", font=F(22), fill=INK2)
    im.save(f"{OUT}/{n}.png", optimize=True); print(n)
crop = lambda p, box: Image.open(p).convert("RGB").crop(box)
th = Image.open("docs/assets/quantgate_thumbnail.png").convert("RGB"); t = Image.new("RGB", (W, H), (15, 21, 28)); f = fit(th, W, H); t.paste(f, ((W - f.width) // 2, (H - f.height) // 2)); t.save(f"{OUT}/01_thumbnail.png", optimize=True); print("01_thumbnail")
slide("02_same_robot", "Same robot, same task: one run succeeds, one fails", "Move the can 3 cm and the policy misses it (initial probe, 0/3) · real SO-101 arm, overhead camera",
      [(f"{VF}/s00_clip.png", 64, 300, 820, 470, False), (f"{VF0}/s02_clipmark.png", 916, 300, 820, 470, False)],
      notes=[(64, 800, "success: the can ends upright on the coaster"), (916, 800, "start moved 3 cm: the gripper misses (marks added)")])
slide("03_what_it_tells_you", "What QuantGate tells the developer", "For developers validating LeRobot policies on Jetson: validate FP16 first · deployment HOLD · the next test is planned",
      [(f"{VF}/s03_split.png", 64, 200, 1672, 940, False)])
slide("04_workflow", "How it works: models suggest and describe, code decides", "Build the candidates → gather evidence on the real arm → decide · where each step runs and which model does it",
      [(f"{CAP}/cap_workflow.png", 64, 200, 1672, 940, True)])
slide("05_try_it_fp16", "Pick a candidate: confirmed, open, evidence, next test", "FP16 (VC-025): cheapest on the device, 19/20 vs FP32 10/10 on the arm · approval on hold · the plan to pre-register",
      [(crop(f"{CAP}/cap_nexttest_fp16.png", (0, 0, 2160, 1584)), 64, 200, 1672, 940, True)])
slide("06_preflight", "Before the arm: HOLD or BLOCK, never a silent GO", "Engine hash · normalization manifest · 200 ms chunk deadline · code-decided verdict · FAULT INJECTION rows are deliberate",
      [(f"{CAP}/cap_preflight.png", 64, 200, 1672, 940, True)])
slide("07_engine_cost", "Measured on the Jetson, not assumed", "FP16 11.6 ms and 82 mJ per inference; INT8 16.8 ms and 101 mJ; FP32 53.4 ms and 403 mJ (trtexec, 15 W)",
      [(f"{CAP}/cap_cost.png", 64, 200, 1672, 940, True)])
slide("08_cost_is_not_approval", "Cost is not approval", "FP16 vs FP32 on the arm: 19/20 vs 10/10 → INSUFFICIENT_EVIDENCE → deployment HOLD → pre-register a revised test",
      [(f"{VF}/s11_split.png", 64, 200, 1672, 940, False)])
slide("09_audit_vs_arm", "The offline score did not predict the arm", "G6 nominal tests, 10–25 trials per engine: all 90–100% · audit top picks 73/75 vs random picks 73/75",
      [(f"{VF}/s10_chart.png", 64, 200, 1672, 940, False)])
slide("10_what_moved", "What moved success: grip and position", "No success difference detected between precisions · pads removed 8/24 · start +3 cm 0/3 · unseen can at the mark 48/48",
      [(f"{VF}/s12_chart.png", 64, 200, 1672, 940, False)])
slide("11_found_fixed", "Found, fixed with data, re-tested sealed", "50 new demonstrations, a 25-minute fine-tune on Nebius Jobs · at +3 cm: old 3/12, fine-tuned 12/12 (counted trials)",
      [(f"{VF}/s15_clip.png", 64, 200, 1672, 940, False)])
slide("12_reach_on_the_table", "Where the fine-tune works, on the table", "−6 cm improved · +3/−3 cm improved · the training mark undecided · +6 cm and the yellow can: fixed by fine-tune v2",
      [(f"{CAP}/cap_reach.png", 64, 200, 1672, 940, True)])
slide("13_finetune_v2", "Fine-tune v2 closed both gaps", "Same session, sealed, 12 vs 12: yellow can 12/12 vs 7/12 · +6 cm 12/12 vs 2/12 · training mark 12/12 vs 12/12",
      [("artifacts/reports/figures/fig_ft2_reach.png", 64, 200, 1672, 940, True)])
slide("14_failures_we_publish", "Physical failures we found and publish", "Gripper friction · a 3 cm shift · a smaller can · a knocked wrist camera found with results still sealed",
      [(f"{CAP}/cap_physical.png", 64, 200, 1672, 940, True)])
slide("15_ai_layers", "AI layers, validated before use", "Cosmos-Reason2 judges the final frame: 22/24 failures caught, 2/72 false alarms on 96 new trials · Nemotron explains; code decides",
      [(f"{VF}/s19_split.png", 64, 200, 1672, 940, False)])
