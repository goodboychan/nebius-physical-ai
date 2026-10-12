"""Narration audio from docs/narration/tts_input.json with Kokoro-82M (Apache-2.0), one WAV per scene.
espeak-ng is not usable on this host, so the dictionary-only G2P runs and missing words are given explicit phonemes in
the input. It prints each scene's duration against its target.
Usage: <venv with kokoro>/python make_narration.py <out dir> [voice] [speed]"""
import json, os, sys, types
fake = types.ModuleType("misaki.espeak")
class _NoEspeak:
    def __init__(self, *a, **k): raise RuntimeError("espeak disabled")
fake.EspeakFallback = fake.EspeakG2P = _NoEspeak; sys.modules["misaki.espeak"] = fake
import misaki; misaki.espeak = fake
import numpy as np, soundfile as sf
from kokoro import KPipeline

out = sys.argv[1]; voice = sys.argv[2] if len(sys.argv) > 2 else "am_michael"; speed = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "narration", "tts_input.json")))
os.makedirs(out, exist_ok=True); p = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M"); tot = 0
for k, text in cfg["scenes"].items():
    a = np.concatenate([x for _, _, x in p(text, voice=voice, speed=speed)]); d = len(a) / 24000; tot += d
    sf.write(f"{out}/scene{k}_{voice}.wav", a, 24000)
    print(f"scene {k}: {d:5.1f} s (target {cfg['targets_s'][k]} s){'  <-- long' if d > cfg['targets_s'][k] else ''}")
print(f"total {tot:.1f} s")
