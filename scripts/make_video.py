"""Assemble the submission video (docs/video_plan.md v3.1) from committed material and the user's edited clips.
Picture segments are timed to the narration's sentence starts (docs/narration/narration_v3.srt). Burned-in subtitles
come from the same SRT. The narration audio is copied in. Nothing is retimed except the stated speed-ups, which are
labelled on screen. Clips from the user's phone are read from video/edit/ (not in git).
Usage: <venv with av+PIL> python scripts/make_video.py <shots dir> <out.mp4>"""
import json, os, re, sys
import av, numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phone_clips as pc

SHOTS, OUT = sys.argv[1:3]
W, H, FPS = 1920, 1080, 30
BG, INK, INK2, ACC = (16, 20, 19), (230, 234, 233), (174, 184, 183), (18, 160, 168)
F = lambda s, b=False: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if b else ""), s)
FONT_SUB, FONT_CHIP, FONT_CARD, FONT_BIG = F(34), F(28), F(46, True), F(80, True)
R = "artifacts/reports/figures"; C = "dashboard/clips"; E = "video/edit"

def srt(path):
    out = []
    for b in open(path).read().strip().split("\n\n"):
        l = b.split("\n"); a, z = l[1].split(" --> ")
        t = lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8]) + int(s[9:]) / 1000
        txt = " ".join(l[2:])
        for k, v in (("S O one oh one", "SO-101"), ("A C T", "ACT"), ("A I", "AI"), ("int eight", "INT8"), ("Quant Gate", "QuantGate")): txt = txt.replace(k, v)
        out.append((t(a), t(z), txt))
    return out

SUBS = srt("docs/narration/narration_v3.srt")

# Segments are (scene, start, end) in seconds relative to the scene start (docs/narration/narration_v3_timing.json),
# then kind, args and the on-screen chip.
ST = json.load(open("docs/narration/narration_v3_timing.json"))
T1L = "video/2.T1_long/20261014_213936.mp4"   # phone, upside down: rot 180
REL = [
    ("0", 0.0, 12.3, "intro", (), None),
    ("1", 0.0, 2.0, "clip", (f"{C}/g6_success.mp4", 2.0, 4, 0), "Same robot, same task: success (overhead, 4×)"),
    ("1", 2.0, 4.1, "clip", (f"{C}/g6_fail_knock.mp4", 8.0, 4, 0), "Same robot, same task: failure (overhead, 4×)"),
    ("1", 4.1, 11.3, "card", ("Before I ship this policy to a tiny Jetson,\nhow do I know which model I can trust?",), None),
    ("2", 0.0, 5.8, "clip", (f"{E}/demo_ft.mp4", 1.0, 1, 0), "Real arm, real time · SO-101 · ACT · Jetson Orin Nano Super"),
    ("2", 5.8, 12.1, "clip", (f"{C}/demos_top_wrist.mp4", 0.0, 1, 0), "Teleoperated demonstrations: overhead and wrist camera (training data)"),
    ("2", 12.1, 24.4, "clip", (f"{E}/demo_ft.mp4", 6.8, 1, 0), "Real arm, real time · fine-tuned policy at +3 cm (demonstration take, not counted)"),
    ("2", 24.4, 43.0, "clip", (T1L, 209.6, 1, 180), "Counted blinded trial (T1 trial 4) · the operator sees trial numbers only"),
    ("3", 0.0, 11.4, "image", (f"{SHOTS}/cost.png",), "Engine cost measured on the Jetson Orin Nano Super (trtexec, 15 W)"),
    ("3", 11.4, 18.5, "image", (f"{SHOTS}/success.png",), "Blinded real-arm success by cell (G6, 245 trials)"),
    ("4", 0.0, 9.9, "image", (f"{R}/fig_cost_evidence.png",), "FP16: cheapest engine; 19/20 on the arm"),
    ("4", 9.9, 13.5, "image", (f"{SHOTS}/contrasts.png",), "Audit-picked vs random INT8 cells: 73/75 vs 73/75"),
    ("4", 13.5, 16.6, "clip", (f"{E}/yellow_can_2.mp4", 4.0, 1, 0), "Unseen yellow can · block result 48/48 (side view of a demonstration)"),
    ("4", 16.6, 20.5, "clip", (f"{C}/v2_shift_regrasp.mp4", 8.0, 4, 0), "Start moved 3 cm: 0/3 (overhead, 4×)"),
    ("4", 20.5, 29.1, "image", (f"{SHOTS}/pos_strip.png",), "50 new demos at −4…+4 cm · fine-tuned 20k steps on Nebius Jobs · ±3 cm held out"),
    ("4", 29.1, 36.7, "clip", (f"{E}/t1_old_vs_ft_counted.mp4", 0.0, 2, 0), "Counted blinded trials at +3 cm (side view, 2×)"),
    ("4", 36.7, 40.0, "image", (f"{R}/fig_ft_position.png",), "+3 cm 12/12 vs 3/12 · −3 cm 10/12 vs 2/12 · training mark undecided"),
    ("5", 0.0, 9.0, "image", (f"{R}/fig_frames.png",), "A failure the first Cosmos setup called a success"),
    ("5", 9.0, 17.3, "card", ("Cosmos-Reason2 end-of-trial judge\n\nfirst setup                  1/21 failures caught\nvalidated prompt, held out   20/21 · 5/252 false alarms\nsame prompt, live new trials 21/23 · 1/49 false alarms",), None),
    ("5", 17.3, 25.2, "image", (f"{SHOTS}/report_meta.png", 0, 1100), "Deployment report: code writes verdicts and numbers; Nemotron (Token Factory) explains"),
    ("6", 0.0, 7.9, "image", (f"{SHOTS}/review_decisions.png",), "The deployment review"),
    ("6", 7.9, 16.2, "image", (f"{SHOTS}/preflight.png",), "Deployment preflight: broken builds and timing are blocked"),
    ("6", 16.2, 22.5, "image", (f"{SHOTS}/review_compare.png",), "Not yet: the review lists the trials still missing"),
    ("7", 0.0, 4.0, "logo", (), None),
]
SEG = [(ST[k] + a, ST[k] + b, kind, args, chip) for k, a, b, kind, args, chip in REL]

