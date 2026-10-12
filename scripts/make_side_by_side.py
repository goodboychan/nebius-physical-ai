"""Side-by-side montage of two trial blocks (overhead camera): left block trial i next to right block trial i.
Every trial is shown in full at SPEED× (frames sampled, not edited), with a label bar: block, trial number, speed.
No outcome or engine is printed, because the stress cells are still sealed.
Usage: python make_side_by_side.py <left_dir> <left_label> <right_dir> <right_label> <out.mp4> [speed]"""
import glob, os, sys
import av, numpy as np
from PIL import Image, ImageDraw, ImageFont

ld, ll, rd, rl, out = sys.argv[1:6]; speed = int(sys.argv[6]) if len(sys.argv) > 6 else 4
L = sorted(glob.glob(f"{ld}/*_top.mp4")); R = sorted(glob.glob(f"{rd}/*_top.mp4")); n = min(len(L), len(R))
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
W, H, BAR = 640, 480, 34
o = av.open(out, "w", options={"movflags": "+faststart"}); s = o.add_stream("libx264", rate=30)
s.width, s.height, s.pix_fmt = 2 * W, H + BAR, "yuv420p"; s.options = {"crf": os.environ.get("CRF", "31"), "preset": "slow"}

def frames(p):
    c = av.open(p); fs = [f.to_ndarray(format="rgb24") for i, f in enumerate(c.decode(c.streams.video[0])) if i % speed == 0]; c.close(); return fs

for i in range(n):
    a, b = frames(L[i]), frames(R[i]); m = max(len(a), len(b))
    ta = os.path.basename(L[i]).split("_")[0]; tb = os.path.basename(R[i]).split("_")[0]
    for k in range(m):
        fa = a[min(k, len(a) - 1)]; fb = b[min(k, len(b) - 1)]
        img = Image.new("RGB", (2 * W, H + BAR), (20, 24, 28)); img.paste(Image.fromarray(fa), (0, BAR)); img.paste(Image.fromarray(fb), (W, BAR))
        d = ImageDraw.Draw(img); t = k * speed / 30
        d.text((10, 7), f"{ll} · trial {int(ta[2:])}", fill=(230, 234, 233), font=font)
        d.text((W + 10, 7), f"{rl} · trial {int(tb[2:])}", fill=(230, 234, 233), font=font)
        d.text((2 * W - 150, 7), f"{speed}x  t={t:4.1f}s", fill=(150, 160, 158), font=font)
        for p in s.encode(av.VideoFrame.from_ndarray(np.asarray(img), format="rgb24")): o.mux(p)
for p in s.encode(): o.mux(p)
o.close(); print(out, n, "pairs")
