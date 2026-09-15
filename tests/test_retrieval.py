"""리트리벌 동결 (`D5` 기반, §12 재현성)."""
import json

import pytest

from edgeqgate.retrieval import (SnapshotMissing, drift, freeze, load_snapshot,
                                 write_snapshot)


def fake_search(results):
    return lambda q: list(results)


R1 = [{"url": "https://a", "title": "A", "content": "x", "score": 0.9},
      {"url": "https://b", "title": "B", "content": "y", "score": 0.5}]


def test_freeze_captures_queries_and_results():
    s = freeze(["q1", "q2"], fake_search(R1))
    assert s.queries == ["q1", "q2"]
    assert s.urls("q1") == ["https://a", "https://b"]
    assert len(s.result_digests["q1"]) == 2


def test_snapshot_hash_is_stable():
    a = freeze(["q"], fake_search(R1))
    b = freeze(["q"], fake_search(R1))
    assert a.snapshot_hash == b.snapshot_hash


def test_snapshot_hash_ignores_score_but_not_content():
    """점수는 재현성 대상이 아니지만 본문이 바뀌면 다른 스냅샷이다."""
    scored = [dict(r, score=0.1) for r in R1]
    assert freeze(["q"], fake_search(scored)).snapshot_hash == \
           freeze(["q"], fake_search(R1)).snapshot_hash
    changed = [dict(R1[0], content="달라짐"), R1[1]]
    assert freeze(["q"], fake_search(changed)).snapshot_hash != \
           freeze(["q"], fake_search(R1)).snapshot_hash


def test_roundtrip(tmp_path):
    s = freeze(["q"], fake_search(R1))
    p = tmp_path / "snap.json"
    h = write_snapshot(s, p)
    assert load_snapshot(p).snapshot_hash == h


def test_replay_without_snapshot_fails_loudly(tmp_path):
    """조용히 새 검색을 하면 동결의 의미가 사라진다."""
    with pytest.raises(SnapshotMissing, match="동결본이 없다"):
        load_snapshot(tmp_path / "missing.json")


def test_tampered_snapshot_detected(tmp_path):
    p = tmp_path / "snap.json"
    write_snapshot(freeze(["q"], fake_search(R1)), p)
    d = json.loads(p.read_text())
    d["results"]["q"][0]["url"] = "https://evil"
    d["result_digests"]["q"][0] = "0" * 64
    p.write_text(json.dumps(d))
    with pytest.raises(SnapshotMissing, match="변조"):
        load_snapshot(p)


def test_all_urls_dedupes_across_queries():
    s = freeze(["q1", "q2"], fake_search(R1))
    assert s.all_urls() == ["https://a", "https://b"]


# ---- 드리프트 ----

def test_drift_detects_identical():
    a = freeze(["q"], fake_search(R1))
    b = freeze(["q"], fake_search(R1))
    d = drift(a, b)["q"]
    assert d["same_set"] and d["same_order"] and d["jaccard"] == 1.0
    assert d["content_changed"] == []


def test_drift_detects_url_replacement():
    a = freeze(["q"], fake_search(R1))
    b = freeze(["q"], fake_search([R1[0], {"url": "https://c", "title": "C", "content": "z"}]))
    d = drift(a, b)["q"]
    assert not d["same_set"]
    assert d["only_a"] == ["https://b"] and d["only_b"] == ["https://c"]
    assert d["jaccard"] == pytest.approx(1 / 3)


def test_drift_detects_content_change_on_same_url():
    """URL이 그대로여도 본문이 바뀌면 근거가 바뀐 것이다."""
    a = freeze(["q"], fake_search(R1))
    b = freeze(["q"], fake_search([dict(R1[0], content="CHANGED"), R1[1]]))
    d = drift(a, b)["q"]
    assert d["same_set"] and d["content_changed"] == ["https://a"]


def test_drift_detects_reorder_only():
    a = freeze(["q"], fake_search(R1))
    b = freeze(["q"], fake_search(list(reversed(R1))))
    d = drift(a, b)["q"]
    assert d["same_set"] and not d["same_order"]