def fit(im, box_w, box_h):
    r = min(box_w / im.width, box_h / im.height); return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)

def chip(d, text):
    w = d.textlength(text, font=FONT_CHIP); d.rounded_rectangle((40, 28, 40 + w + 36, 28 + 48), 10, fill=(28, 34, 33)); d.text((58, 36), text, font=FONT_CHIP, fill=INK)

def subtitle(d, t):
    s = next((x for x in SUBS if x[0] <= t < x[1] + 0.15), None)
    if not s: return
    words, lines, cur = s[2].split(), [], ""
    for w_ in words:
        if d.textlength(cur + " " + w_, font=FONT_SUB) > 1600 and cur: lines.append(cur); cur = w_
        else: cur = (cur + " " + w_).strip()
    lines.append(cur); y = H - 40 - 46 * len(lines)
    for ln in lines:
        w = d.textlength(ln, font=FONT_SUB); d.rectangle(((W - w) / 2 - 14, y - 4, (W + w) / 2 + 14, y + 42), fill=(0, 0, 0)); d.text(((W - w) / 2, y), ln, font=FONT_SUB, fill=(255, 255, 255)); y += 46

def card(text):
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im); mono = "\n\n" in text
    f = F(40) if mono else FONT_CARD
    if mono: f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 40)
    lines = text.split("\n"); hh = 64 * len(lines); y = (H - hh) / 2 - 60
    for i, ln in enumerate(lines):
        w = d.textlength(ln, font=f); d.text(((W - w) / 2 if not mono else 260, y), ln, font=(FONT_CARD if (mono and i == 0) else f), fill=ACC if (mono and i == 0) else INK); y += 64
    return im

