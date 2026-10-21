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
import video_charts as vchart   # feedback notes 3-7: animated charts from the committed CSVs

SHOTS, OUT = sys.argv[1:3]
W, H, FPS = 1920, 1080, 30
BG, INK, INK2, ACC = (16, 20, 19), (230, 234, 233), (174, 184, 183), (18, 160, 168)
F = lambda s, b=False: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if b else ""), s)
if os.environ.get("NARR", "v5") == "v6":   # v9: Noto Sans, the same family as the deck and closer to the dashboard
    F = lambda s, b=False: ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-%s.ttc" % ("Bold" if b else "Regular"), s, index=1)
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

NARR = os.environ.get("NARR", "v5")   # v5 (2026-10-16): external review 7 (story first, >= 65 s of robot footage); v4: notes 1-9
SUBS = srt(f"docs/narration/narration_{NARR}.srt")

# Segments are (scene, start, end) in seconds relative to the scene start (docs/narration/narration_v3_timing.json),
# then kind, args and the on-screen chip.
ST = json.load(open(f"docs/narration/narration_{NARR}_timing.json"))
T1L = "video/2.T1_long/20261014_213936.mp4"   # phone, upside down: rot 180
LOGO = "video/assets/quantgate_logo_intro.mp4"   # the user's logo animation (14.5 s, 1536x1024)
OUTRO = "video/assets/quantgate_logo_outro.mp4"  # the user's logo-only animation for the last scene (14.5 s)
REL = [   # v8 (external review 7): found -> fixed -> still not approved, in the first 25 s; >= 65 s of real robot footage
    ("0", 0.0, 1.4, "clip", (f"{C}/g6_success.mp4", 2.0, 4, 0), "Same robot, same task: success (overhead, 4×)"),
    ("0", 1.4, 3.3, "clip", (f"{C}/g6_fail_knock.mp4", 8.0, 4, 0), "Same robot, same task: failure (overhead, 4×)"),
    ("0", 3.3, 8.2, "clip", (f"{C}/v2_shift_regrasp.mp4", 8.0, 4, 0), "Start moved 3 cm: 0/3 in the first three tries (overhead, 4×)"),
    ("0", 8.2, 19.6, "clip", (f"{E}/t1_old_vs_ft_counted.mp4", 0.0, 2, 0), "Counted trials at +3 cm, sealed and interleaved: old 3/12 · fine-tuned 12/12 (side view, 2×)"),
    ("0", 19.6, 25.825, "chart", ("ft_position",), None),
    ("1", 0.0, 12.575, "video", (LOGO,), None),
    ("2", 0.0, 8.2, "clip", (f"{E}/demo_ft.mp4", 1.0, 1, 0), "Real arm, real time · SO-101 · ACT (Action Chunking with Transformers) · Jetson Orin Nano Super"),
    ("2", 8.2, 15.0, "clip", (f"{C}/demos_top_wrist.mp4", 0.0, 1, 0), "Teleoperated demonstrations: overhead and wrist camera (training data)"),
    ("2", 15.0, 27.4, "clip", (f"{E}/demo_ft.mp4", 9.2, 1, 0), "Real arm, real time · fine-tuned policy at +3 cm (demonstration take, not counted)"),
    ("2", 27.4, 37.525, "clip", (T1L, 209.6, 1, 180), "Counted trial (T1 trial 4) · sealed, interleaved schedule · the operator sees trial numbers only"),
    ("3", 0.0, 9.6, "chart", ("engine_cost",), None),
    ("3", 9.6, 15.0, "overlay", (f"{C}/v2_rubber_success.mp4", 4.0, 4, "g6_success"), "Real arm (overhead, 4×)"),
    ("3", 15.0, 22.4, "overlay", (f"{C}/g6_success.mp4", 6.0, 4, "audit_vs_random"), "Real arm (overhead, 4×)"),
    ("4", 0.0, 4.8, "chart", ("what_moved",), None),
    ("4", 4.8, 8.0, "clip", (f"{E}/yellow_can_2.mp4", 4.0, 1, 0), "Unseen yellow can · block result 48/48 (side view of a demonstration)"),
    ("4", 8.0, 12.5, "clip", (f"{C}/v1_nopad_drop.mp4", 4.0, 4, 0), "Gripper pads removed: the block finished 8/24 (overhead, 4×)"),
    ("4", 12.5, 16.5, "image", (f"{SHOTS}/pos_strip.png",), "50 new demos at −4…+4 cm · fine-tuned 20k steps on Nebius Jobs · ±3 cm held out"),
    ("4", 16.5, 21.425, "clip", (f"{E}/demo_ft.mp4", 30.0, 1, 0), "Fine-tuned policy, real time (demonstration take, not counted)"),
    ("5", 0.0, 9.2, "image", (f"{R}/fig_frames.png",), "A failure the first Cosmos setup called a success"),
    ("5", 9.2, 17.5, "card", ("Cosmos-Reason2 end-of-trial judge\n\nfirst setup                  1/21 failures caught\nvalidated prompt, held out   20/21 · 5/252 false alarms\nsame prompt, live new trials 22/24 · 2/72 false alarms",), None),
    ("5", 17.5, 25.35, "scroll", (f"{SHOTS}/report_meta.png",), "Deployment report: code writes verdicts and numbers; Nemotron (Token Factory) explains"),
    ("6", 0.0, 7.7, "image", (f"{SHOTS}/review_decisions.png",), "The deployment review"),
    ("6", 7.7, 15.6, "image", (f"{SHOTS}/preflight.png",), "Deployment preflight: broken builds and timing are blocked"),
    ("6", 15.6, 23.4, "image", (f"{SHOTS}/review_compare.png",), "Not yet: the review lists the trials and rule changes still missing"),
    ("7", 0.0, 4.2, "endkick", ("Earn the next test, not the approval.",), None),
]
if NARR == "v6":   # v9 (2026-10-21): audience line, 673 blinded trials, the fine-tune's reach, the hidden scene change
    A = os.path.expanduser("~/edgeqgate_data/seminar_assets")
    slot = lambda k: ST[str(int(k) + 1)] - ST[k]
    REL = [r for r in REL if r[0] not in ("1", "4", "5", "6")] + [
        ("6", 0.0, slot("6"), "clip", ("video/assets/dashboard_walkthrough.mp4", 0.0, 1, 0), "QuantGate audit board · screen capture: validate first → preflight → not yet"),
        ("1", 0.0, slot("1"), "video", (LOGO,), None),
        ("4", 0.0, 4.8, "chart", ("what_moved",), None),
        ("4", 4.8, 8.0, "clip", (f"{E}/yellow_can_2.mp4", 4.0, 1, 0), "Unseen yellow can · block result 48/48 (side view of a demonstration)"),
        ("4", 8.0, 12.3, "clip", (f"{C}/v1_nopad_drop.mp4", 4.0, 4, 0), "Gripper pads removed: the block finished 8/24 (overhead, 4×)"),
        ("4", 12.3, 14.8, "image", (f"{SHOTS}/pos_strip.png",), "50 new demos at −4…+4 cm · fine-tuned 20k steps on Nebius Jobs"),
        ("4", 14.8, slot("4"), "image", (f"{R}/fig_ft_reach.png",), "Reach, blinded, 12 vs 12 per condition · re-tested after a scene fix: same readings"),
        ("5", 0.0, 8.6, "clip", (f"{A}/wrist_before_after.mp4", 3.0, 1, 0), None),
        ("5", 8.6, 17.4, "table", ("Cosmos-Reason2 end-of-trial judge", [("first setup", "1/21 failures caught", "bad"), ("validated prompt, held-out recordings", "20/21 · 5/252 false alarms", "ok"), ("same prompt, live new trials", "22/24 · 2/72 false alarms", "ok")]), None),
        ("5", 17.4, slot("5"), "scroll", (f"{SHOTS}/report_meta.png",), "Deployment report: code writes verdicts and numbers; Nemotron (Token Factory) explains"),
    ]
    REL = [(k, a, (slot(k) if k == "2" and b == 37.525 else b), kind, args, chip) for k, a, b, kind, args, chip in REL]
    REL.sort(key=lambda r: (int(r[0]), r[1]))
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

