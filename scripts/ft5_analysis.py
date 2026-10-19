"""Re-test blocks, amendment 8 (docs/finetune_position_preregistration.md §19): T6PR and TYPR, the §17 scenes without the red
markers. Written before the first trial. Runs only after artifacts/freeze/ft5_post.json exists. Outcome as in §4: consensus re-judge ∧ released ∧ no contact ∧ not aborted.
  Primary (TYP, yellow can at the +3 cm mark: a held-out object at a held-out position): FT − OLD success difference,
    Newcombe 95%; improvement detected iff the lower bound > 0 (the T1 rule).
  Secondary (T6P and T6M, cola can at +6 / −6 cm, beyond the ±4 cm demonstration range): the same rule, each reported
    separately, no multiplicity adjustment of the primary.
  Descriptive: failures by trial with the blind mode label (--modes), and blocks not run (stop rule, reach check).
Usage: python scripts/ft5_analysis.py <sealed dir> <rejudge json ...> --out <json> [--modes <json>]"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stress_analysis as sa
from g6_analysis import newcombe
if not os.path.exists("artifacts/freeze/ft5_post.json"): sys.exit("ft5_post.json이 없다")
a = sys.argv[1:]; opt = lambda k: a[a.index(k) + 1] if k in a else None
out, modes_p, sdir = opt("--out"), opt("--modes"), a[0]
for f in a[1:min(a.index(k) for k in ("--out", "--modes") if k in a)]: sa.REJ.update(json.load(open(f)))
MODES = (lambda d: d.get("labels", d))(json.load(open(modes_p))) if modes_p else {}   # {"<block>/<trial>": "placement disturbance" | "grasp" | "transport" | "other"}
ROLE = {"T6PR": "primary", "TYPR": "secondary"}; rep = {}
for blk, role in ROLE.items():
    p = os.path.join(sdir, f"stress_ft5_{blk}_sealed.jsonl")
    if not os.path.exists(p): rep[blk] = {"role": role, "run": False}; continue
    rows = sa.load(p); cs = sa.cells_of(rows)
    r = {"role": role, "run": True, "cells": {c: {"k": int(sum(v["s"])), "n": len(v["s"])} for c, v in cs.items()},
         "failures": {c: [{"trial": x["trial"], "mode": MODES.get(f"{blk}/{x['trial']}")} for x in rows if x["cell"] == c and not x["success"]] for c in cs}}
    if "FT-FP16" in cs and "VC-025" in cs:
        kf, nf = int(sum(cs["FT-FP16"]["s"])), len(cs["FT-FP16"]["s"]); ko, no = int(sum(cs["VC-025"]["s"])), len(cs["VC-025"]["s"])
        lo, hi = newcombe(kf, nf, ko, no)
        r["test"] = {"ft": [kf, nf], "old": [ko, no], "diff_pp": (kf / nf - ko / no) * 100, "newcombe95_pp": [lo * 100, hi * 100],
                     "improvement_detected": lo > 0}
    rep[blk] = r
def clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)): return None
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    return o
json.dump(clean(rep), open(out, "w"), indent=1, allow_nan=False); print(json.dumps(clean(rep), indent=1)[:1500])
