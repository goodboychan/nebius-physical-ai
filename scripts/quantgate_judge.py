"""Judge your own results with QuantGate's rules: one row per candidate build compared with a reference build.
It reuses the functions this study used (scripts/g6_analysis.newcombe, scripts/next_test_plan.n_for), so a row gets the
same reading the review would give it. Nothing here is tuned to the SO-101 data.

Input CSV columns (one row per comparison; the last four are optional):
  candidate, reference, cand_successes, cand_trials, ref_successes, ref_trials[, gpu_ms, energy_mj, placement_ok, preflight_ok]
  - mode is "non-inferiority" (a build vs its reference, e.g. FP16 vs FP32; also when empty) or "improvement"
    (e.g. a fine-tune vs the policy it replaces). Any other value, a yes/no typo or a bad number stops with exit 2,
    and so does an unknown or duplicate column name (a misspelled `mode` column must not fall back to non-inferiority).
    Values are stripped of spaces first; a value of only spaces counts as empty.
  - placement_ok / preflight_ok: yes, no or empty (not checked). A GO needs both to be yes.
  - assumed_rate: the true success rate to plan the next test with (default: the pooled observed rate, kept within
    50%..99.9%; below 50% the plan uses 50%, the most conservative rate, and says so next to the observed rate).
  - engine_sha256: the build the row's trials ran on; with --preflight it must match the card's engine.
  - design: independent (default; separate trials per build) or paired (the same tasks for both builds). The intervals
    here assume independent arms, so a paired row is counted and previewed but never GO, and says not to use it for a
    deployment decision. tally --pair FIELD marks it.
  - collection: controlled (default; both builds under the same conditions on a pre-set interleaved or randomized
    schedule) or observational (anything else, e.g. logs gathered at different times or setups, or not verified).
    An observational row is counted and previewed, never GO. design is how the trials are analysed; collection is how
    they were gathered.
  --preflight pre.json fills preflight_ok for the card's candidate from `preflight --card c.json --checks-only --json`.

Rules (the pre-registered ones, see docs/fp16_real_arm_preregistration.md and next_test_plan.py):
  - non-inferiority: degradation = reference - candidate. The success criterion is met when the upper bound of its
    two-sided 97.5% Newcombe interval is below the tolerance (default 10 pp); "degraded" when the lower bound is above it.
    With --rule study (alias current: this study's pre-registered rule) two arms both at or above 95% stay undecided at
    any sample size (ceiling clause); --rule revised (the default, for a new project) drops that clause. Choose the rule
    before the trials and write it down; never choose it after seeing which one reads better.
  - improvement: detected when the lower bound of the 95% Newcombe interval of candidate - reference is above 0.
  - deployment decision: GO only if the success criterion is met AND placement_ok AND preflight_ok; BLOCK if degraded or
    preflight_ok is no; otherwise HOLD. An improvement is never a GO by itself.
  - next test: trials per arm for 80% power on the success criterion at the same tolerance under the revised rule,
    assuming both builds truly succeed at the pooled observed rate (a planning estimate, not a guarantee).
With --gate the exit code carries the decision for CI: 0 every row GO, 3 any HOLD (none blocked), 4 any BLOCK; bad input
exits 2 either way.
Usage: python scripts/quantgate_judge.py <results.csv> [--rule revised|study] [--tol 10] [--json out.json] [--md out.md] [--gate]"""
import argparse, csv, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g6_analysis import newcombe
import next_test_plan as ntp

Z975 = ntp.Z                     # two-sided 97.5% (the non-inferiority interval of the plans)
Z95 = 1.959963984540054          # two-sided 95% (the improvement rule)
MODES = ("non-inferiority", "improvement")
# "study" (alias "current"): this study's pre-registered rule, with the ceiling clause; use it only to reproduce this
# study. "revised": the rule for a new project (no ceiling clause). Pick it and write it down before the trials run.
RULES = {"revised": "revised", "study": "current", "current": "current"}
RULE_HELP = ("revised (default): for a new project; study: reproduces this study's pre-registered rule with the ceiling "
             "clause (alias: current). Choose before the trials, never after seeing which one gives the better reading.")


