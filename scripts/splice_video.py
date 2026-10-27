"""Replace a run of frames in a finished video and put in a new audio track (video v13, 2026-10-28: scene 6 re-voiced).
The new frames come from `make_video.py` with ONLY_SCENE, so the rest of the picture stays the frames of the earlier
master. The audio is the new narration, loudness-normalised two-pass to -16 LUFS / -1.5 dBTP like the earlier masters.
Usage: python scripts/splice_video.py <master.mp4> <patch.mp4> <first frame> <audio.m4a> <out.mp4> [crf] [preset]"""
import sys
import av

master, patch, k0, audio, out = sys.argv[1:6]; k0 = int(k0)
crf = sys.argv[6] if len(sys.argv) > 6 else "18"; preset = sys.argv[7] if len(sys.argv) > 7 else "medium"
pa = [f.to_image() for f in av.open(patch).decode(video=0)]
mi = av.open(master); ms = mi.streams.video[0]
o = av.open(out, "w", options={"movflags": "+faststart"}); vs = o.add_stream("libx264", rate=30)
vs.width, vs.height, vs.pix_fmt = ms.width, ms.height, "yuv420p"
vs.options = {"crf": crf, "preset": preset, "profile": "high", "tune": "film"}
a_in = av.open(audio); as_ = o.add_stream_from_template(a_in.streams.audio[0], opaque=True)
n = 0
for i, f in enumerate(mi.decode(video=0)):
    im = pa[i - k0] if k0 <= i < k0 + len(pa) else f.to_image()
    for p in vs.encode(av.VideoFrame.from_image(im)): o.mux(p)
    n += 1
for p in vs.encode(): o.mux(p)
for p in a_in.demux(a_in.streams.audio[0]):
    if p.dts is None: continue
    p.stream = as_; o.mux(p)
o.close(); print(f"written {out}: {n} frames, frames {k0}-{k0 + len(pa) - 1} replaced")
