"""Judge your own results with QuantGate's rules: one row per candidate build compared with a reference build.
It reuses the functions this study used (scripts/g6_analysis.newcombe, scripts/next_test_plan.n_for), so a row gets the
same reading the review would give it. Nothing here is tuned to the SO-101 data.

Input CSV columns (one row per comparison; the last four are optional):
  candidate, reference, cand_successes, cand_trials, ref_successes, ref_trials[, gpu_ms, energy_mj, placement_ok, preflight_ok]
  - mode is "non-inferiority" (a build vs its reference, e.g. FP16 vs FP32; also when empty) or "improvement"
    (e.g. a fine-tune vs the policy it replaces). Any other value, a yes/no typo or a bad number stops with exit 2.
  - placement_ok / preflight_ok: yes, no or empty (not checked). A GO needs both to be yes.
  - assumed_rate: the true success rate to plan the next test with (default: the pooled observed rate).

Rules (the pre-registered ones, see docs/fp16_real_arm_preregistration.md and next_test_plan.py):
  - non-inferiority: degradation = reference - candidate. The success criterion is met when the upper bound of its
    two-sided 97.5% Newcombe interval is below the tolerance (default 10 pp); "degraded" when the lower bound is above it.
    With --rule current (the study's rule) two arms both at or above 95% stay undecided at any sample size (ceiling
    clause); --rule revised drops that clause.
  - improvement: detected when the lower bound of the 95% Newcombe interval of candidate - reference is above 0.
  - deployment decision: GO only if the success criterion is met AND placement_ok AND preflight_ok; BLOCK if degraded or
    preflight_ok is no; otherwise HOLD. An improvement is never a GO by itself.
  - next test: trials per arm for 80% power on the success criterion at the same tolerance under the revised rule,
    assuming both builds truly succeed at the pooled observed rate (a planning estimate, not a guarantee).
Usage: python scripts/quantgate_judge.py <results.csv> [--rule current|revised] [--tol 10] [--json out.json]"""
import argparse, csv, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g6_analysis import newcombe
import next_test_plan as ntp

Z975 = ntp.Z                     # two-sided 97.5% (the non-inferiority interval of the plans)
Z95 = 1.959963984540054          # two-sided 95% (the improvement rule)
MODES = ("non-inferiority", "improvement")
GRID = (50, 75, 100, 120, 150, 200, 300, 400, 600, 800, 1000, 1500, 2000)   # trials per arm searched for the next test


class InputError(ValueError): pass


yes = lambda v: {"yes": True, "y": True, "true": True, "1": True, "no": False, "n": False, "false": False, "0": False}.get(str(v or "").strip().lower())

def check_row(r, where="row"):
    """Refuse anything the rules do not define: a typo must stop the run, never change what is tested."""
    for k in ("candidate", "reference", "cand_successes", "cand_trials", "ref_successes", "ref_trials"):
        if (r.get(k) or "").strip() == "": raise InputError(f"{where}: missing {k}")
    try: kc, nc, kr, nr = (int(r[k]) for k in ("cand_successes", "cand_trials", "ref_successes", "ref_trials"))
    except ValueError: raise InputError(f"{where}: success and trial counts must be whole numbers")
    if not (0 <= kc <= nc and 0 <= kr <= nr and nc > 0 and nr > 0): raise InputError(f"{where}: need 0 <= successes <= trials and trials > 0")
    mode = (r.get("mode") or "").strip().lower() or "non-inferiority"
    if mode not in MODES: raise InputError(f"{where}: unknown mode {r.get('mode')!r}; use non-inferiority (or leave it empty) or improvement")
    for k in ("placement_ok", "preflight_ok"):
        if (r.get(k) or "").strip() and yes(r[k]) is None: raise InputError(f"{where}: {k} must be yes, no or empty, not {r[k]!r}")
    for k in ("gpu_ms", "energy_mj", "assumed_rate"):
        v = (r.get(k) or "").strip()
        if not v: continue
        try: x = float(v)
        except ValueError: raise InputError(f"{where}: {k} must be a number, not {v!r}")
        if not math.isfinite(x) or x < 0 or (k == "assumed_rate" and not 0 < x < 1): raise InputError(f"{where}: {k} out of range: {v}")
    return kc, nc, kr, nr, mode


