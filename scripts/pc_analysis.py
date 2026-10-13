"""Positive-control real-arm analysis (docs/positive_control_preregistration.md §4–§5, §8). It runs only after
artifacts/freeze/pc_post.json exists. Outcome: the consensus re-judge ∧ released ∧ no contact ∧ not aborted.
The comparison is stress_analysis.compare(ref=VC-000, test=PC-B, conf=97.5%), the same function as stress v2 and FP16.
Usage: python scripts/pc_analysis.py <sealed dir> <rejudge.json> <out.json>"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stress_analysis as sa
if not os.path.exists("artifacts/freeze/pc_post.json"): sys.exit("pc_post.json이 없다")
sealed, rj, outp = sys.argv[1:4]
sa.REJ.update(json.load(open(rj)))
rows = sa.load(os.path.join(sealed, "stress_pc_P0_sealed.jsonl")); cs = sa.cells_of(rows)
cmp_ = sa.compare(cs["VC-000"], cs["PC-B"], "POSITIVE-CONTROL-v1/P0", 1 - 0.05 / 2, 10000)
lat = {}
for r in rows: lat.setdefault(r["cell"], []).append(r["infer_ms_mean"])
rep = {"n": len(rows), "cells": {c: {"k": int(sum(v["s"])), "n": len(v["s"]), "place_mean": (sum(v["place"]) / len(v["place"])) if v["place"] else None} for c, v in cs.items()},
       "failures": {c: [r["trial"] for r in rows if r["cell"] == c and not r["success"]] for c in cs},
       "comparison": cmp_, "e2e_ms": {c: round(sum(v) / len(v), 1) for c, v in lat.items() if all(x is not None for x in v)},
       "offline_verdict": "NO-GO (artifacts/positive_control/offline_selection.json)"}
def clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)): return None
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    return o
json.dump(clean(rep), open(outp, "w"), indent=1, allow_nan=False)
print(json.dumps({k: rep[k] for k in ("cells", "failures", "e2e_ms")}, indent=1))
c = rep["comparison"]; print("E1", c["E1"]["degradation_pp"], c["E1"]["ci_pp"], c["E1"]["decision"], "| E2", c["E2"]["degradation_px"], c["E2"]["ci_px"], c["E2"]["decision"], "->", c["verdict"])
