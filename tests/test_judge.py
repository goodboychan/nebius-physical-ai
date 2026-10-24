import csv, os, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import quantgate_judge as qj

def rows():
    return list(csv.DictReader(open(ROOT / "examples/my_results.csv", encoding="utf-8-sig")))

def test_the_study_fp16_row_reads_as_the_review_does():
    r = qj.judge(rows(), "current")[0]
    assert r["decision"] == "HOLD" and r["finding"] == "INSUFFICIENT_EVIDENCE" and "ceiling" in r["success_criterion"]
    assert r["interval97_5_pp"] == [-28.7, 27.3]             # the study's own FP16 analysis (fp16_analysis.json, E1)
    assert r["next_test"]["trials_per_arm"] == 120          # the plan's 120 per arm at an assumed 96%
    assert r["priority"].startswith("validate first")      # cheapest build that is not blocked

def test_go_needs_the_criterion_placement_and_preflight():
    cur, rev = qj.judge(rows(), "current"), qj.judge(rows(), "revised")
    assert cur[2]["decision"] == "HOLD"                     # ceiling clause keeps 118/120 vs 117/120 undecided
    assert rev[2]["decision"] == "GO" and rev[2]["success_criterion"] == "met"
    assert rev[3]["decision"] == "BLOCK"                    # same counts, failed preflight
    no_place = dict(rows()[2], placement_ok=""); assert qj.judge_row(no_place, "revised")["decision"] == "HOLD"

def test_improvement_is_never_a_go_and_degradation_blocks():
    assert qj.judge(rows(), "revised")[4]["decision"] == "HOLD"
    bad = dict(rows()[1], cand_successes="20", ref_successes="50"); x = qj.judge_row(bad, "revised")
    assert x["success_criterion"] == "degraded" and x["decision"] == "BLOCK"


def _row(**kw):
    return {"candidate": "FT", "reference": "OLD", "cand_successes": "12", "cand_trials": "12", "ref_successes": "3", "ref_trials": "12",
            "placement_ok": "yes", "preflight_ok": "yes", **kw}


def test_mode_typo_is_refused_not_tested_as_non_inferiority():
    """Usability review 2 (2026-10-24): mode=improvment used to fall through to non-inferiority and read GO."""
    import pytest
    assert qj.judge([_row(mode="improvement")], "revised")[0]["decision"] == "HOLD"
    assert qj.judge([_row(mode="")], "revised")[0]["mode"] == "non-inferiority"
    for bad in ({"mode": "improvment"}, {"mode": "superiority"}, {"placement_ok": "yse"}, {"cand_trials": "12.5"},
                {"cand_successes": "13"}, {"gpu_ms": "-1"}, {"assumed_rate": "1.2"}, {"reference": ""}):
        with pytest.raises(qj.InputError, match="row 1"): qj.judge([_row(**bad)], "revised")


def test_tolerance_reaches_the_sample_size():
    """Usability review 2: the next test used a fixed 10 pp whatever --tol said (120/arm at 5 pp has about 30% power)."""
    r = {"candidate": "FP16", "reference": "FP32", "cand_successes": "19", "cand_trials": "20", "ref_successes": "10", "ref_trials": "10", "assumed_rate": "0.96"}
    n = {t: qj.judge_row(r, "current", t)["next_test"]["trials_per_arm"] for t in (5, 10, 20)}
    assert n == {5: 400, 10: 120, 20: 50}
    assert qj.ntp.power(n[5], 0.96, 0.96, False, tol=5) >= 0.8 and qj.ntp.power(120, 0.96, 0.96, False, tol=5) < 0.5


def test_judge_cli_bad_input_exits_2(tmp_path):
    import subprocess, sys
    f = tmp_path / "r.csv"; f.write_text("candidate,reference,cand_successes,cand_trials,ref_successes,ref_trials,mode\nFT,OLD,12,12,3,12,improvment\n")
    r = subprocess.run([sys.executable, "scripts/quantgate.py", "judge", str(f)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2 and "unknown mode 'improvment'" in r.stderr and "Traceback" not in r.stderr


def _csv(tmp_path, text):
    f = tmp_path / "r.csv"; f.write_text(text); return f


def test_unknown_or_duplicate_column_is_refused(tmp_path):
    """Usability review 3 (2026-10-24): a column named `mod` was ignored, so the row fell back to non-inferiority and read GO."""
    import pytest
    B = "candidate,reference,cand_successes,cand_trials,ref_successes,ref_trials,placement_ok,preflight_ok"
    rows, lines = qj.read_csv(_csv(tmp_path, f"{B},mode\nFT,OLD,12,12,3,12,yes,yes,improvement\n"))
    assert qj.judge(rows, "revised", lines=lines)[0]["decision"] == "HOLD"
    for text, msg in ((f"{B},mod\nFT,OLD,12,12,3,12,yes,yes,improvement\n", "unknown column"),
                      (f"{B},mode,mode\nFT,OLD,12,12,3,12,yes,yes,improvement,\n", "duplicate"),
                      ("candidate,reference,cand_successes,cand_trials,ref_successes\nFT,OLD,12,12,3\n", "missing column"),
                      (f"{B}\nFT,OLD,12,12,3,12,yes,yes,extra\n", "line 2"), ("", "empty")):
        with pytest.raises(qj.InputError, match=msg): qj.read_csv(_csv(tmp_path, text))
    with pytest.raises(qj.InputError, match="unknown column"): qj.judge([{**_row(), "mod": "improvement"}], "revised")


def test_spaces_only_counts_as_empty(tmp_path):
    """Usability review 3: gpu_ms or assumed_rate of " " passed the check and then crashed with ValueError."""
    B = "candidate,reference,cand_successes,cand_trials,ref_successes,ref_trials,gpu_ms,assumed_rate,mode"
    rows, lines = qj.read_csv(_csv(tmp_path, f"{B}\n FP16 , FP32 , 19 ,20,10,10, , ,  \n"))
    x = qj.judge(rows, lines=lines)[0]
    assert x["candidate"] == "FP16" and x["mode"] == "non-inferiority" and "gpu_ms" not in x and x["decision"] == "HOLD"
    rows, _ = qj.read_csv(_csv(tmp_path, f"{B}\nFP16,FP32,19,20,10,10, 11.6 , 0.96 ,\n"))
    x = qj.judge(rows)[0]; assert x["gpu_ms"] == 11.6 and x["next_test"]["trials_per_arm"] == 120
