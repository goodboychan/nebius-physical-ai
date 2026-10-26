"""Developer usability review (2026-10-24): bad commands and options fail loudly, plan takes user-facing names,
a candidate card of your own runs through the preflight, and ask without a key explains itself."""
import json, os, pathlib, shutil, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "scripts/quantgate.py")]


def q(*a, env=None):
    e = {k: v for k, v in os.environ.items() if k != "NEBIUS_API_KEY"} | (env or {})
    return subprocess.run([*CLI, *a], cwd=ROOT, capture_output=True, text=True, env=e)


def test_bad_input_exits_2():
    for a in (["verfiy"], [], ["preflight", "--bogus"], ["preflight", "--card", "nonexistent.json"], ["plan", "nope"], ["preflight", "--json", "x.json"]):
        r = q(*a); assert r.returncode == 2, (a, r.returncode, r.stdout, r.stderr)
        assert "Traceback" not in r.stderr


def test_plan_user_names():
    for name, head in (("FP16", "## VC-025"), ("fine-tune v2", "## FT2-FP16"), ("ft1", "## FT-FP16"), ("black-frame", "## PC-B"), ("VC-025", "## VC-025")):
        r = q("plan", name); assert r.returncode == 0 and head in r.stdout, (name, r.stderr)


def test_ask_without_key_is_friendly():
    r = q("ask", "is FP16 approved?")
    assert r.returncode == 1 and "NEBIUS_API_KEY" in r.stderr and "Traceback" not in r.stderr


def test_example_card_and_broken_cards(tmp_path):
    r = q("preflight", "--card", "examples/candidate/candidate.json")
    assert r.returncode == 3 and "preflight: HOLD" in r.stdout          # INSUFFICIENT_EVIDENCE holds
    d = tmp_path / "c"; shutil.copytree(ROOT / "examples/candidate", d); card = json.load(open(d / "candidate.json"))
    def run(c):
        json.dump(c, open(d / "candidate.json", "w")); return q("preflight", "--card", str(d / "candidate.json")).returncode
    assert run({**card, "verdict": "GO"}) == 0
    assert run({**card, "latency_ms": 264}) == 4                         # misses the 200 ms chunk deadline
    assert run({**card, "engine_sha256": "0" * 64}) == 4                 # engine is not the audited build
    assert run({k: v for k, v in card.items() if k != "latency_ms"}) == 2  # missing field
    (d / "norm_manifest.json").unlink(); assert run(card) == 4           # runner refuses without a manifest


def test_dashboard_links_known_files_only():
    import pytest
    if not (ROOT / ".git").exists(): pytest.skip("links need a git checkout (e.g. not in the submission zip)")
    sys.path.insert(0, str(ROOT / "scripts")); import dash_links as L
    doc = "<p>see artifacts/freeze/fp16_post.json and artifacts/nope.json</p><script>x='artifacts/freeze/fp16_post.json'</script>"
    out = L.link_html(doc)
    assert out.count('class="gh"') == 1 and "/blob/" in out and "nope.json</p>" in out and "x='artifacts" in out
    assert L.link_html(out) == out


def test_card_latency_must_be_positive_and_finite(tmp_path):
    """Usability review 2: latency_ms = -1 passed the timing check (OK, exit 0)."""
    d = tmp_path / "c"; shutil.copytree(ROOT / "examples/candidate", d); card = json.load(open(d / "candidate.json"))
    for bad in (-1, 0, float("nan"), float("inf"), "96", True):
        json.dump({**card, "verdict": "GO", "latency_ms": bad}, open(d / "candidate.json", "w"))
        r = q("preflight", "--card", str(d / "candidate.json")); assert r.returncode == 2 and "latency_ms" in r.stderr, bad
    sys.path.insert(0, str(ROOT / "scripts")); import deploy_preflight as dp   # the check itself also refuses, not only the loader
    assert dp.preflight({**dp.load_card(str(ROOT / "examples/candidate/candidate.json")), "latency_ms": -1, "verdict": "GO"})[0] == "BLOCK"