def table_card(title, rows):   # v9: the Cosmos judge figures as a small light table, like the dashboard panels
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im); x0, y0, x1 = 300, 270, W - 300; rh = 112
    d.rounded_rectangle((x0, y0, x1, y0 + 120 + rh * len(rows)), 22, fill=(241, 243, 242))
    d.text((x0 + 56, y0 + 36), title, font=F(46, True), fill=(20, 24, 28))
    for i, (k, v, tone) in enumerate(rows):
        y = y0 + 120 + rh * i; d.line((x0 + 56, y, x1 - 56, y), fill=(210, 216, 214), width=2)
        d.text((x0 + 56, y + 32), k, font=F(38), fill=(60, 70, 78))
        col = {"bad": (176, 52, 44), "ok": (16, 128, 110)}.get(tone, (20, 24, 28)); w = d.textlength(v, font=F(40, True))
        d.text((x1 - 56 - w, y + 30), v, font=F(40, True), fill=col)
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
    elif kind == "cardfade":   # note 1 (+ follow-up): large, centred, each word brightens as it is spoken
        lines = args[0].split("\n"); f = F(72, True); words = []; y = (H - 120 * len(lines)) / 2 - 40
        probe = ImageDraw.Draw(Image.new("RGB", (W, H)))
        for ln in lines:
            x = (W - probe.textlength(ln, font=f)) / 2
            for w_ in ln.split(" "):
                words.append((w_, x, y)); x += probe.textlength(w_ + " ", font=f)
            y += 120
        # word timing: the narration sentence that matches this card, split by character position
        sub = next((x for x in SUBS if x[0] <= t0 + 0.5 < x[1] + 0.5 and x[2].split()[0] == words[0][0]), (t0, t1, ""))
        total = sum(len(w_) + 1 for w_, _, _ in words); acc = 0; starts = []
        for w_, _, _ in words: starts.append(sub[0] + (sub[1] - sub[0]) * acc / total); acc += len(w_) + 1
        for i in range(n):
            t = t0 + i / FPS; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
            for (w_, x, yy), st in zip(words, starts):
                a_ = min(1.0, max(0.0, (t - st + 0.05) / 0.35)); col = tuple(int(BG[k] + (INK[k] - BG[k]) * a_) for k in range(3))
                if a_ > 0: d.text((x, yy), w_, font=f, fill=col)
            yield im
    elif kind == "overlay":    # review 7: the chart over real robot footage (left part of the frame stays the robot)
        path, s0, speed, cname = args; gen = pc.frames(path, s0, (t1 - t0) * speed + 0.5, fps=FPS / speed, size=None); last = None; fn = vchart.CHARTS[cname]
        for i in range(n):
            try: last = next(gen)[1]
            except StopIteration: pass
            base = Image.new("RGB", (W, H), BG); f = fit(last, W, H); base.paste(f, ((W - f.width) // 2, (H - f.height) // 2))
            panel = fn(i / FPS, t1 - t0).crop((60, 110, 1860, 1010)).resize((1100, 550)); a_ = min(1.0, i / (0.4 * FPS))
            region = base.crop((770, 120, 1870, 670)); base.paste(Image.blend(region, panel, a_), (770, 120)); yield base
    elif kind == "table":
        im = table_card(*args)
        for i in range(n): yield im.copy()
    elif kind == "chart":      # notes 3-7
        fn = vchart.CHARTS[args[0]]
        for i in range(n): yield fn(i / FPS, t1 - t0)
    elif kind == "video":      # the user's logo animation, fitted to 1080 high on its own background
        c_ = av.open(args[0]); fr_ = [f.to_image().convert("RGB") for f in c_.decode(video=0)]; c_.close(); bgc = fr_[0].getpixel((8, 8))
        for i in range(n):
            f = fit(fr_[min(len(fr_) - 1, int(i * len(fr_) / n))], W, H); base = Image.new("RGB", (W, H), bgc); base.paste(f, ((W - f.width) // 2, (H - f.height) // 2)); yield base
    elif kind == "scroll":     # note 8: the whole report, sliding from top to bottom
        im = Image.open(args[0]).convert("RGB"); f = fit(im, 1700, 10 ** 6); view = H - 140; travel = max(f.height - view, 0)
        for i in range(n):
            u = i / max(n - 1, 1); u = 0 if u < 0.06 else (1 if u > 0.94 else (u - 0.06) / 0.88); u = u * u * (3 - 2 * u)
            y = int(travel * u); base = Image.new("RGB", (W, H), BG); pad = Image.new("RGB", (f.width + 40, view + 20), (241, 243, 242))
            base.paste(pad, ((W - pad.width) // 2, 100)); base.paste(f.crop((0, y, f.width, y + view)), ((W - f.width) // 2, 110)); yield base
    elif kind == "endkick":    # note 9: logo end frame + kick line + repository
        # the user's logo-only outro animation (note 9 follow-up): its wordmark build (9 s to the end) fitted to the slot
        c_ = av.open(OUTRO); st_ = c_.streams.video[0]; fr_ = [f.to_image().convert("RGB") for f in c_.decode(video=0) if float(f.pts * st_.time_base) >= 9.0]; c_.close()
        bgc = fr_[0].getpixel((8, 8))
        for i in range(n):
            lg = fit(fr_[min(len(fr_) - 1, int(i * len(fr_) / n))], int(W * 0.62), int(H * 0.62))
            base = Image.new("RGB", (W, H), bgc); base.paste(lg, ((W - lg.width) // 2, 40)); d = ImageDraw.Draw(base); a_ = min(1.0, max(0.0, (i / FPS - 1.2) / 0.8))
            col = tuple(int(bgc[k] + (INK[k] - bgc[k]) * a_) for k in range(3)); f1 = F(60, True); txt = args[0]; w = d.textlength(txt, font=f1); d.text(((W - w) / 2, 760), txt, font=f1, fill=col)
            u = "github.com/goodboychan/nebius-physical-ai"; w = d.textlength(u, font=F(30)); d.text(((W - w) / 2, 870), u, font=F(30), fill=tuple(int(bgc[k] + (INK2[k] - bgc[k]) * a_) for k in range(3)))
            yield base
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

# UPSCALE=2: frames are drawn at 1920x1080 and encoded at 3840x2160 (Lanczos). YouTube gives 4K uploads a much higher
# bitrate, so even 1080p playback is sharper than a 1080p upload; CRF and preset can be set from the environment
SCALE = int(os.environ.get("UPSCALE", "1"))
o = av.open(OUT, "w", options={"movflags": "+faststart"}); vs = o.add_stream("libx264", rate=FPS)
vs.width, vs.height, vs.pix_fmt = W * SCALE, H * SCALE, "yuv420p"
vs.options = {"crf": os.environ.get("CRF", "21"), "preset": os.environ.get("PRESET", "medium"), "profile": "high", "tune": "film"}
a_in = av.open(f"docs/narration/narration_{NARR}_am_michael.m4a"); as_ = o.add_stream_from_template(a_in.streams.audio[0], opaque=True)
k = 0
for seg in SEG:
    for im in frames_of(seg):
        t = k / FPS; d = ImageDraw.Draw(im)
        if seg[4]: chip(d, seg[4])
        if NARR == "v6" and 0.3 <= t < 3.3:   # v9: one number in the first seconds
            a_ = min(1.0, (t - 0.3) / 0.4, (3.3 - t) / 0.4); hl = "673 blinded real-arm trials · evidence before deployment"; fh = F(52, True)
            w = d.textlength(hl, font=fh); x = (W - w) / 2; d.rounded_rectangle((x - 36, 120, x + w + 36, 220), 18, fill=(16, 20, 19))
            d.text((x, 136), hl, font=fh, fill=tuple(int(16 + (c - 16) * a_) for c in (240, 244, 244)))
        if seg[2] not in ("cardfade", "endkick"): subtitle(d, t)   # the card and the kick show the spoken line already
        if SCALE != 1: im = im.resize((W * SCALE, H * SCALE), Image.LANCZOS)
        for p in vs.encode(av.VideoFrame.from_image(im)): o.mux(p)
        k += 1
    print(f"{seg[0]:6.1f}-{seg[1]:6.1f} {seg[2]:5} frames to {k}", flush=True)
for p in vs.encode(): o.mux(p)
for p in a_in.demux(a_in.streams.audio[0]):
    if p.dts is None: continue
    p.stream = as_; o.mux(p)
o.close(); print("written", OUT, k / FPS, "s")
