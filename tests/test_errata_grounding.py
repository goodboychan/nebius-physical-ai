import importlib.util, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("d5g", ROOT / "scripts/d5_errata_grounding.py"); d5g = importlib.util.module_from_spec(spec); spec.loader.exec_module(d5g)


def _load():
    import os
    os.chdir(ROOT); cfg = json.load(open("configs/errata_grounding_v1.json")); return cfg, d5g.results(cfg)


def test_selftest_catches_fabrications():
    cfg, R = _load(); res = d5g.selftest(cfg, R)
    assert res["good"] == [] and all(res["bad_caught"])


def test_reference_labels_cover_snapshot():
    cfg, R = _load()
    assert len(R) == 25 and set(cfg["reference_labels"]) == {r["id"] for r in R}
    assert all(l in cfg["labels"] and (f in cfg["facts"]) == (l in ("MATCHES", "CONTRASTS")) for l, f in cfg["reference_labels"].values())


def test_report_never_shows_model_explanations():
    """The rendered report may show only verbatim quotes (checked by R3) and our own fact text. The model's free-text
    explanation is not shown, because rule R4 checks only that its numbers occur somewhere (external review 4)."""
    cfg, R = _load()
    rows = [{"id": "R13", "title": "t", "url": "u", "accepted": True, "violations": [], "reference": ["MATCHES", "F1"],
             "answer": {"label": "MATCHES", "fact_id": "F1", "quote": "q", "explanation": "SECRET-EXPLANATION 48213 ms 7x"}}]
    md = d5g.render(cfg, rows, {"primary_recall": [1, 1], "extra_positive": [], "accepted": 1, "violations_by_rule": {}, "latency_s_median": 1})
    assert "SECRET-EXPLANATION" not in md and "48213" not in md


def test_r4_known_gaps_are_documented():
    """R4 is weak by design: these pass it. Kept as a test so the limitation stays visible (see the pre-registration §9)."""
    cfg, R = _load(); r = R[12]
    base = {"label": "MATCHES", "fact_id": "F1", "quote": "While my FP16/BF16 baseline achieves 580 QPS, the quantized INT8 version drops to 380 QPS.", "explanation": ""}
    for expl in ("FP16 reaches 380 QPS and INT8 580 QPS.", "INT8 takes 999ms.", "INT8 is 7x slower."):
        assert d5g.validate({**base, "explanation": expl}, r, cfg) == []
