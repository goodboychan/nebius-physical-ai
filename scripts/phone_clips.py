"""Cut the user's side-view phone videos (4K60) into editing clips, aligned to the arm's motion.
Trial IDs carry the time the runner printed its prompt, before the operator pressed Enter, so the motion onset is
found in the video. The search starts at (trial-ID time - video start time) and looks for the first motion segment that
stays active for most of the next 3 s (the pick-and-place motion lasts about 15 s of the 60 s trial; the arm then holds still).
  onset <video> <start HHMMSS> <trial HHMMSS>          -> prints the onset in seconds
  cut   <video> <t0> <dur> <out.mp4> [label]           -> 1920x1080 30 fps H.264 with an optional label bar
  sbs   <left> <tl> <right> <tr> <dur> <out.mp4> <left label> <right label> [caption]  -> 1920x1080, two 960x540 panes
Set ROT=180 for takes recorded with the phone upside down. Labels are drawn by code; nothing is retimed. Output frames are sampled from the 60 fps source at 30 fps."""
import os, sys
import av, numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
hms = lambda s: int(s[:2]) * 3600 + int(s[2:4]) * 60 + int(s[4:6])


def frames(path, t0, dur, fps=30, size=None):
    """Yield (t, PIL image) at `fps` from t0 for dur seconds."""
    c = av.open(path); st = c.streams.video[0]; st.thread_type = "AUTO"
    c.seek(int(max(t0 - 1, 0) / st.time_base), stream=st, backward=True)
    nxt = t0
    for f in c.decode(st):
        t = float(f.pts * st.time_base)
        if t < nxt: continue
        if t > t0 + dur: break
        im = f.to_image()
        if os.environ.get("ROT") == "180": im = im.rotate(180)   # the phone was mounted upside down for some takes
        yield t, (im.resize(size, Image.BILINEAR) if size else im); nxt += 1 / fps
    c.close()


def onset(path, t_from, search=60):
    ts, d, prev = [], [], None
    for t, im in frames(path, t_from, search, fps=10, size=(192, 108)):
        g = np.asarray(im.convert("L"), np.float32)
        if prev is not None: ts.append(t); d.append(float(np.abs(g - prev).mean()))
        prev = g
    d = np.array(d); ts = np.array(ts); thr = max(np.percentile(d, 30) * 2.5, 1.0); act = d > thr
    for i in range(len(act)):
        w = act[i:i + 30]    # next 3 s at 10 fps
        if act[i] and len(w) >= 30 and w.mean() > 0.6: return float(ts[i])
    return None


def bar(im, text, h=54):
    W, H = im.size; out = Image.new("RGB", (W, H + h), (16, 20, 19)); out.paste(im, (0, 0))
    ImageDraw.Draw(out).text((18, H + 12), text, font=ImageFont.truetype(FONT, 28), fill=(230, 234, 233)); return out


def write(out, gen, size):
    o = av.open(out, "w", options={"movflags": "+faststart"}); s = o.add_stream("libx264", rate=30)
    s.width, s.height = size; s.pix_fmt = "yuv420p"; s.options = {"crf": os.environ.get("CRF", "23"), "preset": "medium"}
    for im in gen:
        for p in s.encode(av.VideoFrame.from_image(im)): o.mux(p)
    for p in s.encode(): o.mux(p)
    o.close()


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "onset":
        print(onset(a[1], hms(a[3]) - hms(a[2])))
    elif a[0] == "cut":
        path, t0, dur, out = a[1], float(a[2]), float(a[3]), a[4]; label = a[5] if len(a) > 5 else None
        size = (1920, 1080 - (54 if label else 0))
        write(out, ((bar(im, label) if label else im) for _, im in frames(path, t0, dur, size=size)), (1920, 1080))
    elif a[0] == "sbs":
        L, tl, R, tr, dur, out, ll, rl = a[1], float(a[2]), a[3], float(a[4]), float(a[5]), a[6], a[7], a[8]
        cap = a[9] if len(a) > 9 else ""
        f2 = ImageFont.truetype(FONT, 30); f3 = ImageFont.truetype(FONT, 26)
        def gen():
            for (_, li), (_, ri) in zip(frames(L, tl, dur, size=(960, 540)), frames(R, tr, dur, size=(960, 540))):
                im = Image.new("RGB", (1920, 1080), (16, 20, 19)); im.paste(li, (0, 150)); im.paste(ri, (960, 150)); d = ImageDraw.Draw(im)
                d.text((24, 96), ll, font=f2, fill=(230, 234, 233)); d.text((984, 96), rl, font=f2, fill=(230, 234, 233))
                if cap: d.text((24, 730), cap, font=f3, fill=(174, 184, 183))
                yield im
        write(out, gen(), (1920, 1080))