def logo():
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    lg = Image.open("docs/assets/quantgate_logo.png").convert("RGBA"); lg = fit(lg, 900, 420); im.paste(lg, ((W - lg.width) // 2, 220), lg)
    for y, txt, f, col in ((700, "Evidence before deployment.", F(52, True), INK), (790, "github.com/goodboychan/nebius-physical-ai", F(34), INK2)):
        w = d.textlength(txt, font=f); d.text(((W - w) / 2, y), txt, font=f, fill=col)
    return im

def frames_of(seg):
    t0, t1, kind, args, label = seg; n = int(round((t1 - t0) * FPS))
    if kind == "clip":
        path, s0, speed, rot = args
        gen = pc.frames(path, s0, (t1 - t0) * speed + 0.5, fps=FPS / speed, size=None)
        last = None
        for i in range(n):
            try:
                last = next(gen)[1]
                if rot: last = last.rotate(rot)
            except StopIteration: pass
            base = Image.new("RGB", (W, H), BG); f = fit(last, W, H - 0); base.paste(f, ((W - f.width) // 2, (H - f.height) // 2)); yield base
    elif kind == "image":
        im = Image.open(args[0]).convert("RGB")
        if len(args) == 3: im = im.crop((0, args[1], im.width, min(im.height, args[2])))
        f0 = fit(im, 1760, 860); bg = (241, 243, 242)
        for i in range(n):
            f = f0   # static (the user asked for no zoom; animation timing is set in the PPTX version)
            base = Image.new("RGB", (W, H), BG); pad = Image.new("RGB", (min(W - 40, f.width + 40), min(H - 120, f.height + 40)), bg)
            base.paste(pad, ((W - pad.width) // 2, (H - pad.height) // 2 + 10)); base.paste(f, ((W - f.width) // 2, (H - f.height) // 2 + 10)); yield base
    elif kind == "card":
        im = card(args[0])
        for i in range(n): yield im.copy()
    elif kind == "intro":
        th = fit(Image.open("docs/assets/quantgate_thumbnail.png").convert("RGB"), W, H)
        sx, sy = th.width / 1536, th.height / 1024; ox, oy = (W - th.width) // 2, (H - th.height) // 2
        P = lambda x, y: (ox + x * sx, oy + y * sy)
        subs = [x for x in SUBS if t0 <= x[0] < t1]
        marks = [("Q · QuantGate and quantization", (600, 255, 932, 567), (300, 190)),
                 ("the gap at the corner:\nthe gate", (848, 455, 928, 555), (1190, 400)),
                 ("a candidate leaving the gate:\ncleared for its next test,\nnot approved", (902, 507, 976, 580), (1190, 520))]
        for i in range(n):
            t = t0 + i / FPS; im = Image.new("RGB", (W, H), BG); im.paste(th, (ox, oy)); d = ImageDraw.Draw(im)
            shown = 0 if not subs or t < subs[min(1, len(subs) - 1)][0] else (1 if len(subs) < 3 or t < subs[2][0] + 3.0 else 3)
            if len(subs) >= 3 and t >= subs[2][0] + 3.0: shown = 3
            elif len(subs) >= 3 and t >= subs[2][0]: shown = 2
            for j, (txt, box, at) in enumerate(marks[:shown]):
                x0, y0 = P(box[0], box[1]); x1, y1 = P(box[2], box[3]); d.rounded_rectangle((x0, y0, x1, y1), 14, outline=(255, 255, 255), width=4)
                tx, ty = P(*at); d.multiline_text((tx, ty), txt, font=FONT_CHIP, fill=(255, 255, 255), spacing=8)
            yield im
    else:
        im = logo()
        for i in range(n): yield im.copy()

o = av.open(OUT, "w", options={"movflags": "+faststart"}); vs = o.add_stream("libx264", rate=FPS)
vs.width, vs.height, vs.pix_fmt = W, H, "yuv420p"; vs.options = {"crf": os.environ.get("CRF", "21"), "preset": "medium"}
a_in = av.open("docs/narration/narration_v3_am_michael.m4a"); as_ = o.add_stream_from_template(a_in.streams.audio[0], opaque=True)
k = 0
for seg in SEG:
    for im in frames_of(seg):
        t = k / FPS; d = ImageDraw.Draw(im)
        if seg[4]: chip(d, seg[4])
        subtitle(d, t)
        for p in vs.encode(av.VideoFrame.from_image(im)): o.mux(p)
        k += 1
    print(f"{seg[0]:6.1f}-{seg[1]:6.1f} {seg[2]:5} frames to {k}", flush=True)
for p in vs.encode(): o.mux(p)
for p in a_in.demux(a_in.streams.audio[0]):
    if p.dts is None: continue
    p.stream = as_; o.mux(p)
o.close(); print("written", OUT, k / FPS, "s")
