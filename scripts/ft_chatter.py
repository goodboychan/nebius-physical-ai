"""Exploratory gripper-chatter metric, fixed in docs/finetune_position_preregistration.md §13 before unsealing.
chatter = mean |second difference| of the commanded gripper action (action[:, 5], gripper units 0–100 per step²) over a trial;
chatter_hold = the same over steps where the commanded gripper is below the midpoint of its range in that trial (closed side).
Step 1 (Orin): python ft_chatter.py measure <dir> [<dir> ...] > chatter_raw.json
Step 2 (repo): python ft_chatter.py compare chatter_raw.json <out.json>"""
import glob, json, os, sys
import numpy as np


def measure(dirs):
    out = {}
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(os.path.expanduser(d), "*_traj.npz"))):
            a = np.load(p)["action"]
            if len(a) < 3: continue
            g = a[:, 5].astype(float); d2 = np.abs(np.diff(g, 2)); mid = (g.min() + g.max()) / 2; hold = (g < mid)[2:]
            out[os.path.basename(p)[:-len("_traj.npz")]] = {"chatter": float(d2.mean()), "chatter_hold": float(d2[hold].mean()) if hold.any() else None, "steps": len(g)}
    return out


def mwu(x, y):
    from scipy.stats import mannwhitneyu
    return float(mannwhitneyu(x, y, alternative="two-sided").pvalue) if len(x) and len(y) else None


def compare(raw, out):
    C = json.load(open(raw)); groups = {}
    srcs = [("T1", "artifacts/trials/ft_unsealed/stress_ft_T1_sealed.jsonl"), ("T0", "artifacts/trials/ft_unsealed/stress_ft_T0_sealed.jsonl"),
            ("T2", "artifacts/trials/ft2_unsealed/stress_ft2_T2_sealed.jsonl"), ("FP16 block", "artifacts/trials/fp16_unsealed/stress_fp16_F0_sealed.jsonl")]
    srcs += [("G6", f) for f in sorted(glob.glob("artifacts/trials/g6_unsealed/g6_*_sealed.jsonl"))]
    for blk, f in srcs:
        if not os.path.exists(f): continue
        for l in open(f):
            r = json.loads(l)
            if r.get("aborted") or r["trial_id"] not in C: continue
            groups.setdefault((blk, r["cell"]), []).append(C[r["trial_id"]])
    med = lambda v, k: float(np.median([x[k] for x in v if x[k] is not None])) if v else None
    res = {f"{b} | {c}": {"n": len(v), "chatter_median": med(v, "chatter"), "chatter_hold_median": med(v, "chatter_hold")} for (b, c), v in sorted(groups.items())}
    get = lambda b, c, k: [x[k] for x in groups.get((b, c), []) if x[k] is not None]
    tests = {}
    for b in ("T1", "T0", "T2"):
        for k in ("chatter", "chatter_hold"): tests[f"{b}: FT vs OLD ({k})"] = mwu(get(b, "FT-FP16", k), get(b, "VC-025", k))
    for k in ("chatter", "chatter_hold"):
        old_today = sum((get(b, "VC-025", k) for b in ("T1", "T0", "T2")), [])
        tests[f"OLD today vs VC-025 in FP16 block ({k})"] = mwu(old_today, get("FP16 block", "VC-025", k))
    R = {"note": "exploratory (§13); no decision attached", "groups": res, "mann_whitney_p": tests}
    json.dump(R, open(out, "w"), indent=1); print(json.dumps(R, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "measure": print(json.dumps(measure(sys.argv[2:])))
    else: compare(sys.argv[2], sys.argv[3])
