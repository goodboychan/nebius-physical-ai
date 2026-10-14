"""Assemble per-scene narration WAVs (make_narration.py) into one timed track plus sentence-level SRT subtitles.
Each scene starts at the sum of the previous slots (targets_s in tts_input.json, at least speech + 0.3 s).
Usage: <python with numpy+soundfile> make_narration_track.py <scene wav dir> <voice> <out.wav> <out.srt>"""
import json, os, re, sys
import numpy as np, soundfile as sf

src, voice, out_wav, out_srt = sys.argv[1:5]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "narration", "tts_input.json"))); T = d["targets_s"]; sr = 24000
plain = lambda s: re.sub(r"\[([^\]]+)\]\(/[^)]*\)", r"\1", s)
fmt = lambda x: f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(round((x % 1) * 1000)) % 1000:03d}"
t, track, srt, n = 0.0, [], [], 1
for k in sorted(d["scenes"], key=int):
    a, _ = sf.read(f"{src}/scene{k}_{voice}.wav"); lead = 0.0 if k == "1" else 0.3
    slot = max(T[k], len(a) / sr + lead); seg = np.concatenate([np.zeros(int(lead * sr)), a]); seg = np.concatenate([seg, np.zeros(max(int(slot * sr) - len(seg), 0))])
    track.append(seg); sents = [x for x in re.split(r"(?<=[.?!])\s+", plain(d["scenes"][k])) if x]; dur = len(a) / sr; tot = sum(map(len, sents)); c = t + lead
    for s_ in sents:
        e = c + dur * len(s_) / tot; srt.append(f"{n}\n{fmt(c)} --> {fmt(e)}\n{s_}\n"); n += 1; c = e
    print(f"scene {k}: start {t:6.1f} s, speech {dur:5.1f} s, slot {slot:5.1f} s"); t += slot
sf.write(out_wav, np.concatenate(track), sr); open(out_srt, "w").write("\n".join(srt)); print(f"total {t:.1f} s")
