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
