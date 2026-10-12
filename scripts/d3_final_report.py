"""`D3` final deployment report (after LOCK-3). Nemotron 3 Super @ Nebius Token Factory.

The evidence is collected only from committed artifacts and nothing is estimated:
  - G6 closed-loop results (g6_analysis.json, g6_supplement.json)
  - Orin engine cost (power_bench/SUMMARY.md numbers, re-parsed from the raw logs)
  - D4 retrospective AI-judge test (d4_retro_judge_g6.json, summary only)
  - lock hashes (lock2.json, lock3.json) and the D5 errata snapshot hash
Stress-test results are **not** included. They are still sealed.

The same integrity devices as d3_report_agent: the evidence hash goes in the header, and every number in the report is
checked against the evidence (verify_numbers). A report with unmatched numbers is kept but flagged, never silently
trusted. This layer is a product component (§6), not a scientific claim.
Usage: python scripts/d3_final_report.py [--out artifacts/reports] [--repeats 2]"""
import argparse, glob, json, os, re, sys, time
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d3_report_agent as d3
sys.path.insert(0, "src")
from edgeqgate.hashing import hash_obj


def tegra_median(path, key="VDD_IN"):
    v = [int(m.group(1)) for l in open(path) for m in [re.search(rf"{key} (\d+)mW", l)] if m]
    v.sort(); return v[len(v) // 2]


def evidence():
    A = json.load(open("artifacts/reports/g6_analysis.json")); S = json.load(open("artifacts/reports/g6_supplement.json"))
    R = json.load(open("artifacts/reports/d4_retro_judge_g6.json")); L2 = json.load(open("artifacts/freeze/lock2.json"))
    L3 = json.load(open("artifacts/freeze/lock3.json"))
    cells = {}
    for c, v in A["cells"].items():
        e = S["EX-1_EX-2"][c]
        cells[c] = {"arm": v["arms"][0], "successes": v["k"], "trials": v["n"], "success_rate": round(v["rate"], 3),
                    "wilson95": [round(x, 3) for x in v["wilson95"]], "placement_error_px_mean": round(v["place_mean"], 2),
                    "failure_types": e["failures"], "end_to_end_infer_ms_mean": round(e["infer_ms_mean"], 1), "late_chunks": e["late_chunks"]}
        if c in A["AEP_Q2"]:
            q = A["AEP_Q2"][c]; cells[c]["vs_fp32_E1_success"] = q["E1"]; cells[c]["vs_fp32_E2_placement"] = q["E2"]
    pb = "artifacts/reports/power_bench"; idle = tegra_median(f"{pb}/idle.tegra.log"); cost = {}
    for n in ("VC-000_fp32", "VC-025_fp16", "VC-002_int8", "VC-005_int8", "VC-020_int8"):
        t = open(f"{pb}/{n}.trtexec.log").read()
        qps = float(re.search(r"Throughput: ([\d.]+) qps", t).group(1))
        med = float(re.search(r"GPU Compute Time: .*?median = ([\d.]+) ms", t).group(1)); p = tegra_median(f"{pb}/{n}.tegra.log")
        cost[n] = {"gpu_compute_ms_median": round(med, 1), "throughput_qps": round(qps, 1), "module_power_mw_median": p,
                   "energy_per_inference_mj_above_idle": round((p - idle) / qps)}
    contrast = lambda k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in A[k].items() if kk in ("k1", "n1", "k2", "n2", "diff", "note")} \
        | ({"newcombe95": [round(x, 3) for x in A[k]["newcombe95"]]} if A[k].get("newcombe95") else {})
    errata = sorted(glob.glob("artifacts/retrieval/*.json"))
    return {
        "experiment": {"task": "pick a 268 g cola can from a start mark and stand it on a coaster (SO-101 arm)",
                       "policy": "LeRobot ACT 51.6M, one FP32 checkpoint; 24 INT8 variants differ only in calibration (size, composition, granularity)",
                       "deployment_target": "Jetson Orin Nano Super, 15W mode, TensorRT 10.3",
                       "protocol": "pre-registered; operator-blinded; interleaved; sealed until LOCK-3",
                       "lock2_record_hash": L2["record_hash"], "lock3_record_hash": L3["record_hash"],
                       "trials_main": A["n_trials_main"], "trials_retest": A["n_trials_retest"]},
        "cells": cells,
        "contrasts": {"EP-1_audit_vs_random": contrast("EP-1"), "ES-1_align_vs_mag": contrast("ES-1"), "ES-2_align_vs_cheapA": contrast("ES-2"),
                      "ES-3_align_vs_cheapB_partial": contrast("ES-3"), "ES-4_audit_vs_low": contrast("ES-4"),
                      "ES-5_retest_noise_floor": {"cell": A["ES-5"]["cell"], "main": A["ES-5"]["main"], "retest": A["ES-5"]["retest"],
                                                  "newcombe95": [round(x, 3) for x in A["ES-5"]["newcombe95"]]},
                      "holm_adjusted_p": {k: round(v, 3) for k, v in S["holm_H1_H2"]["holm_p"].items()}},
        "offline_rank_vs_placement_spearman": {k: {"rho": round(v["spearman"], 3), "perm_p": round(v["perm_p_two_sided"], 3)} for k, v in A["EX-4"].items()},
        "aep_q1_best_vs_worst_fidelity": {"E1": A["AEP_Q1"]["E1"]["decision"], "E2": A["AEP_Q1"]["E2"]["decision"],
                                          "E2_degradation_px": round(A["AEP_Q1"]["E2"]["degradation_px"], 2),
                                          "E2_ci_px": [round(x, 2) for x in A["AEP_Q1"]["E2"]["ci_px"]], "falsified": A["AEP_Q1"]["falsified"]},
        "engine_cost_trtexec": cost, "engine_cost_idle_module_power_mw": idle,
        "fp16_closed_loop": "not run yet (pre-registered, docs/fp16_real_arm_preregistration.md)",
        "ai_supervisor": {"shadow_trials": S["EX-3"]["main"]["trials_with_d4"] + S["EX-3"]["retest"]["trials_with_d4"],
                          "non_continue_verdicts": S["EX-3"]["main"]["trials_with_any_non_continue"] + S["EX-3"]["retest"]["trials_with_any_non_continue"],
                          "failures_flagged": len(S["EX-3"]["main"]["failures_flagged"]), "failures_total": len(S["EX-3"]["main"]["failures"]),
                          "retro_end_judge": {"n": R["n"], "answered_yes": R["vs_criterion"]["YES_pos"] + R["vs_criterion"]["YES_neg"],
                                              "failures_caught": R["vs_criterion"]["NO_neg"], "failures_total": R["vs_criterion"]["NO_neg"] + R["vs_criterion"]["YES_neg"]}},
        "errata_snapshot_files": [os.path.basename(e) for e in errata],
    }


