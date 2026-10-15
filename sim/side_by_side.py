"""Side-by-side clip: the real overhead video of a rollout and its Isaac Sim twin replay (exploratory, not evidence).
Frame i of the real video is control step i; the twin frames are replay_<i>.png every N steps. Output plays at 30/N fps.
Usage: python sim/side_by_side.py <real top.mp4> <twin frame dir> <N> <title> <out.mp4>"""
import glob, os, sys
import av, numpy as np
from PIL import Image, ImageDraw, ImageFont
REAL, TW, N, TITLE, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
F = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
real = [f.to_image() for f in av.open(REAL).decode(video=0)]
tw = {int(os.path.basename(p)[7:11]): p for p in glob.glob(f"{TW}/replay_*.png")}
o = av.open(OUT, "w", options={"movflags": "+faststart"}); st = o.add_stream("libx264", rate=30 // N); st.width, st.height, st.pix_fmt = 1280, 560, "yuv420p"
st.options = {"crf": "23"}
for i in sorted(tw):
    if i >= len(real): break
    c = Image.new("RGB", (1280, 560), (16, 20, 19)); c.paste(real[i].resize((640, 480)), (0, 60)); c.paste(Image.open(tw[i]).convert("RGB").resize((640, 480)), (640, 60))
    d = ImageDraw.Draw(c); d.text((16, 14), "Real overhead camera", font=F(22), fill=(230, 234, 233)); d.text((656, 14), "Isaac Sim twin, same joint trajectory", font=F(22), fill=(230, 234, 233))
    d.text((16, 534), f"{TITLE}   step {i}", font=F(16), fill=(174, 184, 183)); d.text((656, 534), "exploratory: kinematics calibrated, contact physics not tuned", font=F(16), fill=(240, 180, 90))
    for p in st.encode(av.VideoFrame.from_image(c)): o.mux(p)
for p in st.encode(): o.mux(p)
o.close(); print("saved", OUT)