def _bad_rule(rule): raise InputError(f"unknown rule {rule!r}; use revised or study")
REQUIRED = ("candidate", "reference", "cand_successes", "cand_trials", "ref_successes", "ref_trials")
OPTIONAL = ("gpu_ms", "energy_mj", "placement_ok", "preflight_ok", "mode", "assumed_rate", "engine_sha256", "design", "collection",
            "pairs_improved", "pairs_regressed", "safety_regressions", "safety_unrecorded_regressions",
            "safety_events_cand", "safety_recorded_cand", "safety_events_ref", "safety_recorded_ref")
COUNTS = OPTIONAL[-8:]   # shown next to the decision, never used in it
# how the trials were collected, apart from how they are analysed (design): controlled = both builds under the same
# conditions on a pre-set (interleaved or randomized) schedule; observational = anything else, or not verified
COLLECTIONS = ("controlled", "observational")
DESIGNS = ("independent", "paired")   # paired: counted and previewed only; the intervals here assume independent arms
GRID = (50, 75, 100, 120, 150, 200, 300, 400, 600, 800, 1000, 1500, 2000)   # trials per arm searched for the next test


class InputError(ValueError): pass


yes = lambda v: {"yes": True, "y": True, "true": True, "1": True, "no": False, "n": False, "false": False, "0": False}.get(str(v or "").strip().lower())

def check_columns(cols):
    """A misspelled column (e.g. `mod`) would otherwise be ignored and silently change the test, so refuse it."""
    cols = [(c or "").strip() for c in cols]
    dup = sorted({c for c in cols if cols.count(c) > 1})
    if dup: raise InputError(f"header: duplicate column(s) {', '.join(dup)}")
    unknown = [c for c in cols if c not in REQUIRED + OPTIONAL]
    if unknown: raise InputError(f"header: unknown column(s) {', '.join(repr(c) for c in unknown)}; allowed: {', '.join(REQUIRED + OPTIONAL)}")
    missing = [c for c in REQUIRED if c not in cols]
    if missing: raise InputError(f"header: missing column(s) {', '.join(missing)}")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.reader(f); header = next(rd, None)
        if header is None: raise InputError("empty file")
        check_columns(header); header = [c.strip() for c in header]; rows, lines = [], []
        for line, vals in enumerate(rd, 2):
            if not any(v.strip() for v in vals): continue          # blank line
            if len(vals) != len(header): raise InputError(f"line {line}: {len(vals)} values for {len(header)} columns")
            rows.append(dict(zip(header, vals))); lines.append(line)
    return rows, lines


