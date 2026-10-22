import json, os, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_plans_cover_candidates_and_respect_the_ceiling_rule():
    os.chdir(ROOT); sys.path.insert(0, str(ROOT / "scripts")); import next_test_plan as ntp
    P = ntp.plans(json.load(open("artifacts/reports/d3_v3_verdicts.json")))
    assert set(P) == {"VC-025", "FT-FP16", "FT2-FP16", "INT8", "PC-B"}   # FT2-FP16 since amendment 9 (2026-10-22)
    for p in P.values():
        assert p["confirmed"] and p["open"] and p["evidence"] and p["next_test"]["rule"]
    # with the ceiling rule, two arms at about 96% are rarely decided, which is why the plans ask for a revised rule
    assert ntp.power(120, 0.96, 0.96, True) < 0.5 < ntp.power(120, 0.96, 0.96, False)
    assert "ceiling" in P["VC-025"]["next_test"]["rule"] and "ceiling" in P["FT-FP16"]["next_test"]["rule"]
