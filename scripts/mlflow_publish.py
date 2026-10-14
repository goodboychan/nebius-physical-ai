"""Populate an MLflow tracking server from committed artifacts only (decision_log 2026-10-12: nothing typed by hand).
Experiments:
  quantgate/grid-offline        one run per grid cell: build settings + G4 offline scores (2,000 audit states)
  quantgate/deployment-verdicts one run per D3 v2 verdict row (code-decided GO / NO-GO / INSUFFICIENT_EVIDENCE)
  quantgate/real-arm            one run per (block, cell): sealed real-arm successes, placement, intervals
  quantgate/cosmos-judge        one run per judge condition on the held-out eval set
  quantgate/hailo-probe         Hailo-8 cells and their Orin counterparts
Each run is tagged with the git commit and the source file it was read from. Re-running replaces runs by name.
Usage: MLFLOW_TRACKING_URI=... [MLFLOW_TRACKING_USERNAME/PASSWORD] python mlflow_publish.py [--g4 <g4 dir>] [--g3 <onnx_results.json>]"""
import argparse, json, os, subprocess
import mlflow
from mlflow.tracking import MlflowClient

ap = argparse.ArgumentParser()
ap.add_argument("--g4", default=os.path.expanduser("~/edgeqgate_data/g4"))
ap.add_argument("--g3", default=os.path.expanduser("~/edgeqgate_data/g3_onnx/onnx_results.json"))
a = ap.parse_args()
REP = "artifacts/reports"
COMMIT = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
cl = MlflowClient()

def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x

def run(exp, name, src, params=None, metrics=None, tags=None, artifacts=()):
    e = mlflow.set_experiment(exp)
    for r in cl.search_runs([e.experiment_id], f"tags.mlflow.runName = '{name}'"):
        cl.delete_run(r.info.run_id)
    with mlflow.start_run(run_name=name):
        mlflow.set_tags({"git_commit": COMMIT, "source": src, **(tags or {})})
        if params: mlflow.log_params({k: str(v) for k, v in params.items() if v is not None})
        if metrics: mlflow.log_metrics({k: float(v) for k, v in metrics.items() if num(v)})
        for p in artifacts:
            if os.path.exists(p): mlflow.log_artifact(p)

def kn(prefix, k, n):
    return {f"{prefix}_k": k, f"{prefix}_n": n, f"{prefix}_rate": k / n if n else None}

# 1. grid, offline
g3 = json.load(open(a.g3)); g4 = json.load(open(f"{a.g4}/g4_payload_index.json"))["cells"]
for c, x in sorted(g3.items()):
    if not c.startswith("VC-"): continue
    s = g4.get(c, {})
    run("quantgate/grid-offline", c, "g3_onnx/onnx_results.json + g4/g4_payload_index.json",
        {k: x.get(k) for k in ("precision", "calib_size", "calib_composition", "granularity", "onnx_sha256", "calib_set_hash")},
        {"g4_mag_mean": s.get("mag_mean"), "g4_align_mean": s.get("align_mean"), "cheap_B": s.get("cheap_B"),
         "orin_gpu_ms_median": s.get("cheap_C_ms"), "n_quantized_nodes": x.get("n_quantize")})

# 2. deployment verdicts
V = json.load(open(f"{REP}/d3_v2_verdicts.json"))
for i, r in enumerate(V["rows"]):
    ci = r.get("e1_ci_pp") or [None, None]
    counts = {**kn("success", *r["success"]), **kn("reference", *r["reference"])} if "success" in r else {}
    run("quantgate/deployment-verdicts", f"{r['candidate']} | {r['context']}", f"{REP}/d3_v2_verdicts.json#rows[{i}]",
        {"candidate": r["candidate"], "context": r["context"], "e2": r.get("e2"), "evidence_path": r.get("evidence_path"),
         "flagged_by": ", ".join(r.get("flagged_by", [])) or None},
        {**counts, "e1_ci_low_pp": ci[0], "e1_ci_high_pp": ci[1],
         "e2e_ms": r.get("e2e_ms"), "gpu_ms_trtexec": r.get("gpu_ms_trtexec")},
        {"verdict": r["verdict"]}, artifacts=[f"{REP}/d3_report_v2.md"] if i == 0 else ())

