"""G6 supplementary analysis, written after LOCK-3 (decision_log 2026-10-11).

g6_analysis.py (hash fixed in lock3.json) left out four preregistered items. This script computes them without
changing any number g6_analysis.py produces:
  - §7.5 Holm correction over H1 (EP-1) and H2 (ES-1..ES-3), two-proportion z test (pooled, two-sided)
  - ES-3 partial coverage flag (declared at LOCK-2: VC-004 had no trials)
  - EX-1 failure types per cell (from the operator's descriptions in docs/sessions/g6_operator_notes.md, by trial number)
  - EX-2 per-cell inference latency (sealed infer_ms_mean)
  - EX-3 D4 shadow-supervisor verdicts vs outcomes
Usage: python scripts/g6_supplement.py --sealed-dir <dir> --report artifacts/reports/g6_analysis.json --out <json>
"""
import argparse, json, math, os
import numpy as np

# Operator descriptions (docs/sessions/g6_operator_notes.md), main-session trial numbers
FAIL_TYPE = {49: "miss", 163: "drop_place", 180: "drop_place", 178: "drop_lift", 179: "drop_lift",
             186: "knock_over_withdraw", 188: "knock_over_withdraw"}
NEAR_MISS = [153, 182, 192, 205, 209, 224]


def two_prop_p(k1, n1, k2, n2):
    p = (k1 + k2) / (n1 + n2); se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0: return 1.0
    z = (k1 / n1 - k2 / n2) / se
    return math.erfc(abs(z) / math.sqrt(2))


def holm(ps):
    order = sorted(ps, key=ps.get); m = len(order); out = {}; run = 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (m - i) * ps[k])); out[k] = run
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--sealed-dir"); ap.add_argument("--report"); ap.add_argument("--out")
    a = ap.parse_args()
    rep = json.load(open(a.report)); lock2 = json.load(open("artifacts/freeze/lock2.json"))
    main = [json.loads(l) for l in open(os.path.join(a.sealed_dir, "g6_main_sealed.jsonl"))]
    retest = [json.loads(l) for l in open(os.path.join(a.sealed_dir, "g6_retest_sealed.jsonl"))]
    out = {"source_report": a.report}
    ps = {}
    for k in ("EP-1", "ES-1", "ES-2", "ES-3"):
        v = rep[k]
        if v.get("note"): continue
        ps[k] = two_prop_p(v["k1"], v["n1"], v["k2"], v["n2"])
    out["holm_H1_H2"] = {"raw_p": ps, "holm_p": holm(ps), "excluded": {"ES-1": "identical cell sets, no contrast"},
                         "not_in_family": ["ES-4", "ES-5"]}
    out["ES-3_coverage"] = lock2["coverage"]["ES-3"]
    cells = {}
    for r in main:
        c = cells.setdefault(r["cell"], {"arm": r["arm"], "n": 0, "fail": {}, "near_miss": [], "infer_ms": [], "step_max_ms": [],
                                         "late_chunks": 0})
        c["n"] += 1; c["infer_ms"].append(r["infer_ms_mean"]); c["step_max_ms"].append(r["step_ms_p50_p99_max"][2])
        c["late_chunks"] += r["late_chunks"]
        if not r["success"]:
            t = FAIL_TYPE.get(r["trial"], "undescribed"); c["fail"][t] = c["fail"].get(t, 0) + 1
        if r["trial"] in NEAR_MISS: c["near_miss"].append(r["trial"])
    out["EX-1_EX-2"] = {k: {"arm": v["arm"], "n": v["n"], "failures": v["fail"], "near_miss_trials": v["near_miss"],
                             "infer_ms_mean": float(np.mean(v["infer_ms"])), "infer_ms_range": [min(v["infer_ms"]), max(v["infer_ms"])],
                             "step_max_ms_median": float(np.median(v["step_max_ms"])), "late_chunks": v["late_chunks"]}
                        for k, v in sorted(cells.items())}
    def d4(rows):
        n_flag = sum(1 for r in rows if any(d not in ("CONTINUE", "UNKNOWN") for d in r.get("d4", {}).get("decisions", {})))
        fails = [r["trial"] for r in rows if not r["success"]]
        flagged_fail = [r["trial"] for r in rows if not r["success"] and any(d not in ("CONTINUE", "UNKNOWN") for d in r.get("d4", {}).get("decisions", {}))]
        lat = [r["d4"]["latency_ms"]["median"] for r in rows if r.get("d4", {}).get("latency_ms")]
        return {"trials_with_d4": sum(1 for r in rows if r.get("d4")), "trials_with_any_non_continue": n_flag,
                "failures": fails, "failures_flagged": flagged_fail,
                "verdicts_total": sum(r["d4"]["n_verdicts"] for r in rows if r.get("d4")),
                "errors_total": sum(r["d4"]["n_errors"] for r in rows if r.get("d4")),
                "latency_median_of_trial_medians_ms": float(np.median(lat)) if lat else None}
    out["EX-3"] = {"main": d4(main), "retest": d4(retest)}
    json.dump(out, open(a.out, "w"), indent=1); print("written", a.out)
