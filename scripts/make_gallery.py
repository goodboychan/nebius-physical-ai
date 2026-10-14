"""Devpost gallery images (3:2, 1500x1000 PNG), composed from the dashboard captures and committed figures.
Usage: <venv with PIL> python scripts/make_gallery.py <shots dir> <out dir>"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

SHOTS, OUT = sys.argv[1:3]; os.makedirs(OUT, exist_ok=True)
W, H = 1500, 1000; BG, INK, INK2, ACC = (16, 20, 19), (230, 234, 233), (174, 184, 183), (163, 230, 53)
F = lambda s, b=False: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if b else ""), s)

def fit(im, w, h):
    r = min(w / im.width, h / im.height); return im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)

def slide(name, title, sub, parts, light=True):
    """parts: list of (image path or PIL image, x, y, w, h) boxes inside the content area."""
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.text((56, 44), title, font=F(46, True), fill=INK); d.text((58, 108), sub, font=F(24), fill=INK2)
    d.rectangle((56, 152, 56 + 90, 156), fill=ACC)
    for src, x, y, w, h in parts:
        p = Image.open(src).convert("RGB") if isinstance(src, str) else src
        f = fit(p, w - (28 if light else 0), h - (28 if light else 0))
        if light: d.rounded_rectangle((x, y, x + w, y + h), 12, fill=(241, 243, 242))
        im.paste(f, (x + (w - f.width) // 2, y + (h - f.height) // 2))
    d.text((56, H - 46), "QuantGate · a robot deployment review · Nebius × NVIDIA", font=F(20), fill=INK2)
    im.save(f"{OUT}/{name}.png", optimize=True); print(name)

thumb = Image.open("docs/assets/quantgate_thumbnail.png").convert("RGB").resize((W, int(W * 1024 / 1536)), Image.LANCZOS)
t = Image.new("RGB", (W, H), (15, 21, 28)); t.paste(thumb, (0, (H - thumb.height) // 2)); t.save(f"{OUT}/01_thumbnail.png", optimize=True)
slide("02_deployment_review", "The deployment review", "Which candidate to validate first, which to distrust, and whether to approve",
      [(f"{SHOTS}/review_decisions.png", 56, 180, 1388, 330), (f"{SHOTS}/review_compare.png", 56, 530, 1388, 410)])
slide("03_position_finetune", "A weakness found, fixed and re-tested", "Blinded, interleaved, 12 vs 12 per position · +3 cm: 12/12 vs 3/12 · −3 cm: 10/12 vs 2/12",
      [("artifacts/reports/figures/fig_ft_position.png", 56, 180, 1388, 420),
       (Image.open(f"{SHOTS}/t1_pair_frame.png").convert("RGB").crop((0, 90, 1920, 690)), 56, 620, 1388, 330)], light=True)
slide("04_engine_cost", "Measured on the Jetson, not assumed", "FP16 is the cheapest engine here: 11.6 ms and 82 mJ per inference; INT8 16.8 ms and 101 mJ",
      [(f"{SHOTS}/cost.png", 56, 180, 1388, 760)])
slide("05_preflight", "Deployment preflight", "Engine hash · normalization manifest · 200 ms chunk deadline · code-decided verdict",
      [(f"{SHOTS}/preflight.png", 56, 180, 1388, 760)])
slide("06_setup", "One task, one arm, cloud where it does real work", "SO-101 + Jetson Orin Nano Super · training on Nebius Jobs · Cosmos-Reason2 and Nemotron 3 Super on Nebius",
      [(f"{SHOTS}/setup.png", 56, 180, 1388, 760)])