# 3. real-arm blocks
G6 = json.load(open(f"{REP}/g6_analysis.json"))
for c, x in G6["cells"].items():
    w = x.get("wilson95") or [None, None]
    run("quantgate/real-arm", f"G6 | {c}", f"{REP}/g6_analysis.json#cells.{c}", {"block": "G6 nominal (pads)", "cell": c},
        {**kn("success", x["k"], x["n"]), "wilson95_low": w[0], "wilson95_high": w[1], "place_mean_px": x.get("place_mean"),
         "aborted": x.get("aborted"), "not_detected": x.get("not_detected")})
S = json.load(open(f"{REP}/stress_v2_analysis.json"))
for blk in ("S0", "S1", "S4"):
    cells = (S.get(blk) or {}).get("cells", {})
    for c, x in cells.items():
        w = x.get("wilson95") or [None, None]
        run("quantgate/real-arm", f"stress v2 {blk} | {c}", f"{REP}/stress_v2_analysis.json#{blk}.cells.{c}", {"block": f"stress v2 {blk}", "cell": c},
            {**kn("success", x["k"], x["n"]), "wilson95_low": w[0], "wilson95_high": w[1], "place_mean_px": x.get("place_mean"), "aborted": x.get("aborted")})
for f, blk in (("fp16_analysis.json", "FP16 block"), ("positive_control_analysis.json", "positive control (PC-B)")):
    D = json.load(open(f"{REP}/{f}"))
    for c, x in D["cells"].items():
        run("quantgate/real-arm", f"{blk} | {c}", f"{REP}/{f}#cells.{c}", {"block": blk, "cell": c},
            {**kn("success", x["k"], x["n"]), "place_mean_px": x.get("place_mean")})

# 4. Cosmos judge, held-out eval
for line in open("artifacts/cosmos_judge/eval_scores.jsonl"):
    x = json.loads(line)
    fr, fa = x["failure_recall"], x["false_alarm"]
    run("quantgate/cosmos-judge", f"{x['cond']} {x['variant']}", "artifacts/cosmos_judge/eval_scores.jsonl",
        {"condition": x["cond"], "variant": x["variant"], "set": x["set"], "model": "nvidia/Cosmos-Reason2-2B"},
        {"failure_recall": fr[0] / fr[1], "failure_recall_k": fr[0], "n_fail": fr[1], "failure_recall_wilson_low": fr[2][0],
         "false_alarm_rate": fa[0] / fa[1], "false_alarm_k": fa[0], "n_success": fa[1], "balanced_accuracy": x["balanced_accuracy"],
         "abstain": x["abstain"][0], "latency_ms_median": x.get("latency_ms_median")})

# 5. Hailo probe
H = json.load(open(f"{REP}/hailo_probe_v1.json"))
for c, x in H["reference"].items():
    run("quantgate/hailo-probe", f"Orin {c}", f"{REP}/hailo_probe_v1.json#reference.{c}", {"target": "Jetson Orin Nano Super, TensorRT 10.3", "scope": "whole graph", "cell": c},
        {"mag_mean": x["mean"], "mag_p90": x["p90"], "latency_ms_median": x["orin_gpu_ms_median"]})
for c, x in H["cells"].items():
    L = x.get("latency", {})
    run("quantgate/hailo-probe", f"Hailo-8 {c}", f"{REP}/hailo_probe_v1.json#cells.{c}",
        {"target": "Raspberry Pi 5 + Hailo-8, DFC 3.34.0 / HailoRT 4.20", "scope": "backbones INT8, CPU FP32 tail", "cell": c, "orin_twin": x["twin"]},
        {"mag_mean": x["device_int8"]["mean"], "mag_p90": x["device_int8"]["p90"], "mag_mean_emulator": x["emulated_int8"]["mean"],
         "device_vs_emulator_mean": x["device_vs_emulator"]["mean"], "split_check_mean": x["split_check_fp_optimized"]["mean"],
         "over_twin": x["device_over_twin_mean"], "latency_ms_median": L.get("total_ms", [None])[0],
         "backbone_ms_median": L.get("backbone_ms", [None])[0], "tail_ms_median": L.get("tail_ms", [None])[0]},
        artifacts=["docs/hailo_portability_probe.md"])
print("done", COMMIT[:8], mlflow.get_tracking_uri())
