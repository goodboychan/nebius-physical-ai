"""Data-collection sequence for the video (scene 1b): segments of the phone videos recorded during the position
fine-tune demos (10/13, real data collection, not a re-enactment), plus the robot's own camera view. Output: 1920x1080,
30 fps, H.264, no audio, with a caption bar. Segments are cut, not sped up.
Usage: python make_datacollection_clip.py <phone video dir> <demo clip mp4> <out.mp4>"""
import sys, os
import av, numpy as np
from PIL import Image, ImageDraw, ImageFont

src, demo, out = sys.argv[1:4]
SEG = [("20261013_222801.mp4", 1.0, 5.0, "Real data collection: a person moves the leader arm, the robot copies it"),
       ("20261013_222603.mp4", 4.5, 7.5, "Teleoperation: leader (front) to follower (back)"),
       ("20261013_222234.mp4", 4.0, 6.5, "50 targeted demos at 5 start positions (-4 to +4 cm)"),
       (demo, 2.0, 5.0, "What the policy learns from: overhead and wrist cameras")]
W, H, FPS = 1920, 1080, 30
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
o = av.open(out, "w", options={"movflags": "+faststart"}); s = o.add_stream("libx264", rate=FPS)
s.width, s.height, s.pix_fmt = W, H, "yuv420p"; s.options = {"crf": "22", "preset": "slow"}
for f, t0, t1, cap in SEG:
    p = f if os.path.isabs(f) else os.path.join(src, f)
    c = av.open(p); st = c.streams.video[0]; nxt = t0
    for fr in c.decode(st):
        t = float(fr.pts * st.time_base)
        if t < nxt: continue
        if t > t1: break
        nxt += 1 / FPS
        im = fr.to_image(); k = min(W / im.width, (H - 96) / im.height); im = im.resize((int(im.width * k), int(im.height * k))); canvas = Image.new("RGB", (W, H)); canvas.paste(im, ((W - im.width) // 2, (H - 96 - im.height) // 2))
        d = ImageDraw.Draw(canvas, "RGBA"); d.rectangle([0, H - 96, W, H], fill=(10, 14, 16, 190)); d.text((48, H - 74), cap, font=font, fill=(235, 240, 238))
        for pk in s.encode(av.VideoFrame.from_image(canvas)): o.mux(pk)
    c.close()
for pk in s.encode(): o.mux(pk)
o.close(); print("written", out)
