import json, os, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_preflight_demo_outcomes(tmp_path):
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "scripts")); import deploy_preflight as dp
    R = dp.demo("artifacts/reports")
    got = {c["case"]: c["outcome"] for c in R["cases"]}
    assert R["deadline_ms"] == 200
    assert got["nominal"] == "HOLD"
    assert got["evidence: fine-tuned policy, improvement at +3 cm"] == "HOLD"   # improvement is not approval
    assert all(v == "BLOCK" for k, v in got.items() if k not in ("nominal", "evidence: fine-tuned policy, improvement at +3 cm"))


def test_preflight_only_explicit_go_passes(tmp_path):
    """External review 6: every label other than GO used to fall through to OK."""
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "scripts")); import deploy_preflight as dp, hashlib, json as js
    e = tmp_path / "E.engine"; e.write_bytes(b"x"); (tmp_path / "E.norm_stats.npz").write_bytes(b"n")
    js.dump({"E": {"file": "E.norm_stats.npz", "sha256": hashlib.sha256(b"n").hexdigest()}}, open(tmp_path / "norm_manifest.json", "w"))
    card = lambda v: {"engine": str(e), "engine_sha256": hashlib.sha256(b"x").hexdigest(), "latency_ms": 50, "latency_label": "t",
                      "verdict": v, "next_action": "n"}
    want = {"GO": "OK", "NO-GO": "BLOCK", "FLAGGED": "BLOCK", "INSUFFICIENT_EVIDENCE": "HOLD", "IMPROVEMENT_DETECTED": "HOLD",
            "NOT_DETECTED": "HOLD", "CONDITIONAL": "BLOCK", "GOO": "BLOCK", "go": "BLOCK", "": "BLOCK"}
    assert {v: dp.preflight(card(v))[0] for v in want} == want
