"""Stress-test analysis (docs/stress_test_protocol.md §5). Written and hashed **before** the first stress trial.

Runs only after `artifacts/freeze/stress_lock_post.json` exists (all stress trials done), except `--synthetic`.
Inputs: the sealed stress log (`stress_S1_sealed.jsonl`, `stress_S4_sealed.jsonl`) and, for the nominal reference,
`artifacts/trials/g6_unsealed/g6_main_sealed.jsonl`.

  Primary (per condition): VC-005 (worst fidelity) vs VC-002 (best). Degradation = best - worst (E1, pp) and
    worst - best (E2, px). Unpaired percentile bootstrap, 10,000 draws. Family = 2 conditions x 2 endpoints, Bonferroni
    -> two-sided 98.75% CI. Decision: hi < tol -> tolerance_compatible, lo > tol -> materially_degraded, else
    indeterminate. Tolerances E1 10 pp, E2 5 px. Ceiling rule: both success rates >= 95% -> E1 indeterminate (ceiling).
    falsified_if: materially_degraded on any primary endpoint.
  Secondary (per condition): each INT8 cell (VC-002, VC-005, VC-020) vs VC-000 (FP32); family of 12, 99.58% CI.
    VC-020 vs VC-002 (calibration size 1024 vs 16, same composition and granularity), same family size as primary.
  Amendment 1 (before any stress trial): block S0 = nominal scene with the gripper pads removed (4 cells x 6), the
    same-hardware baseline. Descriptive per cell: S0 rate, and S1/S4 vs S0 (Newcombe 95%). G6 main is kept as a second,
    different-hardware reference.
  Descriptive: per-cell stress vs nominal (G6 main) success rate; D4 shadow verdicts; D4 end-of-trial judge vs the
    criterion outcome (agreement, confusion matrix).
Usage:
  python scripts/stress_analysis.py --sealed-dir <dir> --out <report.json>
  python scripts/stress_analysis.py --synthetic --out /tmp/stress_synth.json
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g6_analysis import wilson, newcombe, boot_ci, aep_decision

CONDS = ("S1", "S4"); BEST, WORST, FP32, PRACT = "VC-002", "VC-005", "VC-000", "VC-020"
TOL = {"E1": 10.0, "E2": 5.0}
CONF_PRIMARY = 1 - 0.05 / 4; CONF_SECONDARY = 1 - 0.05 / 12


REJ = {}   # v2 (protocol §9): {trial_id: offline re-judge}, replaces the live geometric judge for every v2 trial


def load(path):
    if not os.path.exists(path): return []
    rows = [r for r in (json.loads(l) for l in open(path)) if not r.get("invalid")]
    for r in rows:
        if REJ and r["trial_id"] in REJ:
            j = REJ[r["trial_id"]]; r["judge_live"] = r["judge_auto"]
            r["judge_auto"] = {"success": j["success_geom"], "reason": j["reason"], "base_dist_px": j.get("base_dist_px")}
            r["success"] = bool(j["success_geom"]) and r["released"] and not r["human_contact"] and not r["aborted"]
    return rows


def cells_of(rows):
    out = {}
    for r in rows:
        c = out.setdefault(r["cell"], {"s": [], "place": [], "n_aborted": 0})
        c["s"].append(1.0 if r["success"] else 0.0); c["n_aborted"] += int(r["aborted"])
        d = None if r["aborted"] else r["judge_auto"].get("base_dist_px")
        if d is not None: c["place"].append(float(d))   # G6와 같은 정의: 중단되지 않고 캔 윗면이 검출된 모든 trial
    return out


MIN_PLACE = 5   # amendment 2 (§10): E2 needs at least this many placements per arm, else indeterminate


def verdict(e1, e2):
    """amendment 2 (§10): deployment verdict from the two endpoint decisions."""
    if "materially_degraded" in (e1, e2): return "NO-GO"
    if e1 == "tolerance_compatible" and e2 == "tolerance_compatible": return "GO"
    return "INSUFFICIENT_EVIDENCE"


def compare(a, b, key, conf, n_boot):
    """Degradation of b relative to a (a is the reference): E1 = rate(a) - rate(b), E2 = place(b) - place(a).
    Amendment 2 (§10), fixed before any stress v2 / FP16 outcome was unsealed: the E1 decision uses the Newcombe
    hybrid-score interval at the same confidence (it stays wide at 0 or n failures, where the percentile bootstrap
    collapses to a point). The bootstrap E1 interval is kept as a secondary field."""
    from scipy.stats import norm
    z = float(norm.ppf(1 - (1 - conf) / 2))
    ka, na, kb, nb = int(sum(a["s"])), len(a["s"]), int(sum(b["s"])), len(b["s"])
    nl, nh = newcombe(ka, na, kb, nb, z)
    e1b = boot_ci(a["s"], b["s"], np.mean, n_boot, key + "/E1", conf)
    e2 = boot_ci(b["place"], a["place"], np.mean, n_boot, key + "/E2", conf)
    ceiling = ka / na >= 0.95 and kb / nb >= 0.95
    d1 = "indeterminate (ceiling)" if ceiling else aep_decision(nl * 100, nh * 100, TOL["E1"])
    enough = len(a["place"]) >= MIN_PLACE and len(b["place"]) >= MIN_PLACE
    d2 = aep_decision(e2[1], e2[2], TOL["E2"]) if enough else f"indeterminate (< {MIN_PLACE} placements)"
    return {"ref_k_n": [ka, na], "test_k_n": [kb, nb],
            "E1": {"degradation_pp": (ka / na - kb / nb) * 100, "ci_pp": [nl * 100, nh * 100], "method": "Newcombe hybrid score",
                   "decision": d1, "bootstrap_ci_pp_secondary": [e1b[1] * 100, e1b[2] * 100]},
            "E2": {"degradation_px": e2[0], "ci_px": [e2[1], e2[2]], "n_place": [len(a["place"]), len(b["place"])], "decision": d2},
            "verdict": verdict(d1, d2), "ceiling_rule_applied": bool(ceiling), "conf": conf}


def analyse(stress, nominal, n_boot=10000):
    rep = {"n_trials": {c: len(stress[c]) for c in CONDS}, "n_trials_S0": len(stress.get("S0", []))}
    nom = cells_of(nominal); s0 = cells_of(stress.get("S0", []))
    rep["S0"] = {c: {"k": int(sum(v["s"])), "n": len(v["s"]), "place_mean": float(np.mean(v["place"])) if v["place"] else None}
                 for c, v in sorted(s0.items())}
    for cond in CONDS:
        cs = cells_of(stress[cond]); R = {}
        R["cells"] = {c: {"k": int(sum(v["s"])), "n": len(v["s"]), "wilson95": wilson(int(sum(v["s"])), len(v["s"])),
                          "place_mean": float(np.mean(v["place"])) if v["place"] else None, "aborted": v["n_aborted"],
                          "nominal_k_n": [int(sum(nom[c]["s"])), len(nom[c]["s"])] if c in nom else None,
                          "S0_k_n": [int(sum(s0[c]["s"])), len(s0[c]["s"])] if c in s0 else None,
                          "vs_S0_newcombe95_pp": [x * 100 for x in newcombe(int(sum(s0[c]["s"])), len(s0[c]["s"]), int(sum(v["s"])), len(v["s"]))]
                                                 if c in s0 else None}
                      for c, v in sorted(cs.items())}
        if BEST in cs and WORST in cs:
            R["primary_worst_vs_best"] = compare(cs[BEST], cs[WORST], f"STRESS-v1/{cond}/primary", CONF_PRIMARY, n_boot)
        R["secondary_vs_fp32"] = {c: compare(cs[FP32], cs[c], f"STRESS-v1/{cond}/{c}-vs-FP32", CONF_SECONDARY, n_boot)
                                  for c in (BEST, WORST, PRACT) if c in cs and FP32 in cs}
        if BEST in cs and PRACT in cs:
            R["secondary_calib1024_vs_16"] = compare(cs[BEST], cs[PRACT], f"STRESS-v1/{cond}/VC020-vs-VC002", CONF_PRIMARY, n_boot)
        # D4 shadow verdicts and end-of-trial judge (descriptive)
        rows = stress[cond]
        R["d4_shadow"] = {"trials": sum(1 for r in rows if r.get("d4")),
                          "trials_with_non_continue": sum(1 for r in rows if r.get("d4") and any(k not in ("CONTINUE", "UNKNOWN") for k in r["d4"]["decisions"])),
                          "failures": [r["trial"] for r in rows if not r["success"]],
                          "failures_flagged": [r["trial"] for r in rows if not r["success"] and r.get("d4") and
                                               any(k not in ("CONTINUE", "UNKNOWN") for k in r["d4"]["decisions"])]}
        cm = {"YES_success": 0, "YES_failure": 0, "NO_success": 0, "NO_failure": 0, "other": 0}
        for r in rows:
            a = ((r.get("d4_judge") or {}).get("answer") or "").strip().upper().rstrip(".")
            if a in ("YES", "NO"): cm[f"{a}_{'success' if r['success'] else 'failure'}"] += 1
            else: cm["other"] += 1
        n = cm["YES_success"] + cm["YES_failure"] + cm["NO_success"] + cm["NO_failure"]
        R["d4_judge"] = {"confusion": cm, "agreement": (cm["YES_success"] + cm["NO_failure"]) / n if n else None}
        rep[cond] = R
    prim = [rep[c]["primary_worst_vs_best"][e]["decision"] for c in CONDS if "primary_worst_vs_best" in rep[c] for e in ("E1", "E2")]
    rep["falsified"] = any(d == "materially_degraded" for d in prim)
    return rep


def synthetic():
    rng = np.random.default_rng(0); st = {}
    p = {"VC-000": 0.85, "VC-002": 0.85, "VC-005": 0.6, "VC-020": 0.8}
    for cond in CONDS:
        rows = []
        for c, pc in p.items():
            for i in range(12):
                ok = bool(rng.random() < pc)
                rows.append({"cell": c, "trial": len(rows) + 1, "success": ok, "aborted": False, "invalid": False,
                             "judge_auto": {"success": ok, "base_dist_px": float(rng.normal(9 if c != "VC-005" else 14, 3)) if ok else None},
                             "d4": {"decisions": {"CONTINUE": 100}}, "d4_judge": {"answer": "YES" if rng.random() < 0.8 else "NO"}})
        st[cond] = rows
    st["S0"] = [{"cell": c, "trial": i, "success": True, "aborted": False, "judge_auto": {"success": True, "base_dist_px": 7.0}} for i, c in enumerate(list(p) * 6)]
    nominal = [{"cell": c, "success": True, "aborted": False, "judge_auto": {"success": True, "base_dist_px": 7.0}} for c in p for _ in range(25)]
    return st, nominal


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--sealed-dir"); ap.add_argument("--out")
    ap.add_argument("--synthetic", action="store_true"); ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--version", default="v1", choices=["v1", "v2"])   # v2: rubber-band gripper (protocol §8), same analysis
    ap.add_argument("--rejudge", nargs="*", default=[])   # v2: stress_rejudge.py outputs (protocol §9); required for v2
    a = ap.parse_args()
    if a.synthetic:
        st, nom = synthetic(); rep = analyse(st, nom, a.n_boot); rep["SYNTHETIC"] = True
    else:
        post = "artifacts/freeze/" + ("stress_v2_post.json" if a.version == "v2" else "stress_lock_post.json")
        pre = "stress_v2_" if a.version == "v2" else "stress_"
        if a.version == "v2":
            if not a.rejudge: sys.exit("v2는 --rejudge(오프라인 재판정 결과)가 필요하다 (프로토콜 §9)")
            for f in a.rejudge: REJ.update(json.load(open(f)))
        if not os.path.exists(post):
            sys.exit("stress_lock_post.json이 없다. 스트레스 trial을 모두 마치고 봉인 로그 해시를 고정한 뒤 실행한다")
        st = {c: load(os.path.join(a.sealed_dir, f"{pre}{c}_sealed.jsonl")) for c in CONDS + ("S0",)}
        rep = analyse(st, load("artifacts/trials/g6_unsealed/g6_main_sealed.jsonl"), a.n_boot)
    import math
    def _clean(o):   # strict JSON: NaN/inf -> null (2026-10-13 external review)
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)): return None
        if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
        return o
    json.dump(_clean(rep), open(a.out, "w"), indent=1, allow_nan=False, default=lambda o: list(o) if isinstance(o, set) else str(o))
    print("written", a.out)