def check_row(r, where="row"):
    """Refuse anything the rules do not define: a typo must stop the run, never change what is tested.
    Returns the row with every value stripped, so later steps only see normalized values."""
    check_columns(list(r))
    r = {k: (v if v is not None else "").strip() if isinstance(v, str) or v is None else str(v).strip() for k, v in r.items()}
    for k in REQUIRED:
        if (r.get(k) or "").strip() == "": raise InputError(f"{where}: missing {k}")
    try: kc, nc, kr, nr = (int(r[k]) for k in ("cand_successes", "cand_trials", "ref_successes", "ref_trials"))
    except ValueError: raise InputError(f"{where}: success and trial counts must be whole numbers")
    if not (0 <= kc <= nc and 0 <= kr <= nr and nc > 0 and nr > 0): raise InputError(f"{where}: need 0 <= successes <= trials and trials > 0")
    mode = (r.get("mode") or "").strip().lower() or "non-inferiority"
    if mode not in MODES: raise InputError(f"{where}: unknown mode {r.get('mode')!r}; use non-inferiority (or leave it empty) or improvement")
    if r.get("collection", "").lower() not in ("",) + COLLECTIONS: raise InputError(f"{where}: unknown collection {r['collection']!r}; use controlled (or leave it empty) or observational")
    if r.get("design", "").lower() not in ("",) + DESIGNS: raise InputError(f"{where}: unknown design {r['design']!r}; use independent (or leave it empty) or paired")
    for k in ("placement_ok", "preflight_ok"):
        if (r.get(k) or "").strip() and yes(r[k]) is None: raise InputError(f"{where}: {k} must be yes, no or empty, not {r[k]!r}")
    h = r.get("engine_sha256", "")
    if h and not (len(h) == 64 and all(c in "0123456789abcdef" for c in h.lower())): raise InputError(f"{where}: engine_sha256 must be 64 hex characters")
    for k in COUNTS:
        v = r.get(k, "")
        if v and not v.isdigit(): raise InputError(f"{where}: {k} must be a whole number, not {v!r}")
    if r.get("pairs_improved") or r.get("pairs_regressed"):
        if r.get("design", "").lower() != "paired": raise InputError(f"{where}: pairs_improved / pairs_regressed need design=paired")
    for a_, b_ in (("safety_events_cand", "safety_recorded_cand"), ("safety_events_ref", "safety_recorded_ref")):
        if r.get(a_) and r.get(b_) and int(r[a_]) > int(r[b_]): raise InputError(f"{where}: {a_} is larger than {b_}")
    if r.get("safety_regressions") and r.get("pairs_regressed") and int(r["safety_regressions"]) > int(r["pairs_regressed"]):
        raise InputError(f"{where}: safety_regressions is larger than pairs_regressed")
    for k in ("gpu_ms", "energy_mj", "assumed_rate"):
        v = (r.get(k) or "").strip()
        if not v: continue
        try: x = float(v)
        except ValueError: raise InputError(f"{where}: {k} must be a number, not {v!r}")
        if not math.isfinite(x) or x < 0 or (k == "assumed_rate" and not 0 < x < 1): raise InputError(f"{where}: {k} out of range: {v}")
    return r, kc, nc, kr, nr, mode


def judge_row(r, rule="revised", tol=10.0, where="row"):
    rule = RULES.get(rule) or _bad_rule(rule)
    if not (math.isfinite(tol) and 0 < tol < 100): raise InputError(f"tolerance must be between 0 and 100 pp, not {tol}")
    r, kc, nc, kr, nr, mode = check_row(r, where)
    pc, pr = kc / nc, kr / nr; place, pre = yes(r.get("placement_ok")), yes(r.get("preflight_ok"))
    out = {"candidate": r["candidate"], "reference": r["reference"], "mode": mode, "rule": "study" if rule == "current" else rule, "tolerance_pp": tol, "candidate_k_n": [kc, nc], "reference_k_n": [kr, nr]}
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
            # the observed rate and the planning rate are reported apart (user test 4: a floor of 50% was labelled "observed")
            ar = r.get("assumed_rate"); po = (kc + kr) / (nc + nr)
            if ar not in (None, ""): p, basis = float(ar), f"{float(ar):.0%}, the assumed_rate column (the pooled observed rate is {po:.1%})"
            else:
                p = max(min(po, 0.999), 0.5)
                basis = (f"the pooled observed rate, {po:.1%}" if p == po else
                         f"{p:.0%}, the planner's floor: the pooled observed rate is {po:.1%}, and a rate near 50% needs the most trials, so it is the conservative assumption"
                         if p == 0.5 else f"{p:.1%}, the planner's cap; the pooled observed rate is {po:.1%}")
            n = ntp.n_for(p, p, False, grid=GRID, tol=tol)
            out["next_test"] = {"compare": f"{r['candidate']} vs {r['reference']}", "rule": f"pre-register the revised rule (no ceiling clause), tolerance {tol:g} pp",
                                "trials_per_arm": n if n else f"more than {GRID[-1]}", "observed_pooled_rate": round(po, 4), "planning_rate": round(p, 4),
                                "assumption": f"planned as if both builds truly succeed at {basis}; 80% power on the success criterion at {tol:g} pp, not the chance of a final GO"}
    if pre is False: out["why"] += "; the preflight failed"
    for k in ("gpu_ms", "energy_mj"):
        if r.get(k) not in (None, ""): out[k] = float(r[k])
    if r.get("engine_sha256"): out["engine_sha256"] = r["engine_sha256"].lower()
    for k in COUNTS:
        if r.get(k): out[k] = int(r[k])
    out["design"] = r.get("design", "").lower() or "independent"; out["collection"] = r.get("collection", "").lower() or "controlled"
    why = []   # supported for counting, not for deciding
    if out["design"] == "paired":
        why.append("the trials are paired (the same tasks for both builds), but this interval treats the arms as independent; "
                   "analyse the pairs (e.g. a paired bootstrap or McNemar)")
    if out["collection"] == "observational":
        why.append("the trials were not collected under one controlled schedule (or that is not verified): conditions, timing or "
                   "operators may differ between builds, so a difference may not be the build's")
    if why:
        out["preview_only"] = True
        # the finding a downstream check reads must not say GO for a preview (preflight --judge takes it as evidence)
        out["preview_finding"] = out["finding"]
        if out["finding"] in ("GO", "IMPROVEMENT_DETECTED"): out["finding"] = "INSUFFICIENT_EVIDENCE"
        if out["decision"] == "GO": out["decision"] = "HOLD"
        out.pop("next_test", None); out.pop("priority", None)
        out["why"] = "PREVIEW ONLY, not for a deployment decision: " + "; ".join(why) + ". Reading as if independent and controlled: " + out["why"]
    return out

