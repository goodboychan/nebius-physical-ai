"""G6 AEP Q1/Q2 sensitivity analysis (post-LOCK-3 correction, decision_log 2026-10-12). It does not replace the locked
`g6_analysis.py`, whose output stays as it is. This version recomputes every success (E1) decision with the Newcombe
hybrid-score interval at the same confidence as the original. The original percentile bootstrap collapses to a point
when a cell has 0 failures (for example 15/15), which made "tolerance_compatible" too easy to reach. E2 (placement) is
taken unchanged from the locked report. Each cell then gets a deployment verdict: GO (both endpoints
tolerance_compatible), NO-GO (any materially_degraded) or INSUFFICIENT_EVIDENCE (otherwise).
Also flags: ES-2 groups share VC-020 trials, so Newcombe's independence assumption does not hold; ES-3 is partial
(VC-004 has no trials).
Usage: python scripts/g6_q2_sensitivity.py <g6_analysis.json> <out.json>"""
import json, sys
from scipy.stats import norm
sys.path.insert(0, "scripts")
from g6_analysis import newcombe, aep_decision
sys.path.insert(0, "scripts"); from stress_analysis import verdict

A = json.load(open(sys.argv[1])); C = A["cells"]; f = C["VC-000"]
out = {"source": sys.argv[1], "method_E1": "Newcombe hybrid score, same confidence as locked analysis", "Q2": {}}
z2 = float(norm.ppf(1 - 0.0025 / 2))
for c, q in A["AEP_Q2"].items():
    v = C[c]; lo, hi = newcombe(f["k"], f["n"], v["k"], v["n"], z2)
    ceiling = f["k"] / f["n"] >= 0.95 and v["k"] / v["n"] >= 0.95
    d1 = "indeterminate (ceiling)" if ceiling else aep_decision(lo * 100, hi * 100, 10)
    out["Q2"][c] = {"fp32": [f["k"], f["n"]], "cell": [v["k"], v["n"]], "E1_ci_pp_newcombe99.75": [round(lo * 100, 1), round(hi * 100, 1)],
                    "E1_decision": d1, "E1_decision_locked_bootstrap": q["E1"], "E2_decision_locked": q["E2"], "verdict": verdict(d1, q["E2"])}
q1 = A["AEP_Q1"]; z1 = float(norm.ppf(1 - 0.025 / 2))
AUD, LOW = ["VC-002", "VC-020", "VC-010"], ["VC-005", "VC-007"]
kb, nb = sum(C[c]["k"] for c in AUD), sum(C[c]["n"] for c in AUD); kw, nw = sum(C[c]["k"] for c in LOW), sum(C[c]["n"] for c in LOW)
lo, hi = newcombe(kb, nb, kw, nw, z1)
out["Q1"] = {"best": [kb, nb], "worst": [kw, nw], "E1_ci_pp_newcombe97.5": [round(lo * 100, 1), round(hi * 100, 1)],
             "E1_decision": "indeterminate (ceiling)" if q1["ceiling_rule_applied"] else aep_decision(lo * 100, hi * 100, 10),
             "E2_decision_locked": q1["E2"]["decision"], "falsified": False}
out["flags"] = {"ES-2": "groups share VC-020 trials; Newcombe assumes independent samples, interval is approximate",
                "ES-3": "partial coverage: VC-004 (score_cheap_B top 3) has no trials; contrast is on 2 of 3 cells"}
out["summary"] = {v: sorted(c for c, r in out["Q2"].items() if r["verdict"] == v) for v in ("GO", "NO-GO", "INSUFFICIENT_EVIDENCE")}
json.dump(out, open(sys.argv[2], "w"), indent=1); print(json.dumps(out["summary"])); print(json.dumps(out["Q1"]))
