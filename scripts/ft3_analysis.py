"""T0R analysis, amendment 6 (docs/finetune_position_preregistration.md §15). Written before the first T0R trial.
Runs only after artifacts/freeze/ft3_post.json exists. Outcome as in §4: consensus re-judge ∧ released ∧ no contact ∧ not aborted.
  Primary (replication, descriptive): FT and OLD failures in T0R by trial, with the failure mode from the operator notes and the
    video re-judge (mode labels are added by hand in --modes, written blind to cells before unsealing).
    Reading: FT failures = 0 -> "not repeated in 12"; >= 1 placement disturbance -> "the training-mark failure mode repeats";
    >= 1 but none a placement disturbance -> "FT failed at the training mark again, by a different mode".
  Secondary: T0 + T0R pooled, stress_analysis.compare(ref=OLD, test=FT, conf=97.5%). Pooling was chosen after T0 was seen
    (10/12 vs 12/12) and is reported as such. GO is unreachable at 24 vs 24 (best case: ceiling, indeterminate).
  Exploratory: gripper chatter FT vs OLD in T0R (§13 metric, MWU two-sided), against the T0 direction (FT > OLD).
Usage: python scripts/ft3_analysis.py <sealed dir T0R> <sealed dir T1/T0> <rejudge json ...> --modes <json> --chatter <raw json> --out <json>"""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stress_analysis as sa
from ft_chatter import mwu
from g6_analysis import wilson
if not os.path.exists("artifacts/freeze/ft3_post.json"): sys.exit("ft3_post.json이 없다")
a = sys.argv[1:]; opt = lambda k: a[a.index(k) + 1] if k in a else None
out, modes_p, chat_p = opt("--out"), opt("--modes"), opt("--chatter"); s3, s0 = a[0], a[1]
for f in a[2:min(a.index(k) for k in ("--out", "--modes", "--chatter") if k in a)]: sa.REJ.update(json.load(open(f)))
MODES = json.load(open(modes_p)) if modes_p else {}   # {trial number (str): "placement disturbance" | "grasp" | "transport" | "other"}
r3 = sa.load(os.path.join(s3, "stress_ft3_T0R_sealed.jsonl")); r0 = sa.load(os.path.join(s0, "stress_ft_T0_sealed.jsonl"))
c3 = sa.cells_of(r3); c0 = sa.cells_of(r0)
fail = {c: [{"trial": r["trial"], "mode": MODES.get(str(r["trial"]))} for r in r3 if r["cell"] == c and not r["success"]] for c in c3}
ft = fail.get("FT-FP16", [])
reading = ("not repeated in 12 trials" if not ft else
           "the training-mark failure mode repeats" if any(f["mode"] == "placement disturbance" for f in ft) else
           "FT failed at the training mark again, by a different mode")
pool = {c: {k: c0[c][k] + c3[c][k] for k in ("s", "place")} for c in ("FT-FP16", "VC-025")}
rep = {"T0R": {"cells": {c: {"k": int(sum(v["s"])), "n": len(v["s"])} for c, v in c3.items()}, "failures": fail,
               "primary_reading": reading,
               "ft_failure_rate_wilson95": list(wilson(len(ft), len(c3["FT-FP16"]["s"])))},
       "pooled_T0_T0R": {**sa.compare(pool["VC-025"], pool["FT-FP16"], "FINETUNE-v1/T0+T0R", 1 - 0.05 / 2, 10000),
                         "note": "pooling chosen after T0 was seen; GO unreachable at 24 vs 24"}}
if chat_p:
    C = json.load(open(chat_p)); g = {c: [C[r["trial_id"]]["chatter"] for r in r3 if r["cell"] == c and r["trial_id"] in C] for c in c3}
    rep["chatter_T0R"] = {"median": {c: float(np.median(v)) if v else None for c, v in g.items()}, "n": {c: len(v) for c, v in g.items()},
                          "mwu_p": mwu(g.get("FT-FP16", []), g.get("VC-025", [])), "T0_direction": "FT > OLD"}
clean = lambda o: None if isinstance(o, float) and (math.isnan(o) or math.isinf(o)) else {k: clean(v) for k, v in o.items()} if isinstance(o, dict) \
    else [clean(v) for v in o] if isinstance(o, (list, tuple)) else o
json.dump(clean(rep), open(out, "w"), indent=1, allow_nan=False); print(json.dumps(clean(rep), indent=1)[:1500])