def judge(rows, rule="revised", tol=10.0, lines=None):
    if not rows: raise InputError("no rows")
    res = [judge_row(r, rule, tol, f"row {i}" + (f" (line {lines[i - 1]})" if lines else "")) for i, r in enumerate(rows, 1)]
    ok = [x for x in res if x["decision"] != "BLOCK" and "gpu_ms" in x and not x.get("preview_only")]
    if ok:   # validation priority: the cheapest build that is not blocked (cost first, energy second)
        best = min(ok, key=lambda x: (x["gpu_ms"], x.get("energy_mj", math.inf))); best["priority"] = "validate first (cheapest build that is not blocked)"
    return res

def apply_preflight(rows, pre):
    """Fill preflight_ok for the card's candidate from `preflight --checks-only --json` output, so it is not typed by
    hand. Refuses a result that is not checks-only, a candidate missing from the CSV, a row naming another engine, and a
    hand-entered preflight_ok that disagrees with the checks."""
    if not isinstance(pre, dict) or not pre.get("checks_only"): raise InputError("--preflight needs the output of `preflight --card c.json --checks-only --json pre.json`")
    c = pre.get("candidate")
    if not c: raise InputError("--preflight: the card has no `candidate` field naming its CSV row")
    hit = [r for r in rows if (r.get("candidate") or "").strip() == c]
    if not hit: raise InputError(f"--preflight: no row for candidate {c!r} in the CSV")
    ok = "yes" if pre.get("outcome") == "OK" else "no"
    for r in hit:
        h = (r.get("engine_sha256") or "").strip().lower()
        if h and h != pre.get("engine_sha256"): raise InputError(f"--preflight: row {c!r} is for engine {h[:12]}, the card for {pre.get('engine_sha256', '')[:12]}: not the same build")
        manual = (r.get("preflight_ok") or "").strip()
        if manual and yes(manual) != (ok == "yes"): raise InputError(f"--preflight: row {c!r} says preflight_ok={manual} but the checks say {ok}")
        r["preflight_ok"] = ok
        if not h: r["engine_sha256"] = pre.get("engine_sha256", "")
    return rows


def shown_counts(x):
    """What the average hides, shown next to the decision and never used in it: per-pair changes and safety events.
    Missing information is said to be missing, not read as none."""
    L = []
    if x.get("design") == "paired":
        if "pairs_regressed" in x:
            L.append(f"pairs: {x.get('pairs_improved', 0)} improved, {x['pairs_regressed']} regressed" +
                     ((f" ({x['safety_regressions']} with a safety event" + (f", {x['safety_unrecorded_regressions']} with no safety record" if x.get("safety_unrecorded_regressions") else "") + ")")
                      if "safety_regressions" in x else "; safety of the regressions: not provided") +
                     " · regressed trial ids: tally --regressions")
        else: L.append("pairs: per-pair changes not provided (tally --pair counts them)")
    if "safety_events_cand" in x:
        L.append(f"safety events: {x['safety_events_cand']} in {x.get('safety_recorded_cand', '?')} recorded trials of {x['candidate']}, "
                 f"{x.get('safety_events_ref', '?')} in {x.get('safety_recorded_ref', '?')} of {x['reference']} (trials without a record are not counted as none)")
    else: L.append("safety events: not provided")
    return [l + " · shown, not used in the decision" for l in L]


