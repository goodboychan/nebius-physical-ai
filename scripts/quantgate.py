"""QuantGate command line: one entry point for the deployment review.

  quantgate.py review [--no-llm]   rebuild the decision layer from committed evidence, in order:
                                   verdict table -> D3 report v3 (Nemotron on Token Factory, unless --no-llm) and figures
                                   -> next-test plans -> the full review as one HTML file (artifacts/reports/review_report.html,
                                   no API key needed) -> dashboard report section -> deployment preflight demo -> review cost
  quantgate.py plan [candidate]    from evidence to the next test: confirmed, open, evidence, and the next test's plan
                                   (FP16, FT1, FT2, INT8, PC-B; all when omitted), written by code
  quantgate.py ask "<question>"    ask the review (Nemotron picks the rows, code prints verdicts and numbers)
  quantgate.py preflight [--card c.json]  the four-check preflight on your own candidate card (exit 0 OK, 3 HOLD,
                                   4 BLOCK), or without --card its fault-injection demo
  quantgate.py judge <csv>         your own results under the same rules: decision, why, next test (examples/my_results.csv);
                                   --gate makes the exit code the decision (0 GO, 3 HOLD, 4 BLOCK) for CI
  quantgate.py tally <log.jsonl>   per-trial logs -> the judge CSV row, with an explicit success definition
  quantgate.py card --engine ...   the candidate card and normalization manifest, from the files and the logs
  quantgate.py cost                what the review cost (Nebius list prices, real-arm hours)
  quantgate.py verify              tests, runner harness, and the sealed-log hashes against the post-lock records
  quantgate.py stages              the hardware and cloud stages that produce the evidence, with their commands

`review`, `preflight`, `cost` and `verify` need no robot, no GPU and no network (except `review` without --no-llm and
`ask`, which call Nebius Token Factory with NEBIUS_API_KEY).
Usage: python scripts/quantgate.py <command> [...]   (quantgate.py <command> -h for its options; bad input exits 2)"""
import hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); PY = sys.executable
run = lambda *a: (print("$", " ".join(a), file=sys.stderr, flush=True), subprocess.run([PY, *a], cwd=ROOT, check=True))   # stdout stays the result

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
                    ("ft4_post.json", "ft4_unsealed"), ("int8c2_post.json", "int8c2_unsealed"), ("ft5_post.json", "ft5_unsealed"), ("ft6_post.json", "ft6_unsealed")):
        p = os.path.join(ROOT, "artifacts/freeze", post)
        if not os.path.exists(p): continue
        for f, v in json.load(open(p))["sealed_logs"].items():
            q = os.path.join(ROOT, "artifacts/trials", d, f)
            want = v["sha256"] if isinstance(v, dict) else v
            ok = os.path.exists(q) and hashlib.sha256(open(q, "rb").read()).hexdigest() == want; bad += not ok
            print(f"  {'ok ' if ok else 'BAD'} {post}: {f}")
    if bad: sys.exit(f"{bad} sealed log(s) do not match their post-lock record")


# names people use for the plan candidates -> the ids in next_test_plans.json
ALIASES = {"fp16": "VC-025", "vc025": "VC-025", "ft": "FT-FP16", "ft1": "FT-FP16", "finetune": "FT-FP16", "finetunev1": "FT-FP16",
           "ftfp16": "FT-FP16", "ft2": "FT2-FP16", "finetunev2": "FT2-FP16", "ft2fp16": "FT2-FP16", "int8": "INT8",
           "pcb": "PC-B", "blackframe": "PC-B", "blackframecalibration": "PC-B"}


def plan(name):
    P = json.load(open(os.path.join(ROOT, "artifacts/reports/next_test_plans.json")))
    if name:
        k = ALIASES.get("".join(c for c in name.lower() if c.isalnum()))
        if k not in P:
            print(f"quantgate.py plan: unknown candidate {name!r}; use one of FP16 (VC-025), FT1 (FT-FP16), FT2 (FT2-FP16), INT8, PC-B", file=sys.stderr); sys.exit(2)
        P = {k: P[k]}
    sys.path.insert(0, HERE); import next_test_plan as ntp; print(ntp.md(P))


