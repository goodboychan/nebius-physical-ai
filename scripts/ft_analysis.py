"""Position fine-tune evaluation analysis (docs/finetune_position_preregistration.md §5). Written before the first trial.
Runs only after artifacts/freeze/ft_post.json exists. Outcome: consensus re-judge (stress §11) ∧ released ∧ no contact ∧ not aborted.
Primary (T1, +3 cm held out): FT − OLD success difference, Newcombe 95%; improvement detected iff the lower bound > 0.
Secondary (T0, nominal): stress_analysis.compare(ref=OLD VC-025, test=FT-FP16, conf=97.5%) -> GO / NO-GO / INSUFFICIENT_EVIDENCE.
Usage: python scripts/ft_analysis.py <sealed dir> <rejudge json ...> --out <json>"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stress_analysis as sa
from g6_analysis import newcombe
if not os.path.exists("artifacts/freeze/ft_post.json"): sys.exit("ft_post.json이 없다")
args = sys.argv[1:]; out = args[args.index("--out") + 1]; sealed = args[0]
for f in args[1:args.index("--out")]: sa.REJ.update(json.load(open(f)))
rep = {}
for blk in ("T1", "T0"):
    rows = sa.load(os.path.join(sealed, f"stress_ft_{blk}_sealed.jsonl")); cs = sa.cells_of(rows)
    rep[blk] = {"cells": {c: {"k": int(sum(v["s"])), "n": len(v["s"])} for c, v in cs.items()},
                "failures": {c: [r["trial"] for r in rows if r["cell"] == c and not r["success"]] for c in cs}}
    if blk == "T1" and "FT-FP16" in cs and "VC-025" in cs:
        kf, nf = int(sum(cs["FT-FP16"]["s"])), len(cs["FT-FP16"]["s"]); ko, no = int(sum(cs["VC-025"]["s"])), len(cs["VC-025"]["s"])
        lo, hi = newcombe(kf, nf, ko, no)
        rep[blk]["primary"] = {"ft": [kf, nf], "old": [ko, no], "diff_pp": (kf / nf - ko / no) * 100, "newcombe95_pp": [lo * 100, hi * 100],
                               "improvement_detected": lo > 0}
    if blk == "T0" and "FT-FP16" in cs and "VC-025" in cs:
        rep[blk]["secondary"] = sa.compare(cs["VC-025"], cs["FT-FP16"], "FINETUNE-v1/T0", 1 - 0.05 / 2, 10000)
def clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)): return None
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    return o
json.dump(clean(rep), open(out, "w"), indent=1, allow_nan=False); print(json.dumps(clean(rep), indent=1)[:1500])
