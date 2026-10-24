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
