import json, os, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_preflight_demo_outcomes(tmp_path):
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "scripts")); import deploy_preflight as dp
    R = dp.demo("artifacts/reports")
    got = {c["case"]: c["outcome"] for c in R["cases"]}
    assert R["deadline_ms"] == 200
    assert got["nominal"] == "HOLD"
    assert all(v == "BLOCK" for k, v in got.items() if k != "nominal")
