"""Fine-tune v2 blocks, amendment 9 (docs/finetune_position_preregistration.md §21). Written before the first trial.
Runs only after artifacts/freeze/ft6_post.json exists. Outcome as in §4: consensus re-judge ∧ released ∧ no contact ∧ not aborted.
  Primary (TYP2, yellow can at +3 cm) and secondary (T6P2, cola can at +6 cm): FT2 − FT success difference, Newcombe 95%;
    improvement detected iff the lower bound > 0 (the T1 rule), each reported separately.
  Guard (T0G, cola can at the training mark): descriptive; the difference and its Newcombe 95% interval are reported, and a
    drop (upper bound < 0) is flagged. No replacement decision follows from it.
  Descriptive: failures by trial with the blind mode label (--modes).
Usage: python scripts/ft6_analysis.py <sealed dir> <rejudge json ...> --out <json> [--modes <json>] [--post <json>]"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stress_analysis as sa
from g6_analysis import newcombe
a = sys.argv[1:]; opt = lambda k: a[a.index(k) + 1] if k in a else None
POST = opt("--post") or "artifacts/freeze/ft6_post.json"   # --post only for the dry run on relabelled data
if not os.path.exists(POST): sys.exit("ft6_post.json이 없다")
out, modes_p, sdir = opt("--out"), opt("--modes"), a[0]
for f in a[1:min(a.index(k) for k in ("--out", "--modes", "--post") if k in a)]: sa.REJ.update(json.load(open(f)))
MODES = (lambda d: d.get("labels", d))(json.load(open(modes_p))) if modes_p else {}
ROLE = {"TYP2": "primary", "T6P2": "secondary", "T0G": "guard"}; rep = {}
for blk, role in ROLE.items():
    p = os.path.join(sdir, f"stress_ft6_{blk}_sealed.jsonl")
    if not os.path.exists(p): rep[blk] = {"role": role, "run": False}; continue
    rows = sa.load(p); cs = sa.cells_of(rows)
    r = {"role": role, "run": True, "cells": {c: {"k": int(sum(v["s"])), "n": len(v["s"])} for c, v in cs.items()},
         "failures": {c: [{"trial": x["trial"], "mode": MODES.get(f"{blk}/{x['trial']}")} for x in rows if x["cell"] == c and not x["success"]] for c in cs}}
    if "FT2-FP16" in cs and "FT-FP16" in cs:
        k2, n2 = int(sum(cs["FT2-FP16"]["s"])), len(cs["FT2-FP16"]["s"]); k1, n1 = int(sum(cs["FT-FP16"]["s"])), len(cs["FT-FP16"]["s"])
        lo, hi = newcombe(k2, n2, k1, n1)
        r["test"] = {"ft2": [k2, n2], "ft": [k1, n1], "diff_pp": (k2 / n2 - k1 / n1) * 100, "newcombe95_pp": [lo * 100, hi * 100]}
        if role == "guard": r["test"]["drop_flagged"] = hi < 0
        else: r["test"]["improvement_detected"] = lo > 0
    rep[blk] = r
def clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)): return None
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    return o
json.dump(clean(rep), open(out, "w"), indent=1, allow_nan=False); print(json.dumps(clean(rep), indent=1)[:1500])
