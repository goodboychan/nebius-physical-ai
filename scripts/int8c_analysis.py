"""INT8 chatter block Q8, amendment 3 (docs/fp16_real_arm_preregistration.md §9). Written before the first Q8 trial.
Runs only after artifacts/freeze/int8c_post.json exists.
  Primary: gripper chatter (the finetune prereg §13 metric: mean |second difference| of the commanded gripper per trial),
    VC-002 (INT8) against VC-025 (FP16), Mann-Whitney U two-sided at alpha 0.05. The direction stated in advance is
    VC-002 > VC-025 (post hoc in G6 and the FP16 block). Confirmed iff p < 0.05 and the VC-002 median is higher.
  Secondary: chatter_hold (closed-gripper steps), the same test, reported alongside.
  Descriptive: success (consensus re-judge ∧ released ∧ no contact ∧ not aborted) with stress_analysis.compare(ref=VC-025,
    test=VC-002, 97.5%) semantics, including the ceiling rule; no approval follows from this block.
Usage: python scripts/int8c_analysis.py <sealed dir> <rejudge json> --chatter <chatter_raw.json> --out <json> [--block Q8B]"""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stress_analysis as sa
from ft_chatter import mwu
a = sys.argv[1:]; opt = lambda k: a[a.index(k) + 1] if k in a else None
BLK = opt("--block") or "Q8"; POST = {"Q8": "artifacts/freeze/int8c_post.json", "Q8B": "artifacts/freeze/int8c2_post.json"}[BLK]   # amendment 4: Q8B replaces Q8
if not os.path.exists(POST): sys.exit(f"{POST}이 없다")
out, chat_p, sdir = opt("--out"), opt("--chatter"), a[0]
for f in a[1:min(a.index(k) for k in ("--out", "--chatter", "--block") if k in a)]: sa.REJ.update(json.load(open(f)))
rows = sa.load(os.path.join(sdir, {"Q8": "stress_int8c_Q8_sealed.jsonl", "Q8B": "stress_int8c2_Q8B_sealed.jsonl"}[BLK])); cs = sa.cells_of(rows); C = json.load(open(chat_p))
rep = {"cells": {c: {"k": int(sum(v["s"])), "n": len(v["s"])} for c, v in cs.items()}}
for key in ("chatter", "chatter_hold"):
    g = {c: [C[r["trial_id"]][key] for r in rows if r["cell"] == c and r["trial_id"] in C and C[r["trial_id"]].get(key) is not None] for c in ("VC-002", "VC-025")}
    p = mwu(g["VC-002"], g["VC-025"]); m = {c: float(np.median(v)) if v else None for c, v in g.items()}
    rep[key] = {"median": m, "n": {c: len(v) for c, v in g.items()}, "mwu_p_two_sided": p,
                "confirmed_direction_int8_higher": bool(p is not None and p < 0.05 and m["VC-002"] is not None and m["VC-002"] > m["VC-025"])}
rep["primary"] = "chatter"; rep["success_descriptive"] = sa.compare(cs["VC-025"], cs["VC-002"], f"INT8C-v1/{BLK}", 1 - 0.05 / 2, 10000)
clean = lambda o: None if isinstance(o, float) and (math.isnan(o) or math.isinf(o)) else {k: clean(v) for k, v in o.items()} if isinstance(o, dict) \
    else [clean(v) for v in o] if isinstance(o, (list, tuple)) else o
json.dump(clean(rep), open(out, "w"), indent=1, allow_nan=False); print(json.dumps(clean(rep), indent=1)[:1500])
