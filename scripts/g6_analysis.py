"""G6 analysis (QuantGate primary/secondary + EX-4 + the AEP-facing registration v1).

Runs **only after LOCK-3** (`artifacts/freeze/lock3.json` must exist). The one exception is `--k2-interim`, which
evaluates the pre-defined K2 rule (decision_log 2026-10-10) and prints only "fired / not fired" plus a readiness
check. `--synthetic` runs the whole pipeline on generated data to test the code. The synthetic run never reads the
sealed log.

Inputs: the sealed trial logs (`g6_main_sealed.jsonl`, `g6_retest_sealed.jsonl`) and `artifacts/freeze/lock2.json`.
Output: a JSON report. Numbers in prose must come from this report.

Usage:
  python scripts/g6_analysis.py --sealed-dir <dir> --out <report.json>        (after LOCK-3)
  python scripts/g6_analysis.py --sealed-dir <dir> --k2-interim
  python scripts/g6_analysis.py --synthetic --out /tmp/synth.json
"""
import argparse, json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from edgeqgate.hashing import seed_from

SEED = "PREREG-SEED-2026-09-14"
Z = 1.959963984540054


def wilson(k, n, z=Z):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def newcombe(k1, n1, k2, n2, z=Z):
    """Newcombe hybrid-score CI for p1 - p2 (method 10)."""
    p1, p2 = k1 / n1, k2 / n2; l1, u1 = wilson(k1, n1, z); l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    return (d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def boot_ci(a, b, stat, n_boot, seed_key, conf):
    """Unpaired percentile bootstrap of stat(a) - stat(b)."""
    rng = np.random.default_rng(seed_from(SEED, seed_key))
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0 or len(b) == 0: return (float("nan"), float("nan"), float("nan"))
    d = np.array([stat(rng.choice(a, len(a))) - stat(rng.choice(b, len(b))) for _ in range(n_boot)])
    lo, hi = np.percentile(d, [(1 - conf) / 2 * 100, (1 + conf) / 2 * 100])
    return (float(stat(a) - stat(b)), float(lo), float(hi))


def aep_decision(lo, hi, tol):
    if hi < tol: return "tolerance_compatible"
    if lo > tol: return "materially_degraded"
    return "indeterminate"


def load(sealed_dir, session):
    p = os.path.join(sealed_dir, f"g6_{session}_sealed.jsonl")
    if not os.path.exists(p): return []
    rows = [json.loads(l) for l in open(p)]
    return [r for r in rows if not r.get("invalid")]


def per_cell(rows):
    out = {}
    for r in rows:
        c = out.setdefault(r["cell"], {"n": 0, "k": 0, "place": [], "not_detected": 0, "aborted": 0, "arms": set()})
        c["n"] += 1; c["k"] += int(r["success"]); c["arms"].add(r["arm"]); c["aborted"] += int(r["aborted"])
        if not r["aborted"]:
            d = r["judge_auto"].get("base_dist_px")
            if d is None: c["not_detected"] += 1
            else: c["place"].append(float(d))
    for c in out.values(): c["arms"] = sorted(c["arms"])
    return out


def pooled(cells, names):
    k = sum(cells[c]["k"] for c in names if c in cells); n = sum(cells[c]["n"] for c in names if c in cells)
    pl = [x for c in names if c in cells for x in cells[c]["place"]]
    return k, n, pl


def k2_interim(cells, plan):
    int8 = [c for a, cs in plan["arms"].items() if a not in ("ARM-FP32", "ARM-RETEST") for c in cs]
    ready = all(cells.get(c, {"n": 0})["n"] >= 8 for c in int8 + ["VC-000"])
    if not ready:
        return {"ready": False, "min_n": min(cells.get(c, {"n": 0})["n"] for c in int8 + ["VC-000"])}
    f = cells["VC-000"]
    any_sep = any(newcombe(f["k"], f["n"], cells[c]["k"], cells[c]["n"])[0] > 0 for c in int8)
    return {"ready": True, "k2_fired": not any_sep}


def analyse(main, retest, lock2, n_boot=10000):
    plan = lock2["arm_plan"]; rk = lock2["rankings"]; A = plan["arms"]
    cells = per_cell(main); rep = {"n_trials_main": len(main), "n_trials_retest": len(retest)}
    rep["cells"] = {c: {"n": v["n"], "k": v["k"], "rate": v["k"] / v["n"], "wilson95": wilson(v["k"], v["n"]),
                        "place_mean": float(np.mean(v["place"])) if v["place"] else None,
                        "place_median": float(np.median(v["place"])) if v["place"] else None,
                        "not_detected": v["not_detected"], "aborted": v["aborted"], "arms": v["arms"]} for c, v in cells.items()}
    def contrast(name, g1, g2):
        k1, n1, _ = pooled(cells, g1); k2, n2, _ = pooled(cells, g2)
        same = sorted(g1) == sorted(g2)
        rep[name] = {"group1": g1, "group2": g2, "k1": k1, "n1": n1, "k2": k2, "n2": n2,
                     "diff": (k1 / n1 - k2 / n2) if n1 and n2 else None,
                     "newcombe95": newcombe(k1, n1, k2, n2) if n1 and n2 and not same else None,
                     "note": "identical cell sets: no contrast" if same else None}
    top = lambda s: [c for c in rk[s] if c != "VC-025"][:3]
    contrast("EP-1", A["ARM-AUDIT"], A["ARM-RANDOM"])
    contrast("ES-1", top("score_align"), top("score_mag"))
    contrast("ES-2", top("score_align"), top("score_cheap_A"))
    contrast("ES-3", top("score_align"), top("score_cheap_B"))
    contrast("ES-4", A["ARM-AUDIT"], A["ARM-LOW"])
    rc = plan["retest_cell"]; rt = per_cell(retest).get(rc)
    if rt and rc in cells:
        rep["ES-5"] = {"cell": rc, "main": [cells[rc]["k"], cells[rc]["n"]], "retest": [rt["k"], rt["n"]],
                       "newcombe95": newcombe(cells[rc]["k"], cells[rc]["n"], rt["k"], rt["n"])}
    rep["K2_interim_rule"] = k2_interim(cells, plan)
    # AEP registration v1
    best, worst = A["ARM-AUDIT"], A["ARM-LOW"]
    kb, nb, pb = pooled(cells, best); kw, nw, pw = pooled(cells, worst)
    sb = [1.0] * kb + [0.0] * (nb - kb); sw = [1.0] * kw + [0.0] * (nw - kw)
    ceiling = nb and nw and kb / nb >= 0.95 and kw / nw >= 0.95
    e1 = boot_ci(sb, sw, np.mean, n_boot, "AEP-physical-v1/Q1/E1", 0.975)   # best - worst = degradation
    e2 = boot_ci(pw, pb, np.mean, n_boot, "AEP-physical-v1/Q1/E2", 0.975)   # worst - best = degradation
    rep["AEP_Q1"] = {"E1": {"degradation_pp": e1[0] * 100, "ci_pp": [e1[1] * 100, e1[2] * 100],
                            "decision": "indeterminate (ceiling)" if ceiling else aep_decision(e1[1] * 100, e1[2] * 100, 10)},
                     "E2": {"degradation_px": e2[0], "ci_px": [e2[1], e2[2]], "decision": aep_decision(e2[1], e2[2], 5)},
                     "ceiling_rule_applied": bool(ceiling)}
    rep["AEP_Q1"]["falsified"] = any(v["decision"] == "materially_degraded" for k, v in rep["AEP_Q1"].items() if k in ("E1", "E2"))
    f = cells.get("VC-000"); q2 = {}
    if f:
        sf = [1.0] * f["k"] + [0.0] * (f["n"] - f["k"])
        for c in [c for a, cs in A.items() if a not in ("ARM-FP32", "ARM-RETEST") for c in cs]:
            if c not in cells: continue
            v = cells[c]; sc = [1.0] * v["k"] + [0.0] * (v["n"] - v["k"])
            d1 = boot_ci(sf, sc, np.mean, n_boot, f"AEP-physical-v1/Q2/{c}/E1", 0.9975)
            d2 = boot_ci(v["place"], f["place"], np.mean, n_boot, f"AEP-physical-v1/Q2/{c}/E2", 0.9975)
            q2[c] = {"E1": aep_decision(d1[1] * 100, d1[2] * 100, 10), "E1_ci_pp": [d1[1] * 100, d1[2] * 100],
                     "E2": aep_decision(d2[1], d2[2], 5), "E2_ci_px": [d2[1], d2[2]]}
    rep["AEP_Q2"] = q2
    # Q3 / EX-4: Spearman between frozen rank and per-cell mean placement (INT8 cells with data)
    from scipy.stats import spearmanr
    rng = np.random.default_rng(seed_from(SEED, "EX-4"))
    ex4 = {}
    for s in ("score_align", "score_mag", "score_cheap_A", "score_cheap_B", "score_cheap_C"):
        cs = [c for c in rk[s] if c in cells and c != "VC-000" and cells[c]["place"]]
        if len(cs) < 4: continue
        x = np.array([rk[s].index(c) for c in cs], float); y = np.array([np.mean(cells[c]["place"]) for c in cs])
        rho = spearmanr(x, y).statistic
        perm = np.array([spearmanr(x, rng.permutation(y)).statistic for _ in range(10000)])
        ex4[s] = {"n_cells": len(cs), "spearman": float(rho), "perm_p_two_sided": float((np.abs(perm) >= abs(rho)).mean())}
    rep["EX-4"] = ex4
    return rep


def synthetic(lock2):
    rng = np.random.default_rng(0); rows = []; plan = lock2["arm_plan"]
    for arm, cs in plan["arms"].items():
        for c in cs:
            n = plan["trials_per_cell"][arm]; p = 0.98 if arm in ("ARM-FP32", "ARM-AUDIT") else 0.9
            for i in range(n):
                ok = rng.random() < p
                rows.append({"cell": c, "arm": arm, "success": bool(ok), "aborted": False, "invalid": False,
                             "judge_auto": {"base_dist_px": float(rng.normal(9 if arm != "ARM-LOW" else 13, 3)) if ok else None},
                             "session": "retest" if arm == "ARM-RETEST" else "main"})
    return [r for r in rows if r["session"] == "main"], [r for r in rows if r["session"] == "retest"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sealed-dir"); ap.add_argument("--out"); ap.add_argument("--k2-interim", action="store_true")
    ap.add_argument("--synthetic", action="store_true"); ap.add_argument("--n-boot", type=int, default=10000)
    a = ap.parse_args()
    lock2 = json.load(open("artifacts/freeze/lock2.json"))
    if a.synthetic:
        m, r = synthetic(lock2); rep = analyse(m, r, lock2, n_boot=a.n_boot); rep["SYNTHETIC"] = True
    elif a.k2_interim:
        cells = per_cell(load(a.sealed_dir, "main")); print(json.dumps(k2_interim(cells, lock2["arm_plan"]))); sys.exit(0)
    else:
        if not os.path.exists("artifacts/freeze/lock3.json"):
            sys.exit("LOCK-3 기록이 없다. 본 세션·RETEST 완료 후 lock3을 쓰고 실행한다 (§8 LOCK-3)")
        rep = analyse(load(a.sealed_dir, "main"), load(a.sealed_dir, "retest"), lock2, n_boot=a.n_boot)
    json.dump(rep, open(a.out, "w"), indent=1, default=lambda o: list(o) if isinstance(o, (set, tuple)) else str(o))
    print("written", a.out)
