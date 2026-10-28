"""YouTube caption file from the narration SRT, with the same display spellings as the burned-in subtitles
(make_video.srt): the SRT is written for the voice ("Quant Gate", "int eight"), captions for the reader.
YouTube's automatic captions mis-hear the names ("Quanggate", "in date", "Neotron"); uploading this file replaces them.
Usage: python scripts/make_captions.py [narration version, default v10] -> docs/narration/captions_<v>_en.srt"""
import sys

V = sys.argv[1] if len(sys.argv) > 1 else "v10"
DISPLAY = (("S O one oh one", "SO-101"), ("A C T", "ACT"), ("A I", "AI"), ("int eight", "INT8"), ("Quant Gate", "QuantGate"))
out = []
for b in open(f"docs/narration/narration_{V}.srt").read().strip().split("\n\n"):
    lines = b.split("\n"); txt = " ".join(lines[2:])
    for k, v in DISPLAY: txt = txt.replace(k, v)
    out.append("\n".join(lines[:2] + [txt]))
open(f"docs/narration/captions_{V}_en.srt", "w").write("\n\n".join(out) + "\n")
print(f"written docs/narration/captions_{V}_en.srt: {len(out)} captions")