def test_tally_reproduces_the_study_from_the_sealed_log(tmp_path):
    """Tester feedback (2026-10-24): logs -> judge row. The success definition decides the count."""
    log = "artifacts/trials/fp16_unsealed/stress_fp16_F0_sealed.jsonl"; base = ["tally", log, "--candidate", "VC-025", "--reference", "VC-000"]
    assert q(*base).stdout.splitlines()[1] == "VC-025,VC-000,18,20,9,10"     # live automatic judge
    r = q(*base, "--success", "artifacts/fp16/rejudge/F0_consensus.json:success_geom", "--and", "released", "--not", "human_contact")
    assert r.stdout.splitlines()[1] == "VC-025,VC-000,19,20,10,10"            # pre-registered outcome, as in fp16_analysis.json
    out = tmp_path / "r.csv"
    assert q(*base, "--set", "placement_ok=yes", "--append", str(out)).returncode == 0
    assert q("judge", str(out)).returncode == 0
    for bad in (["--candidate", "VC-999"], ["--set", "mode=improvment"], ["--success", "nope.json:x"], ["--success", "steps"]):
        r = q(*base, *bad); assert r.returncode == 2 and "Traceback" not in r.stderr, (bad, r.stderr)


def test_judge_gate_and_paths_from_another_folder(tmp_path):
    """judge --gate: 0 all GO, 3 any HOLD, 4 any BLOCK; a relative path is the caller's, not the repo's."""
    H = "candidate,reference,cand_successes,cand_trials,ref_successes,ref_trials,placement_ok,preflight_ok\n"
    for rows, want in (("A,B,118,120,117,120,yes,yes\n", 0), ("A,B,19,20,10,10,yes,yes\n", 3), ("A,B,118,120,117,120,yes,no\nA,B,19,20,10,10,yes,yes\n", 4)):
        (tmp_path / "r.csv").write_text(H + rows)
        r = subprocess.run([*CLI, "judge", "r.csv", "--rule", "revised", "--gate", "--md", "r.md"], cwd=tmp_path, capture_output=True, text=True)
        assert r.returncode == want, (rows, r.returncode, r.stderr)
        assert (tmp_path / "r.md").read_text().startswith("# QuantGate judge")


def test_malformed_manifest_blocks_not_crashes(tmp_path):
    d = tmp_path / "c"; shutil.copytree(ROOT / "examples/candidate", d)
    for text in ("{broken", '["x"]', '{"policy": 3}'):
        (d / "norm_manifest.json").write_text(text)
        r = q("preflight", "--card", str(d / "candidate.json")); assert r.returncode == 4 and "Traceback" not in r.stderr, (text, r.stderr)


def test_tally_refuses_counting_a_trial_twice(tmp_path):
    """Usability review 4: the same log 20 times read 380/400 vs 200/200 and turned HOLD into GO."""
    log = "artifacts/trials/fp16_unsealed/stress_fp16_F0_sealed.jsonl"
    (tmp_path / "copy.jsonl").write_text(open(ROOT / log).read())
    (tmp_path / "part.jsonl").write_text("".join(open(ROOT / log).readlines()[5:8]))
    (tmp_path / "noid.jsonl").write_text('{"cell": "VC-025", "success": true}\n')
    base = ["--candidate", "VC-025", "--reference", "VC-000"]
    for logs, msg in (([log, log], "log given twice"), ([log, "./" + log], "log given twice"), ([log, str(tmp_path / "copy.jsonl")], "duplicate trial"),
                      ([log, str(tmp_path / "part.jsonl")], "duplicate trial"), ([str(tmp_path / "noid.jsonl")], "no 'trial_id'")):
        r = q("tally", *logs, *base); assert r.returncode == 2 and msg in r.stderr, (logs, r.stderr)