SYSTEM = """You write the final deployment report for a pre-registered robotics quantization experiment.

HARD RULES:
1. Use ONLY numbers that appear in the evidence JSON. Never estimate, interpolate, average or invent.
2. If the evidence does not support a claim, say the evidence is absent.
3. Closed-loop results may be reported only as given. When a confidence interval includes zero, write "no difference
   detected", never "no difference" or "equivalent".
4. FP16 has NO closed-loop evidence. Do not claim FP16 is safe on the robot.
5. Stress-test results are not in the evidence. Do not mention their outcomes.
6. Concise and factual. No marketing words ("robust", "excellent", "significant improvement").
7. Write in English."""

USER = """Evidence (all numbers you may use):

```json
{evidence}
```

Write the report with exactly these sections:

## 1. Closed-loop summary
Success and placement per arm (FP32, INT8 groups). The primary contrast and the noise floor (retest), side by side.

## 2. Per-cell go / no-go
For each of the 10 INT8 cells: GO, NO-GO or UNDECIDED, with the evidence (success, vs_fp32 decisions). Group cells
that share the same verdict and reason.

## 3. Precision recommendation for this target
Use engine_cost_trtexec and the closed-loop results. State clearly which part of the recommendation still lacks
closed-loop evidence.

## 4. Supervisor and audit reliability
Whether the offline ranking predicted closed-loop results, and what the AI supervisor and end judge caught.

## 5. What this report cannot answer
"""


def call(ev, max_tokens):
    import http.client
    body = json.dumps({"model": d3.MODEL, "max_tokens": max_tokens, "temperature": 0.2, "messages": [
        {"role": "system", "content": SYSTEM}, {"role": "user", "content": USER.format(evidence=json.dumps(ev, indent=1))}]})
    conn = http.client.HTTPSConnection(d3.HOST, timeout=300); t0 = time.time()
    conn.request("POST", "/v1/chat/completions", body=body, headers={"Authorization": f"Bearer {os.environ['NEBIUS_API_KEY']}",
                                                                     "Content-Type": "application/json"})
    r = conn.getresponse(); raw = r.read(); conn.close()
    if r.status != 200: raise RuntimeError(f"HTTP {r.status}: {raw[:200].decode(errors='replace')}")
    d = json.loads(raw); return d["choices"][0]["message"]["content"] or "", d.get("usage", {}), time.time() - t0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="artifacts/reports"); ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--max-tokens", type=int, default=8192); a = ap.parse_args()
    ev = evidence(); h = hash_obj(ev); json.dump(ev, open(f"{a.out}/d3_final_evidence.json", "w"), indent=1)
    runs = []
    for i in range(a.repeats):
        text, usage, dt = call(ev, a.max_tokens); um = d3.verify_numbers(text, ev) if text.strip() else ["<empty>"]
        runs.append({"repeat": i, "latency_sec": round(dt, 1), "usage": usage, "unmatched_numbers": um,
                     "sections_present": sum(f"## {k}." in text for k in range(1, 6)), "text": text})
        d3.log(f"run {i}: {dt:.1f}s, unmatched {len(um)} {um[:8]}, sections {runs[-1]['sections_present']}/5")
    best = min(runs, key=lambda r: (len(r["unmatched_numbers"]), -r["sections_present"]))
    head = (f"# QuantGate — final deployment report (auto-generated)\n\n> Written by the `D3` agent ({d3.MODEL}, Nebius Token Factory) "
            f"from committed artifacts. Product component, not a scientific claim (§6). Numbers are machine-checked against the evidence.\n\n"
            f"| Item | Value |\n|---|---|\n| Evidence hash | `{h}` |\n| Evidence file | `artifacts/reports/d3_final_evidence.json` |\n"
            f"| Run selected | {best['repeat']} of {len(runs)} (fewest unmatched numbers) |\n| Latency | {best['latency_sec']} s |\n"
            f"| **Numbers not in evidence** | **{len(best['unmatched_numbers'])}**{(' — ' + ', '.join(best['unmatched_numbers'][:10])) if best['unmatched_numbers'] else ''} |\n\n---\n\n")
    open(f"{a.out}/d3_final_report.md", "w").write(head + best["text"])
    json.dump({"evidence_hash": h, "model": d3.MODEL, "runs": runs}, open(f"{a.out}/d3_final_runs.json", "w"), indent=1)
    print("written", f"{a.out}/d3_final_report.md")
