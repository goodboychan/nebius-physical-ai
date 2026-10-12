"""FP16 real-arm analysis (docs/fp16_real_arm_preregistration.md §5). Written and hashed before the first F0 trial.
Runs only after artifacts/freeze/fp16_post.json exists, except --synthetic.

Outcome: as in stress v2 (protocol §9): offline re-judge of the saved video (stress_rejudge.py) ∧ released ∧ no contact.
Primary: VC-025 (FP16) vs VC-000 (FP32). Degradation = FP32 - FP16 for E1 (pp) and FP16 - FP32 for E2 (px).
  Unpaired percentile bootstrap, 10,000 draws, family = 2 endpoints -> 97.5% two-sided CI. AEP decision semantics,
  tolerances E1 10 pp, E2 5 px, ceiling rule (both >= 95% -> E1 indeterminate).
Secondary: VC-025 vs VC-002 (INT8 best fidelity), same CI.
Descriptive: per-cell end-to-end inference latency (sealed infer_ms_mean), late chunks, step-time max.
Usage: python scripts/fp16_analysis.py --sealed-dir <dir> --rejudge <json> --out <json> | --synthetic --out <json>"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stress_analysis as sa

CONF = 1 - 0.05 / 2


def run(rows, n_boot):
    cs = sa.cells_of(rows); rep = {"n": len(rows)}
    rep["cells"] = {c: {"k": int(sum(v["s"])), "n": len(v["s"]), "place_mean": float(np.mean(v["place"])) if v["place"] else None}
                    for c, v in sorted(cs.items())}
    if "VC-000" in cs and "VC-025" in cs: rep["primary_fp16_vs_fp32"] = sa.compare(cs["VC-000"], cs["VC-025"], "FP16-v1/primary", CONF, n_boot)
    if "VC-002" in cs and "VC-025" in cs: rep["secondary_fp16_vs_int8"] = sa.compare(cs["VC-002"], cs["VC-025"], "FP16-v1/secondary", CONF, n_boot)
    lat = {}
    for r in rows:
        l = lat.setdefault(r["cell"], {"infer_ms": [], "late": 0, "step_max": []})
        if "infer_ms_mean" in r: l["infer_ms"].append(r["infer_ms_mean"])
        l["late"] += r.get("late_chunks", 0)
        if "step_ms_p50_p99_max" in r: l["step_max"].append(r["step_ms_p50_p99_max"][2])
    rep["latency"] = {c: {"infer_ms_mean": float(np.mean(v["infer_ms"])) if v["infer_ms"] else None, "late_chunks": v["late"],
                          "step_max_ms_median": float(np.median(v["step_max"])) if v["step_max"] else None} for c, v in lat.items()}
    p = rep.get("primary_fp16_vs_fp32")
    rep["falsified_fp16_safe"] = bool(p) and any(p[e]["decision"] == "materially_degraded" for e in ("E1", "E2"))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--sealed-dir"); ap.add_argument("--rejudge"); ap.add_argument("--out")
    ap.add_argument("--synthetic", action="store_true"); ap.add_argument("--n-boot", type=int, default=10000)
    a = ap.parse_args()
    if a.synthetic:
        rng = np.random.default_rng(1)
        rows = [{"cell": c, "trial_id": f"t{i}", "success": bool(rng.random() < 0.9), "aborted": False, "released": True, "human_contact": False,
                 "judge_auto": {"success": True, "base_dist_px": float(rng.normal(20, 3))}, "infer_ms_mean": {"VC-025": 25, "VC-000": 79, "VC-002": 34}[c]}
                for i, c in enumerate(["VC-025"] * 20 + ["VC-000"] * 10 + ["VC-002"] * 10)]
        rep = run(rows, a.n_boot); rep["SYNTHETIC"] = True
    else:
        if not os.path.exists("artifacts/freeze/fp16_post.json"): sys.exit("fp16_post.json이 없다. F0 trial을 모두 마치고 봉인 로그 해시를 고정한 뒤 실행한다")
        sa.REJ.update(json.load(open(a.rejudge)))
        rep = run(sa.load(os.path.join(a.sealed_dir, "stress_fp16_F0_sealed.jsonl")), a.n_boot)
    json.dump(rep, open(a.out, "w"), indent=1, default=str); print("written", a.out)