def test_linked_checks_judge_preflight(tmp_path):
    """Usability review 4: readiness checks -> judge preflight_ok -> full preflight, tied by candidate name and engine hash."""
    d = tmp_path / "ex"; shutil.copytree(ROOT / "examples", d); card, res = d / "gate/candidate.json", d / "gate/results.csv"
    pre, jj = tmp_path / "pre.json", tmp_path / "judge.json"
    def flow():
        c = q("preflight", "--card", str(card), "--checks-only", "--json", str(pre)).returncode
        j = q("judge", str(res), "--rule", "revised", "--preflight", str(pre), "--json", str(jj), "--gate")
        p = q("preflight", "--card", str(card), "--judge", str(jj)).returncode if j.returncode in (0, 3, 4) else None
        return c, j.returncode, p, j.stderr
    assert flow()[:3] == (0, 0, 0)                                   # intact build: GO end to end
    assert json.load(open(jj))[0]["engine_sha256"] == json.load(open(card))["engine_sha256"]
    (d / "candidate/policy.engine").write_bytes(b"tampered")
    c, j, p, _ = flow(); assert (c, j, p) == (4, 4, 4)               # tampered engine: blocked at every stage
    shutil.copy(ROOT / "examples/candidate/policy.engine", d / "candidate/policy.engine")
    res.write_text(res.read_text().replace(",yes,,", ",yes,no,")); assert flow()[1] == 2   # hand-entered preflight_ok disagrees
    res.write_text(open(ROOT / "examples/gate/results.csv").read().replace(json.load(open(card))["engine_sha256"], "0" * 64))
    c, j, p, err = flow(); assert j == 2 and "not the same build" in err  # CSV row names another engine
    assert q("judge", str(res), "--preflight", str(ROOT / "examples/candidate/candidate.json")).returncode == 2   # not a checks-only output


def test_gate_config_refuses_silent_misconfig(tmp_path):
    """Usability review 4: FAIL_ON=holdd passed a BLOCK; RESULTS outside on.paths would never run the gate."""
    G = [sys.executable, str(ROOT / "scripts/gate_config_check.py")]; W = ".github/workflows/quantgate-gate.yml"
    env = lambda **kw: {**os.environ, **kw}
    run = lambda *a, **kw: subprocess.run([*G, *a], cwd=ROOT, capture_output=True, text=True, env=env(**kw)).returncode
    assert run(W) == 0 and run(W, FAIL_ON="holdd") == 2 and run(W, RESULTS="examples/my_results.csv") == 2
    assert [run("--apply", f, "4", "0") for f in ("block", "hold", "none", "holdd")] == [1, 1, 0, 2]
    assert [run("--apply", f, "3", "0") for f in ("block", "hold")] == [0, 1]


def test_rollout_walkthrough_end_to_end(tmp_path):
    """User test 2 (2026-10-26): from a JSONL rollout log to a decision, as in examples/rollout/README.md."""
    d = tmp_path / "rollout"; shutil.copytree(ROOT / "examples/rollout", d)
    run = lambda *a: subprocess.run([*CLI, *a], cwd=d, capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "NEBIUS_API_KEY"})
    r = run("tally", "trials.jsonl", "--group", "build", "--candidate", "int8", "--reference", "fp32", "--and", "released",
            "--placement", "place_px", "--engine", "build/int8.engine")
    assert r.returncode == 0 and "placement_ok=yes" in r.stderr; (d / "results.csv").write_text(r.stdout)
    assert r.stdout.splitlines()[1].startswith("int8,fp32,38,40,39,40,yes,")
    r = run("card", "--engine", "build/int8.engine", "--norm", "build/int8.norm_stats.npz", "--candidate", "int8",
            "--latency-from", "trials.jsonl", "--group", "build", "--out", "card.json")
    card = json.load(open(d / "card.json")); assert r.returncode == 0 and "over 40 trials" in card["latency_label"]   # the aborted trial is left out
    assert run("preflight", "--card", "card.json", "--checks-only", "--json", "pre.json").returncode == 0
    j = run("judge", "results.csv", "--preflight", "pre.json", "--json", "judge.json")
    assert j.returncode == 0 and "Deployment decision: HOLD" in j.stdout and "$ scripts" not in j.stdout
    assert json.load(open(d / "judge.json"))[0]["rule"] == "revised"
    p = run("preflight", "--card", "card.json", "--judge", "judge.json")
    lines = p.stdout.splitlines()
    assert p.returncode == 3 and lines[0].startswith("preflight") and "HOLD" in lines[0] and "not approve" in lines[0]   # decision first
    assert any(l.split()[0] == "HOLD" and "evidence" in l for l in lines[1:]) and not any(l.split()[0] == "pass" for l in lines[1:])


