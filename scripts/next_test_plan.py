"""From evidence to the next test (external review 7): for each candidate, what is confirmed, what is open, the evidence
behind both (rows, sealed logs, trial ids, clips), and an exportable plan for the next test (comparison, conditions,
measurements, decision rule, trials per arm with simulated power). Everything comes from the code-written verdict table
(artifacts/reports/d3_v3_verdicts.json) and the committed logs; no model is called.
Power is simulated (fixed seed) with the same Newcombe interval and 10 pp tolerance as the pre-registered E1 rule:
power = P(upper bound of the degradation < 10 pp), i.e. for the success criterion only; a final GO also needs the
placement criterion (E2) and the preflight, so it is not the probability of approval. The pre-registered ceiling rule (both arms >= 95% -> undecided) is
shown separately: with it, two arms at about 96% stay undecided most of the time at any sample size.
Usage: python scripts/next_test_plan.py [--out artifacts/reports]     (quantgate.py plan [candidate] prints one)"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g6_analysis import newcombe
from scipy.stats import norm
R = "artifacts/reports"; Z = float(norm.ppf(1 - 0.025 / 2))

def power(n, p_ref, p_c, ceiling, sims=3000, seed=0, tol=10.0):
    rng = np.random.default_rng(seed); ok = 0
    for _ in range(sims):
        kr, kc = rng.binomial(n, p_ref), rng.binomial(n, p_c)
        if ceiling and kr / n >= 0.95 and kc / n >= 0.95: continue
        ok += newcombe(kr, n, kc, n, Z)[1] * 100 < tol
    return round(ok / sims, 2)

def n_for(p_ref, p_c, ceiling, target=0.8, grid=(50, 75, 100, 120, 150, 200, 300, 400, 600), tol=10.0):
    for n in grid:
        if power(n, p_ref, p_c, ceiling, tol=tol) >= target: return n
    return None

def plans(T):
    rows = T["rows"]; by = lambda c, ctx: next((r for r in rows if r["candidate"] == c and ctx in r["context"]), None)
    P = {}
    fp16 = by("VC-025", "FP16 run")
    P["VC-025"] = {
        "candidate": "VC-025 (FP16, old policy)", "status": "recommended to validate first; approval on hold",
        "confirmed": ["cheapest engine on the device: 11.6 ms and 82 mJ per inference (power_bench/SUMMARY.md)",
                      f"real arm {fp16['success'][0]}/{fp16['success'][1]} against FP32 {fp16['reference'][0]}/{fp16['reference'][1]} (fp16_analysis.json)"],
        "open": ["success against FP32 within 10 pp: INSUFFICIENT_EVIDENCE, and both arms are at or above 95%, so the pre-registered ceiling rule keeps it undecided"],
        "evidence": [fp16["evidence_path"], "artifacts/freeze/fp16_post.json", "artifacts/trials/fp16_unsealed/stress_fp16_F0_sealed.jsonl"],
        "next_test": {"compare": "VC-025 (FP16) vs VC-000 (FP32), same old policy", "conditions": "training start mark, rubber-band gripper, cola can",
                      "measure": "success (consensus re-judge), placement error, gripper chatter", "schedule": "sealed, interleaved, new tokens",
                      "rule": "pre-register a revised E1 (success) rule without the ceiling clause: the success criterion is met if the 97.5% Newcombe upper bound of the degradation is below 10 pp; a final GO also needs placement (E2, 5 px) and the preflight",
                      "trials_per_arm": {"under the revised rule, if equal at 96%": n_for(0.96, 0.96, False), "with the current ceiling rule, power at 200/arm": power(200, 0.96, 0.96, True)}}}
    t0 = by("FT-FP16", "pooled")
    # amendment 7 (prereg §17-18): generalization blocks; absent before 2026-10-18
    g = json.load(open("artifacts/reports/ft4_analysis.json")) if os.path.exists("artifacts/reports/ft4_analysis.json") else {}
    # amendment 8 (prereg §19-20): re-tests without the red markers; absent before 2026-10-21
    r5 = json.load(open("artifacts/reports/ft5_analysis.json")) if os.path.exists("artifacts/reports/ft5_analysis.json") else {}
    GEN_CTX = {"TYP": "yellow can at +3 cm (held-out object, primary)", "T6P": "start +6 cm (beyond the demonstrations)", "T6M": "start -6 cm (beyond the demonstrations)"}
    P["FT-FP16"] = {
        "candidate": "FT-FP16 (position fine-tune)", "status": "next candidate where the start varies between -6 and +3 cm with the cola can; superseded for the yellow can and +6 cm by FT2-FP16 (amendment 9); not a replacement at the trained spot",
        "confirmed": [f"{r['context']}: {r['success'][0]}/{r['success'][1]} vs old {r['reference'][0]}/{r['reference'][1]}, {r['verdict']}" for r in rows
                      if r["candidate"] == "FT-FP16" and r["verdict"] == "IMPROVEMENT_DETECTED"]
                     + [f"{GEN_CTX[k]}: {g[k]['test']['ft'][0]}/{g[k]['test']['ft'][1]} vs old {g[k]['test']['old'][0]}/{g[k]['test']['old'][1]}, IMPROVEMENT_DETECTED" for k in ("T6M",)
                        if k in g and g[k]["test"]["improvement_detected"]],
        "open": [f"training mark, T0 + T0R pooled: {t0['success'][0]}/{t0['success'][1]} vs old {t0['reference'][0]}/{t0['reference'][1]}, {t0['verdict']}"]
                + [f"{GEN_CTX[k]}: {g[k]['test']['ft'][0]}/{g[k]['test']['ft'][1]} vs old {g[k]['test']['old'][0]}/{g[k]['test']['old'][1]}, NOT_DETECTED" for k in ("TYP", "T6P")
                   if k in g and not g[k]["test"]["improvement_detected"]]
                + [f"{c} re-test without the red markers (amendment 8, H1 'unclear'): {r5[k]['test']['ft'][0]}/{r5[k]['test']['ft'][1]} vs old {r5[k]['test']['old'][0]}/{r5[k]['test']['old'][1]}, NOT_DETECTED"
                   for k, c in (("T6PR", "start +6 cm"), ("TYPR", "yellow can at +3 cm")) if k in r5 and not r5[k]["test"]["improvement_detected"]],
        "evidence": [t0["evidence_path"], "artifacts/freeze/ft_post.json", "artifacts/freeze/ft3_post.json", "artifacts/finetune/T0R_modes.json",
                     "artifacts/reports/ft4_analysis.json", "artifacts/freeze/ft4_post.json", "artifacts/finetune/GEN_modes.json",
                     "artifacts/reports/ft5_analysis.json", "artifacts/freeze/ft5_post.json", "artifacts/finetune/GEN2_modes.json",
                     "T0 failures: trials 18 and 22 (placement disturbance, docs/sessions/ft_operator_notes.md); clip: dashboard/clips/t1_old_vs_ft.mp4"],
        "completed": ["the plan for the gaps (a new fine-tune with demonstrations at +6 cm and with the yellow can, re-tested under a new pre-registration): completed as FT2-FP16, amendment 9"] if os.path.exists("artifacts/reports/ft6_analysis.json") else [],
        "next_test": {"compare": "FT-FP16 vs VC-025 (old FP16 policy) at the training mark",
                      "conditions": "training start mark (nominal), cola can",
                      "measure": "success, failure mode (placement disturbance), gripper chatter", "schedule": "sealed, interleaved, new tokens (operator blinding stays partial: the motions differ)",
                      "rule": "success non-inferiority at 10 pp (97.5% Newcombe), pre-registered without the ceiling clause (if both arms land at or above 95%, the current ceiling clause would hold it undecided); a final GO also needs placement (E2, 5 px) and the preflight",
                      "trials_per_arm": {"under the revised rule, if truly equal (95.8%)": n_for(23 / 24, 23 / 24, False),
                                         "under the revised rule, if the observed 4 pp gap is real": n_for(23 / 24, 22 / 24, False),
                                         "with the current ceiling rule, power at 120/arm if truly equal": power(120, 23 / 24, 23 / 24, True)}}}
    # amendment 9 (prereg §21-22): fine-tune v2 for the two gaps; absent before 2026-10-22
    r6 = json.load(open("artifacts/reports/ft6_analysis.json")) if os.path.exists("artifacts/reports/ft6_analysis.json") else {}
    if r6:
        C6 = {"TYP2": "yellow can at +3 cm (held out, primary)", "T6P2": "start +6 cm (held out, secondary)", "T0G": "training mark (guard)"}
        tt = lambda k: f"{C6[k]}: {r6[k]['test']['ft2'][0]}/{r6[k]['test']['ft2'][1]} vs FT {r6[k]['test']['ft'][0]}/{r6[k]['test']['ft'][1]}"
        P["FT2-FP16"] = {
            "candidate": "FT2-FP16 (fine-tune v2: yellow can and far starts)", "status": "next candidate for the yellow can and starts up to +6 cm; not approved, not yet a replacement at the trained spot",
            "confirmed": [tt(k) + ", IMPROVEMENT_DETECTED" for k in ("TYP2", "T6P2") if r6[k]["test"].get("improvement_detected")]
                         + ([tt("T0G") + ", no drop flagged (12-trial guard)"] if not r6["T0G"]["test"].get("drop_flagged") else []),
            "open": [tt(k) + ", NOT_DETECTED" for k in ("TYP2", "T6P2") if not r6[k]["test"].get("improvement_detected")]
                    + ([tt("T0G") + ", DROP FLAGGED"] if r6["T0G"]["test"].get("drop_flagged") else [])
                    + ["non-inferiority at the training mark against the old policy (the guard detects only a large drop)",
                       "FT did better in this session than before (7/12 and 2/12 against 0/12): the earlier gap was partly the scene (a knocked wrist camera)"],
            "evidence": ["artifacts/reports/ft6_analysis.json", "artifacts/freeze/ft6_post.json", "artifacts/finetune/GEN3_modes.json",
                         "artifacts/finetune/rejudge/TYP2_consensus.json", "docs/finetune_position_preregistration.md#22"],
            "next_test": {"compare": "FT2-FP16 vs VC-025 (old FP16 policy) at the training mark, and FT2 at more objects and positions",
                          "conditions": "training mark; the yellow can and the cola can between -6 and +7 cm; a session-start wrist-camera check",
                          "measure": "success, failure mode, gripper chatter", "schedule": "sealed, interleaved, new tokens",
                          "rule": "success non-inferiority at 10 pp (97.5% Newcombe) without the ceiling clause; a final GO also needs placement (E2, 5 px) and the preflight",
                          "trials_per_arm": {"under the revised rule, if truly equal (about 96%)": n_for(0.96, 0.96, False)}}}
    P["INT8"] = {
        "candidate": "INT8 builds (24 calibration variants)", "status": "not first: slower and costlier per inference than FP16 on this device",
        "confirmed": ["16.8-17.1 ms and 101 mJ per inference for the 3 benched builds", "audit-picked cells 73/75 vs random 73/75: the offline score did not predict the arm"],
        "open": ["success against FP32: INSUFFICIENT_EVIDENCE for every cell, under the ceiling rule",
                 "chatter re-test (Q8B, pre-registered): VC-002 median 0.497 vs FP16 0.391, MWU p = 0.12, the post hoc 2x pattern NOT confirmed; chatter rose for both engines in that session (unexplained)",
                 "Q8B success, descriptive: VC-002 23/24 vs FP16 20/24 (FP16 below its earlier level at the mark; no approval follows)"],
        "evidence": ["artifacts/reports/g6_analysis.json", "artifacts/freeze/lock3.json", "artifacts/reports/ft_chatter.json", "artifacts/reports/int8c2_analysis.json", "artifacts/freeze/int8c2_post.json"],
        "next_test": {"compare": "only if memory or power forces INT8: VC-002 vs FP16 (VC-025) against FP32 under the revised success rule; first find why chatter rose for every engine between sessions (FP16-only check at the mark)", "conditions": "training start mark, the pre-registered scene (no extra markers)",
                      "measure": "success, placement, gripper chatter as a session-level health check", "schedule": "sealed, interleaved",
                      "rule": "success non-inferiority at 10 pp (97.5% Newcombe) without the ceiling clause; chatter compared with the earlier nominal blocks before any engine comparison", "trials_per_arm": {"chatter re-test done (Q8B, block size)": 24}}}
    P["PC-B"] = {
        "candidate": "PC-B (black-frame calibration)", "status": "rejected", "confirmed": ["flagged offline by the input check, action error and audit score"],
        "open": ["the offline warning was not confirmed on the arm in 12 trials (unresolved)"], "evidence": ["artifacts/reports/simple_checks_vs_audit.json", "artifacts/reports/positive_control_analysis.json"],
        "next_test": {"compare": "none: block it at the calibration-input check", "conditions": "-", "measure": "-", "schedule": "-", "rule": "preflight BLOCK (FLAGGED)", "trials_per_arm": {}}}
    return P

def md(P):
    L = ["# From evidence to the next test (written by code)", ""]
    for k, p in P.items():
        L += [f"## {p['candidate']}", f"**Status**: {p['status']}", "", "Confirmed:"] + [f"- {x}" for x in p["confirmed"]] + ["", "Open:"] + [f"- {x}" for x in p["open"]]
        if p.get("completed"): L += ["", "Completed since the plan was made:"] + [f"- {x}" for x in p["completed"]]
        L += ["", "Evidence:"] + [f"- `{x}`" if "/" in x and " " not in x else f"- {x}" for x in p["evidence"]]
        nt = p["next_test"]; L += ["", "Next test:"] + [f"- {a}: {nt[a]}" for a in ("compare", "conditions", "measure", "schedule", "rule")]
        L += [(f"- {a}: {v}" if ("power at" in a or "block size" in a) else f"- trials per arm for 80% power on the success criterion (not the chance of a final GO), {a}: {v}") for a, v in nt["trials_per_arm"].items()] + [""]
    return "\n".join(L)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=R); a = ap.parse_args()
    T = json.load(open(f"{R}/d3_v3_verdicts.json")); P = plans(T)
    json.dump(P, open(f"{a.out}/next_test_plans.json", "w"), indent=1); open(f"{a.out}/next_test_plans.md", "w").write(md(P))
    print(md(P))
