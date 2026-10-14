import importlib.util, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("d3v3", ROOT / "scripts/d3_report_v3.py"); d3v3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(d3v3)


def test_selftest_catches_review5_sentences():
    res = d3v3.selftest()
    assert res["good_issues"] == [] and all(res["bad_caught"].values())


def test_precision_names_and_plain_go_allowed():
    assert d3v3.check_explanation("The FP16 and INT8 builds can go to another round of trials.") == []
    assert d3v3.check_explanation("FP16 is GO.") and d3v3.check_explanation("insufficient evidence")