def test_card_refuses_what_it_cannot_measure(tmp_path):
    d = tmp_path / "b"; shutil.copytree(ROOT / "examples/rollout/build", d); (tmp_path / "x.npz").write_bytes(b"n")
    base = ["card", "--engine", str(d / "int8.engine"), "--candidate", "int8", "--out", str(tmp_path / "c.json")]
    assert q(*base, "--norm", str(tmp_path / "x.npz"), "--latency-ms", "90").returncode == 2           # not next to the engine
    assert q(*base, "--norm", str(d / "int8.norm_stats.npz")).returncode == 2                          # no latency given
    assert q(*base, "--norm", str(d / "int8.norm_stats.npz"), "--latency-ms", "-3").returncode == 2
    assert q(*base, "--norm", str(d / "int8.norm_stats.npz"), "--latency-from", str(ROOT / "examples/rollout/trials.jsonl"),
             "--group", "build", "--candidate", "nope").returncode == 2


def test_tally_placement_reproduces_the_study_reading():
    log = "artifacts/trials/fp16_unsealed/stress_fp16_F0_sealed.jsonl"; rj = "artifacts/fp16/rejudge/F0_consensus.json"
    r = q("tally", log, "--candidate", "VC-025", "--reference", "VC-000", "--success", rj + ":success_geom", "--and", "released",
          "--not", "human_contact", "--placement", rj + ":base_dist_px")
    assert r.returncode == 0 and r.stdout.splitlines()[1] == "VC-025,VC-000,19,20,10,10,yes"   # fp16_analysis.json E2: tolerance_compatible
    assert "degradation -0.6 px" in r.stderr


def test_rule_names():
    sys.path.insert(0, str(ROOT / "scripts")); import quantgate_judge as qj
    row = {"candidate": "A", "reference": "B", "cand_successes": "118", "cand_trials": "120", "ref_successes": "119", "ref_trials": "120"}
    assert qj.judge_row(row, "study")["success_criterion"].startswith("undecided (ceiling")
    assert qj.judge_row(row, "study")["success_criterion"] == qj.judge_row(row, "current")["success_criterion"]
    assert qj.judge_row(row)["rule"] == "revised" and qj.judge_row(row)["success_criterion"] == "met"


def test_external_log_conversion(tmp_path):
    """User test 3 (2026-10-26): nulls need a written rule, a task under two builds is a pair, 3 matches "3"."""
    d = tmp_path / "ext"; shutil.copytree(ROOT / "examples/external", d)
    run = lambda *a, py=False: subprocess.run([sys.executable, *a] if py else [*CLI, *a], cwd=d, capture_output=True, text=True)
    assert run("convert.py", py=True).returncode == 0
    base = ["tally", "--group", "config", "--candidate", "3", "--reference", "1"]
    r = run(*base[:1], "raw.jsonl", *base[1:], "--id", "attempt_id", "--success", "judge.success")
    assert r.returncode == 2 and "--missing fail or --missing drop" in r.stderr
    assert run(*base[:1], "raw.jsonl", *base[1:], "--id", "attempt_id", "--success", "judge.success", "--missing", "fail").stdout.splitlines()[1] == "3,1,19,40,8,40"
    assert run(*base[:1], "raw.jsonl", *base[1:], "--id", "attempt_id", "--success", "judge.success", "--missing", "drop").returncode == 0
    r = run(*base[:1], "trials.jsonl", *base[1:], "--id", "task_id"); assert r.returncode == 2 and "use --pair FIELD" in r.stderr
    r = run(*base[:1], "trials.jsonl", *base[1:], "--pair", "task_id", "--set", "mode=improvement")
    assert r.returncode == 0 and "40 pairs with both builds" in r.stderr and r.stdout.splitlines()[1].endswith(",improvement,paired")
    (d / "results.csv").write_text(r.stdout)
    j = run("judge", "results.csv", "--gate"); assert j.returncode == 3 and "PREVIEW ONLY" in j.stdout
    r = run(*base[:1], "trials.jsonl", "--group", "config", "--candidate", "three", "--reference", "1", "--pair", "task_id")
    assert r.returncode == 2 and "'3' (int)" in r.stderr
    (d / "mix.jsonl").write_text('{"trial_id": "x1", "config": 3, "success": true}\n{"trial_id": "x2", "config": "3", "success": true}\n')
    r = run(*base[:1], "mix.jsonl", *base[1:]); assert r.returncode == 2 and "both as int and str" in r.stderr