def judge_row(r, rule="current", tol=10.0, where="row"):
    if not (math.isfinite(tol) and 0 < tol < 100): raise InputError(f"tolerance must be between 0 and 100 pp, not {tol}")
    kc, nc, kr, nr, mode = check_row(r, where)
    pc, pr = kc / nc, kr / nr; place, pre = yes(r.get("placement_ok")), yes(r.get("preflight_ok"))
    out = {"candidate": r["candidate"], "reference": r["reference"], "mode": mode, "candidate_k_n": [kc, nc], "reference_k_n": [kr, nr]}
    missing = []
    if mode == "improvement":
        lo, hi = newcombe(kc, nc, kr, nr, Z95); out["difference_pp"] = round((pc - pr) * 100, 1); out["interval95_pp"] = [round(lo * 100, 1), round(hi * 100, 1)]
        out["finding"] = "IMPROVEMENT_DETECTED" if lo > 0 else "NOT_DETECTED"
        out["decision"] = "BLOCK" if pre is False else "HOLD"
        out["why"] = ("an improvement is not an approval: compare it with the reference for non-inferiority where it will be deployed"
                      if lo > 0 else "no improvement shown at this sample size")
    else:
        lo, hi = newcombe(kr, nr, kc, nc, Z975)   # degradation = reference - candidate
        out["degradation_pp"] = round((pr - pc) * 100, 1); out["interval97_5_pp"] = [round(lo * 100, 1), round(hi * 100, 1)]
        ceiling = rule == "current" and pc >= 0.95 and pr >= 0.95
        if ceiling: crit = "undecided (ceiling clause: both arms at or above 95%)"
        elif hi * 100 < tol: crit = "met"
        elif lo * 100 > tol: crit = "degraded"
        else: crit = "undecided"
        out["success_criterion"] = crit
        if crit == "degraded": out["finding"], out["decision"] = "NO-GO", "BLOCK"
        elif crit == "met":
            if place is not True: missing.append("placement check")
            if pre is not True: missing.append("deployment preflight")
            out["finding"] = "GO" if not missing and pre is not False else "INSUFFICIENT_EVIDENCE"
            out["decision"] = "BLOCK" if pre is False else ("GO" if not missing else "HOLD")
        else: out["finding"], out["decision"] = "INSUFFICIENT_EVIDENCE", "BLOCK" if pre is False else "HOLD"
        out["why"] = {"met": "the success criterion is met" + ("; still missing: " + ", ".join(missing) if missing else ""),
                      "degraded": f"the candidate is worse than the reference by more than {tol:g} pp"}.get(crit, f"success is {crit} at a {tol:g} pp tolerance")
        if out["decision"] == "HOLD" and crit != "met":
            ar = r.get("assumed_rate"); p = float(ar) if ar not in (None, "") else max(min((kc + kr) / (nc + nr), 0.999), 0.5); n = ntp.n_for(p, p, False, grid=GRID, tol=tol)
            out["next_test"] = {"compare": f"{r['candidate']} vs {r['reference']}", "rule": f"pre-register the revised rule (no ceiling clause), tolerance {tol:g} pp",
                                "trials_per_arm": n if n else f"more than {GRID[-1]}",
                                "assumption": f"both truly succeed at {p:.0%} ({'assumed' if ar not in (None, '') else 'pooled observed'}); 80% power on the success criterion at {tol:g} pp, not the chance of a final GO"}
    if pre is False: out["why"] += "; the preflight failed"
    for k in ("gpu_ms", "energy_mj"):
        if r.get(k) not in (None, ""): out[k] = float(r[k])
    return out

def judge(rows, rule="current", tol=10.0):
    if not rows: raise InputError("no rows")
    res = [judge_row(r, rule, tol, f"row {i} (line {i + 1})") for i, r in enumerate(rows, 1)]
    ok = [x for x in res if x["decision"] != "BLOCK" and "gpu_ms" in x]
    if ok:   # validation priority: the cheapest build that is not blocked (cost first, energy second)
        best = min(ok, key=lambda x: (x["gpu_ms"], x.get("energy_mj", math.inf))); best["priority"] = "validate first (cheapest build that is not blocked)"
    return res

def md(res, rule, tol):
    L = [f"# QuantGate judge ({'current rule, with the ceiling clause' if rule == 'current' else 'revised rule'}, tolerance {tol:g} pp)", ""]
    for x in res:
        k, n = x["candidate_k_n"]; kr, nr = x["reference_k_n"]
        L += [f"## {x['candidate']} vs {x['reference']} ({x['mode']})", f"- **Deployment decision: {x['decision']}** · evidence finding: {x['finding']}",
              f"- observed: {k}/{n} vs {kr}/{nr}" + (f" · degradation {x['degradation_pp']} pp, 97.5% interval {x['interval97_5_pp']}" if "degradation_pp" in x else
                                                      f" · difference {x['difference_pp']} pp, 95% interval {x['interval95_pp']}"), f"- why: {x['why']}"]
        if x.get("priority"): L += [f"- priority: {x['priority']}"]
        if x.get("next_test"): nt = x["next_test"]; L += [f"- next test: {nt['compare']}; {nt['rule']}; about {nt['trials_per_arm']} trials per arm ({nt['assumption']})"]
        L += [""]
    return "\n".join(L)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--rule", choices=["current", "revised"], default="current")
    ap.add_argument("--tol", type=float, default=10.0); ap.add_argument("--json"); a = ap.parse_args()
    try:
        rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig"))); res = judge(rows, a.rule, a.tol)
    except FileNotFoundError: print(f"error: file not found: {a.csv}", file=sys.stderr); sys.exit(2)
    except InputError as e: print(f"error: {a.csv}: {e}", file=sys.stderr); sys.exit(2)
    if a.json: json.dump(res, open(a.json, "w"), indent=1)
    print(md(res, a.rule, a.tol))
