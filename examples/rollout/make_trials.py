"""Writes trials.jsonl: a SYNTHETIC rollout log in the shape QuantGate reads (one JSON object per trial), for the
walkthrough in README.md. Not robot data. Two builds of one policy, 40 trials each, interleaved over two sessions:
int8 38/40, fp32 39/40, with one aborted trial. Usage: python make_trials.py"""
import json, random

rng = random.Random(20261026)
fail = {"int8": {7, 23}, "fp32": {31}}   # trial numbers (per build) that fail
rows = []
for i in range(81):
    build = "int8" if i % 2 == 0 else "fp32"; k = i // 2 + 1
    aborted = i == 80                                  # an operator abort at the end: left out by tally (--drop aborted)
    ok = not aborted and k not in fail[build]
    rows.append({"trial_id": f"T{i + 1:03d}", "session": "day1" if i < 40 else "day2", "build": build, "aborted": aborted,
                 "success": ok, "released": ok, "place_px": round(rng.gauss(9.0 if build == "fp32" else 9.6, 2.5), 1) if ok else None,
                 "rtt_ms": round(rng.uniform(70, 98) if build == "int8" else rng.uniform(90, 130), 1)})
open("trials.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
print({b: (sum(r["success"] for r in rows if r["build"] == b and not r["aborted"]), sum(r["build"] == b and not r["aborted"] for r in rows)) for b in fail})
