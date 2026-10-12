"""Clip of real teleoperated demonstrations from the LOCK-1 dataset: overhead (left) and wrist camera (right), real
time, with a label bar. Frames come from the dataset videos at each episode's from/to timestamps, unedited.
Usage: python make_demo_clip.py <dataset_root> <out.mp4> <episode> [<episode> ...]"""
import glob, sys
import av, numpy as np, pandas as pd
from PIL import Image, ImageDraw, ImageFont

root, out = sys.argv[1:3]; eps = [int(x) for x in sys.argv[3:]]
E = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{root}/meta/episodes/*/*.parquet"))]).set_index("episode_index")
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
TW, TH, WW, BAR = 640, 480, 768, 34

def clip(cam, ep):
    r = E.loc[ep]; k = f"videos/observation.images.{cam}"
    p = f"{root}/{k}/chunk-{int(r[k + '/chunk_index']):03d}/file-{int(r[k + '/file_index']):03d}.mp4"
    a, b = r[k + "/from_timestamp"], r[k + "/to_timestamp"]; c = av.open(p); st = c.streams.video[0]; fs = []
    for f in c.decode(st):
        t = float(f.pts * st.time_base)
        if a - 1e-3 <= t < b - 1e-3: fs.append(f.to_image())
        elif t >= b: break
    c.close(); return fs

o = av.open(out, "w", options={"movflags": "+faststart"}); s = o.add_stream("libx264", rate=30)
s.width, s.height, s.pix_fmt = TW + WW, TH + BAR, "yuv420p"; s.options = {"crf": "25", "preset": "slow"}
for ep in eps:
    top, wr = clip("top", ep), clip("wrist", ep)
    for i in range(min(len(top), len(wr))):
        img = Image.new("RGB", (TW + WW, TH + BAR), (20, 24, 28)); img.paste(top[i], (0, BAR)); img.paste(wr[i].resize((WW, TH)), (TW, BAR))
        d = ImageDraw.Draw(img)
        d.text((10, 7), f"teleoperated demo · episode {ep} · overhead", fill=(230, 234, 233), font=font)
        d.text((TW + 10, 7), "wrist camera (OpenMV AE3)", fill=(230, 234, 233), font=font)
        d.text((TW + WW - 190, 7), f"1x  t={i / 30:4.1f}s", fill=(150, 160, 158), font=font)
        for p in s.encode(av.VideoFrame.from_ndarray(np.asarray(img), format="rgb24")): o.mux(p)
for p in s.encode(): o.mux(p)
o.close(); print(out, eps)
