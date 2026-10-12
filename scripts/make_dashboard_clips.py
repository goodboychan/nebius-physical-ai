"""Re-encode trial overhead videos as H.264 for the D7 board. The trial videos are AV1, which some browsers cannot play.
It trims to 2 s after the last frame with visible motion, capped at max_s. With the 60 s cap used for the board, the
whole trial is kept, because camera noise and people in view keep the motion test above threshold.
There is no speed change and no edit: each clip is the real trial video, re-encoded.
Usage: python make_dashboard_clips.py <src.mp4> <out.mp4> [max_s]"""
import sys, av, numpy as np
src, out = sys.argv[1:3]; max_s = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
c = av.open(src); st = c.streams.video[0]; fps = float(st.average_rate or 30)
frames, diffs, prev = [], [], None
for f in c.decode(st):
    a = f.to_ndarray(format="rgb24"); g = a.mean(axis=2)
    diffs.append(0.0 if prev is None else float(np.abs(g - prev).mean())); prev = g; frames.append(a)
c.close()
d = np.convolve(np.array(diffs), np.ones(15) / 15, mode="same")
moving = np.where(d > 0.6)[0]
end = min(len(frames), (moving[-1] if len(moving) else len(frames)) + int(2 * fps), int(max_s * fps))
o = av.open(out, "w", options={"movflags": "+faststart"}); s = o.add_stream("libx264", rate=int(round(fps)))
s.width, s.height, s.pix_fmt = frames[0].shape[1], frames[0].shape[0], "yuv420p"; s.options = {"crf": "27", "preset": "slow"}
for a in frames[:end]:
    for p in s.encode(av.VideoFrame.from_ndarray(a, format="rgb24")): o.mux(p)
for p in s.encode(): o.mux(p)
o.close(); print(out, f"{end / fps:.1f}s of {len(frames) / fps:.1f}s")
