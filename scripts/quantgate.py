"""QuantGate command line: one entry point for the deployment review.

  quantgate.py review [--no-llm]   rebuild the decision layer from committed evidence, in order:
                                   verdict table -> D3 report v3 (Nemotron on Token Factory, unless --no-llm) and figures
                                   -> next-test plans -> the full review as one HTML file (artifacts/reports/review_report.html,
                                   no API key needed) -> dashboard report section -> deployment preflight demo -> review cost
  quantgate.py plan [candidate]    from evidence to the next test: confirmed, open, evidence, and the next test's plan
                                   (VC-025, FT-FP16, INT8, PC-B; all when omitted), written by code
  quantgate.py ask "<question>"    ask the review (Nemotron picks the rows, code prints verdicts and numbers)
  quantgate.py preflight           the four-check preflight and its fault-injection demo
  quantgate.py cost                what the review cost (Nebius list prices, real-arm hours)
  quantgate.py verify              tests, runner harness, and the sealed-log hashes against the post-lock records
  quantgate.py stages              the hardware and cloud stages that produce the evidence, with their commands

`review`, `preflight`, `cost` and `verify` need no robot, no GPU and no network (except `review` without --no-llm and
`ask`, which call Nebius Token Factory with NEBIUS_API_KEY).
Usage: python scripts/quantgate.py <command> [...]"""
import hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); PY = sys.executable
run = lambda *a: (print("$", " ".join(a), flush=True), subprocess.run([PY, *a], cwd=ROOT, check=True))

STAGES = """Evidence stages (run once per policy; each writes committed, hashed artifacts):
  1. Data        lerobot-record on the SO-101 -> LOCK-1 split        edgeqgate.splits (manifest in artifacts/manifests/)
  2. Train       Nebius Jobs, L40S                                    scripts/job/train_act.sh, scripts/job/finetune_act.sh
  3. Candidates  ModelOpt INT8 grid + FP16 (NGC container)            scripts/build_grid_lerobot.py
  4. Engines     TensorRT on the Jetson, frozen timing cache          scripts/build_engines_orin.sh;  cost: scripts/orin_power_bench.sh
  5. Audit       2,000 held-out states, Nebius Jobs fan-out           scripts/g4_prepare_states.py, scripts/g4_build_payload.py, scripts/job/audit_job_g4.py
  6. LOCK-2      freeze rankings before any trial                     scripts/g4_lock2.py
  7. Real arm    sealed, interleaved, operator-blind schedule         scripts/*_schedule.py;  scripts/so101_trial.py --blind <block>
  8. Unseal      hash logs (artifacts/freeze/*_post.json), re-judge, analyse (scripts/*_analysis.py)
  9. Review      python scripts/quantgate.py review"""


def verify():
    run("-m", "pytest", "-q"); run("tests/runner_abort_harness.py")
    bad = 0
    for post, d in (("lock3.json", "g6_unsealed"), ("stress_v1_post.json", "stress_unsealed/v1"), ("stress_v2_post.json", "stress_unsealed/v2"),
                    ("fp16_post.json", "fp16_unsealed"), ("pc_post.json", "pc_unsealed"), ("ft_post.json", "ft_unsealed"), ("ft2_post.json", "ft2_unsealed"), ("ft3_post.json", "ft3_unsealed"),
                    ("ft4_post.json", "ft4_unsealed"), ("int8c2_post.json", "int8c2_unsealed"), ("ft5_post.json", "ft5_unsealed")):
        p = os.path.join(ROOT, "artifacts/freeze", post)
        if not os.path.exists(p): continue
        for f, v in json.load(open(p))["sealed_logs"].items():
            q = os.path.join(ROOT, "artifacts/trials", d, f)
            want = v["sha256"] if isinstance(v, dict) else v
            ok = os.path.exists(q) and hashlib.sha256(open(q, "rb").read()).hexdigest() == want; bad += not ok
            print(f"  {'ok ' if ok else 'BAD'} {post}: {f}")
    if bad: sys.exit(f"{bad} sealed log(s) do not match their post-lock record")


if __name__ == "__main__":
    a = sys.argv[1:] or ["-h"]
    if a[0] == "review":
        run("scripts/d3_report_v3.py", *(["--dry"] if "--no-llm" in a else []))
        if "--no-llm" not in a: run("scripts/build_dashboard_report.py")
        run("scripts/next_test_plan.py"); run("scripts/build_review_html.py"); run("scripts/build_dashboard_nexttest.py")
        run("scripts/deploy_preflight.py"); run("scripts/review_cost.py")
        print("review rebuilt: artifacts/reports/" + ("{d3_v3_verdicts.json" if "--no-llm" in a else "{d3_report_v3.md, d3_v3_verdicts.json") +
              ", next_test_plans.md, review_report.html, preflight_demo.json, review_cost.md}" + ("" if "--no-llm" in a else "; dashboard/audit_gate.html"))
        print("open artifacts/reports/review_report.html in a browser: the whole review, no key needed")
    elif a[0] == "ask": run("scripts/quantgate_ask.py", *a[1:])
    elif a[0] == "plan":
        P = json.load(open(os.path.join(ROOT, "artifacts/reports/next_test_plans.json")))
        keys = [k for k in P if not a[1:] or k.lower() == a[1].lower()] or sys.exit(f"unknown candidate; one of {list(P)}")
        sys.path.insert(0, HERE); import next_test_plan as ntp; print(ntp.md({k: P[k] for k in keys}))
    elif a[0] == "preflight": run("scripts/deploy_preflight.py")
    elif a[0] == "cost": run("scripts/review_cost.py")
    elif a[0] == "verify": verify()
    elif a[0] == "stages": print(STAGES)
    else: print(__doc__)