def test_paired_design_is_never_go():
    sys.path.insert(0, str(ROOT / "scripts")); import quantgate_judge as qj
    row = {"candidate": "A", "reference": "B", "cand_successes": "118", "cand_trials": "120", "ref_successes": "117", "ref_trials": "120",
           "placement_ok": "yes", "preflight_ok": "yes"}
    assert qj.judge_row(row)["decision"] == "GO"
    x = qj.judge_row({**row, "design": "paired"}); assert x["decision"] == "HOLD" and x["preview_only"] and "next_test" not in x
    import pytest
    with pytest.raises(qj.InputError, match="unknown design"): qj.judge_row({**row, "design": "pared"})


def test_planning_rate_is_not_called_observed():
    """User test 4 (2026-10-26): a 50% planning floor was labelled "pooled observed" when 26.3% was observed."""
    sys.path.insert(0, str(ROOT / "scripts")); import quantgate_judge as qj
    nt = qj.judge_row({"candidate": "GR00T", "reference": "OpenPI", "cand_successes": "6", "cand_trials": "27", "ref_successes": "9", "ref_trials": "30"})["next_test"]
    assert nt["observed_pooled_rate"] == round(15 / 57, 4) and nt["planning_rate"] == 0.5
    assert "26.3%" in nt["assumption"] and "floor" in nt["assumption"] and "pooled observed rate, " not in nt["assumption"]
    nt = qj.judge_row({"candidate": "A", "reference": "B", "cand_successes": "46", "cand_trials": "50", "ref_successes": "48", "ref_trials": "50"})["next_test"]
    assert nt["planning_rate"] == nt["observed_pooled_rate"] == 0.94 and "the pooled observed rate, 94.0%" in nt["assumption"]


def test_preview_rows_never_approve_downstream(tmp_path):
    """A preview row's finding must not reach preflight --judge as GO (found while adding collection=observational)."""
    d = tmp_path / "ex"; shutil.copytree(ROOT / "examples", d); card, res = d / "gate/candidate.json", d / "gate/results.csv"
    pre, jj = tmp_path / "pre.json", tmp_path / "judge.json"
    for col, val in (("collection", "observational"), ("design", "paired")):
        lines = open(ROOT / "examples/gate/results.csv").read().splitlines()
        res.write_text(f"{lines[0]},{col}\n{lines[1]},{val}\n")
        assert q("preflight", "--card", str(card), "--checks-only", "--json", str(pre)).returncode == 0
        j = q("judge", str(res), "--preflight", str(pre), "--json", str(jj), "--gate"); assert j.returncode == 3, j.stdout
        x = json.load(open(jj))[0]; assert x["preview_only"] and x["preview_finding"] == "GO" and x["finding"] == "INSUFFICIENT_EVIDENCE"
        p = q("preflight", "--card", str(card), "--judge", str(jj)); assert p.returncode == 3 and "preview only" in p.stdout


def test_csv_text_outcomes_conditions_and_audit(tmp_path):
    d = tmp_path / "ext"; shutil.copytree(ROOT / "examples/external", d)
    run = lambda *a: subprocess.run([*CLI, *a], cwd=d, capture_output=True, text=True)
    base = ["tally", "episodes.csv", "--id", "episode_id", "--group", "model", "--candidate", "gr00t", "--reference", "openpi"]
    r = run(*base, "--success", "eval_outcome"); assert r.returncode == 2 and "did you mean eval.outcome" in r.stderr
    r = run(*base, "--success", "eval.outcome"); assert r.returncode == 2 and "--map Success=true" in r.stderr
    maps = [x for v in ("Success=true", "Stalled=false", "Safety=false", "Timeout=false") for x in ("--map", v)]
    r = run(*base, "--success", "eval.outcome", *maps); assert r.returncode == 2 and "'Partial', which --map does not cover" in r.stderr
    r = run(*base, "--success", "eval.outcome", *maps, "--map", "Partial=false", "--where", "object=spoons", "--where", "start_objects=3",
            "--set", "collection=observational", "--audit", "audit.jsonl")
    assert r.returncode == 0 and r.stdout.splitlines()[1] == "gr00t,openpi,6,30,9,30,observational", (r.stdout, r.stderr)
    A = [json.loads(l) for l in open(d / "audit.jsonl")]
    assert len(A) == 160 and sum(a["status"] == "counted" for a in A) == 60
    assert any(a["status"] == "excluded" and a["reason"].startswith("condition not met: object is 'towels'") for a in A)
    assert all({"source", "line", "id", "build", "status", "reason"} <= set(a) for a in A)