def need_key(cmd):
    if not os.environ.get("NEBIUS_API_KEY"):
        sys.exit(f"quantgate.py {cmd}: needs a Nebius Token Factory key: export NEBIUS_API_KEY=... (https://studio.nebius.com)\n"
                 "Without a key: `quantgate.py review --no-llm` rebuilds the whole review, `quantgate.py plan FP16` prints one plan.")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="quantgate.py", description="QuantGate: the deployment review of quantized robot policies.",
                                 epilog="Exit codes: 0 ok; 1 a step failed or NEBIUS_API_KEY is missing; 2 usage error (unknown command, option, candidate or bad card); preflight --card and judge --gate: 3 HOLD, 4 BLOCK.")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="<command>")
    r = sub.add_parser("review", help="rebuild the decision layer from committed evidence")
    r.add_argument("--no-llm", action="store_true", help="skip the Nemotron report (no key, no network)")
    p = sub.add_parser("plan", help="from evidence to the next test, written by code")
    p.add_argument("candidate", nargs="?", help="FP16, FT1, FT2, INT8 or PC-B (or VC-025, FT-FP16, FT2-FP16); all when omitted")
    q = sub.add_parser("ask", help="ask the review a question (needs NEBIUS_API_KEY)"); q.add_argument("question", nargs="+")
    f = sub.add_parser("preflight", help="the four-check preflight: your own card, or the fault-injection demo")
    f.add_argument("--card", help="your candidate card, e.g. examples/candidate/candidate.json (exit 0 OK, 3 HOLD, 4 BLOCK)")
    f.add_argument("--json", help="with --card: also write the result as JSON")
    f.add_argument("--checks-only", action="store_true", help="with --card: engine, normalization and timing only (for judge --preflight)")
    f.add_argument("--judge", help="with --card: take the verdict from this judge --json output for the card's candidate")
    c = sub.add_parser("card", help="write a candidate card and the normalization manifest from the files and trial logs")
    c.add_argument("--engine", required=True, help="the build's .engine file"); c.add_argument("--norm", required=True, help="its normalization file, next to the engine")
    c.add_argument("--candidate", required=True, help="the build's name, as in the logs and the judge CSV")
    c.add_argument("--latency-from", nargs="+", metavar="LOG", help="trial logs (JSONL): the card takes the max of --latency-field over the candidate's trials")
    c.add_argument("--latency-field", default="rtt_ms", help="per-trial worst round trip, observation to action, in ms (default rtt_ms)")
    c.add_argument("--latency-ms", type=float, help="instead of --latency-from: the measured worst case in ms")
    c.add_argument("--group", default="cell", help="the log field naming the build (default cell)"); c.add_argument("--out", required=True)
    j = sub.add_parser("judge", help="your own results under the same rules (examples/my_results.csv)")
    j.add_argument("csv"); j.add_argument("--rule", choices=["revised", "study", "current"], default="revised", help="revised (default) for a new project; study (alias current) reproduces this study's rule. Choose before the trials"); j.add_argument("--tol", type=float, default=10.0); j.add_argument("--json")
    j.add_argument("--md", help="also write the report as Markdown"); j.add_argument("--gate", action="store_true", help="exit 0 all GO, 3 any HOLD, 4 any BLOCK (for CI)")
    j.add_argument("--preflight", help="fill preflight_ok from `preflight --card c.json --checks-only --json pre.json`")
    sub.add_parser("tally", help="per-trial JSONL logs -> one judge CSV row (quantgate.py tally -h)")
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["tally"]:   # its own parser, so `tally -h` shows the tally options
        sys.path.insert(0, HERE); import quantgate_tally; sys.exit(quantgate_tally.main(argv[1:]))
    sub.add_parser("cost", help="what the review cost (Nebius list prices, real-arm hours)")
    sub.add_parser("verify", help="tests, runner harness, and the sealed-log hashes against the post-lock records")
    sub.add_parser("stages", help="the hardware and cloud stages that produce the evidence")
    a = ap.parse_args(argv)
    if a.cmd == "review":
        if not a.no_llm: need_key("review (without --no-llm)")
        run("scripts/d3_report_v3.py", *(["--dry"] if a.no_llm else []))
        if not a.no_llm: run("scripts/build_dashboard_report.py")
        run("scripts/next_test_plan.py"); run("scripts/build_review_html.py"); run("scripts/build_dashboard_nexttest.py")
        run("scripts/deploy_preflight.py"); run("scripts/review_cost.py")
        print("review rebuilt: artifacts/reports/" + ("{d3_v3_verdicts.json" if a.no_llm else "{d3_report_v3.md, d3_v3_verdicts.json") +
              ", next_test_plans.md, review_report.html, preflight_demo.json, review_cost.md}" + ("" if a.no_llm else "; dashboard/audit_gate.html"))
        print("open artifacts/reports/review_report.html in a browser: the whole review, no key needed")
    elif a.cmd == "ask": need_key("ask"); run("scripts/quantgate_ask.py", *a.question)
    elif a.cmd == "plan": plan(a.candidate)
    elif a.cmd == "preflight":
        if a.card:
            if a.checks_only and a.judge: ap.error("preflight: use --checks-only or --judge, not both")
            sys.path.insert(0, HERE); import deploy_preflight as dp; sys.exit(dp.run_card(a.card, a.json, a.checks_only, a.judge))
        if a.json or a.checks_only or a.judge: ap.error("preflight --json, --checks-only and --judge need --card")
        run("scripts/deploy_preflight.py")
    elif a.cmd == "judge":   # the step runs from the repo root, so the user's paths are made absolute first
        ab = os.path.abspath
        run("scripts/quantgate_judge.py", ab(a.csv), "--rule", a.rule, "--tol", str(a.tol), *(["--json", ab(a.json)] if a.json else []),
            *(["--md", ab(a.md)] if a.md else []), *(["--gate"] if a.gate else []), *(["--preflight", ab(a.preflight)] if a.preflight else []))
    elif a.cmd == "card":
        sys.path.insert(0, HERE); import deploy_preflight as dp
        try: card = dp.make_card(a.engine, a.norm, a.candidate, a.out, a.latency_ms, a.latency_from, a.latency_field, a.group)
        except dp.CardError as e: print(f"error: {e}", file=sys.stderr); sys.exit(2)
        print(f"wrote {a.out}: {card['candidate']}, engine {card['engine_sha256'][:12]}, {card['latency_label']} {card['latency_ms']} ms; "
              f"normalization manifest next to the engine")
    elif a.cmd == "cost": run("scripts/review_cost.py")
    elif a.cmd == "verify": verify()
    elif a.cmd == "stages": print(STAGES)


if __name__ == "__main__":
    try: main()
    except subprocess.CalledProcessError as e: sys.exit(e.returncode)   # the step already printed its error (or its gate code); no traceback