def gate(res):
    d = {x["decision"] for x in res}
    return 4 if "BLOCK" in d else 3 if "HOLD" in d else 0


def md(res, rule, tol):
    rule = RULES.get(rule, rule)
    name = "study rule: the pre-registered rule of this study, with the ceiling clause" if rule == "current" else "revised rule, for a new project"
    L = [f"# QuantGate judge ({name}, tolerance {tol:g} pp)", "",
         "_Assumes each trial is independent and both builds ran under the same conditions on a pre-set schedule; rows marked otherwise are previews only._",
         "", "_The rule and tolerance are part of the plan: fix them before the trials, not after seeing the results._", ""]
    for x in res:
        k, n = x["candidate_k_n"]; kr, nr = x["reference_k_n"]
        tags = [t for t in (x.get("design") == "paired" and "paired design", x.get("collection") == "observational" and "observational data") if t]
        L += [f"## {x['candidate']} vs {x['reference']} ({x['mode']}{', ' + ' and '.join(tags) + ': PREVIEW ONLY' if x.get('preview_only') else ''})",
              f"- **Deployment decision: {x['decision']}** · evidence finding: {x['finding']}" + ((f" (the preview reading would be {x['preview_finding']}; not for deployment)" if x['preview_finding'] != x['finding'] else " (preview only, not for deployment)") if x.get("preview_only") else ""),
              f"- observed: {k}/{n} vs {kr}/{nr}" + (f" · degradation {x['degradation_pp']} pp, 97.5% interval {x['interval97_5_pp']}" if "degradation_pp" in x else
                                                      f" · difference {x['difference_pp']} pp, 95% interval {x['interval95_pp']}"), f"- why: {x['why']}"]
        L += [f"- {line}" for line in shown_counts(x)]
        if x.get("priority"): L += [f"- priority: {x['priority']}"]
        if x.get("next_test"): nt = x["next_test"]; L += [f"- next test: {nt['compare']}; {nt['rule']}; about {nt['trials_per_arm']} trials per arm ({nt['assumption']})"]
        L += [""]
    return "\n".join(L)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--rule", choices=["revised", "study", "current"], default="revised", help=RULE_HELP)
    ap.add_argument("--tol", type=float, default=10.0); ap.add_argument("--json"); ap.add_argument("--md", help="also write the report as Markdown (e.g. for a PR comment)")
    ap.add_argument("--gate", action="store_true", help="exit 0 if every row is GO, 3 if any is HOLD, 4 if any is BLOCK")
    ap.add_argument("--preflight", help="fill preflight_ok for the card's candidate from `preflight --checks-only --json` output"); a = ap.parse_args()
    try:
        rows, lines = read_csv(a.csv)
        if a.preflight:
            try: pre = json.load(open(a.preflight))
            except (FileNotFoundError, json.JSONDecodeError) as e: raise InputError(f"--preflight {a.preflight}: {e}")
            rows = apply_preflight(rows, pre)
        res = judge(rows, a.rule, a.tol, lines)
    except FileNotFoundError: print(f"error: file not found: {a.csv}", file=sys.stderr); sys.exit(2)
    except InputError as e: print(f"error: {a.csv}: {e}", file=sys.stderr); sys.exit(2)
    if a.json: json.dump(res, open(a.json, "w"), indent=1)
    text = md(res, a.rule, a.tol); print(text)
    if a.md: open(a.md, "w").write(text + "\n")
    if a.gate: sys.exit(gate(res))
