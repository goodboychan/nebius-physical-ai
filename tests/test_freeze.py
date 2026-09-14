"""§8 `LOCK-2` 동결과 실기 러너 차단."""
import json

import pytest

from edgeqgate.arms import build_arms, coverage_report
from edgeqgate.freeze import (LockViolation, create_lock2, load_lock2, lock2_status,
                              require_lock2, write_lock2)

SEED = "PREREG-SEED-TEST"


@pytest.fixture
def record(rankings, manifest, buffer):
    plan = build_arms(rankings, seed=SEED)
    return create_lock2(rankings, plan, manifest, buffer,
                        coverage=coverage_report(plan, rankings))


def test_runner_blocked_without_freeze(tmp_path):
    """§12: 점수 해시 파일이 없으면 러너는 실행을 거부한다."""
    with pytest.raises(LockViolation, match="동결 기록이 없다"):
        require_lock2(tmp_path / "missing.json")


def test_status_reports_unlocked_without_raising(tmp_path):
    s = lock2_status(tmp_path / "missing.json")
    assert s["locked"] is False and "reason" in s


def test_freeze_roundtrip_and_runner_passes(record, tmp_path):
    p = tmp_path / "lock2.json"
    h = write_lock2(record, p)
    assert load_lock2(p).record_hash == h
    assert require_lock2(p).ranking_hash == record.ranking_hash
    assert lock2_status(p)["locked"] is True


def test_freeze_is_not_overwritable(record, tmp_path):
    """재동결은 개정 사항이지 덮어쓰기가 아니다 (§13)."""
    p = tmp_path / "lock2.json"
    write_lock2(record, p)
    with pytest.raises(LockViolation, match="이미 존재"):
        write_lock2(record, p)


def test_tampered_record_is_detected(record, tmp_path):
    p = tmp_path / "lock2.json"
    write_lock2(record, p)
    payload = json.loads(p.read_text())
    payload["rankings"]["score_align"] = list(reversed(payload["rankings"]["score_align"]))
    p.write_text(json.dumps(payload))
    with pytest.raises(LockViolation, match="변조"):
        require_lock2(p)


def test_missing_score_blocks_runner(rankings, manifest, buffer, tmp_path):
    """`IG-9`: 5개 점수가 모두 동결되어야 한다."""
    partial = {k: v for k, v in rankings.items() if k != "score_cheap_C"}
    plan = build_arms(rankings, seed=SEED)
    with pytest.raises(ValueError, match="IG-9"):
        create_lock2(partial, plan, manifest, buffer)


def test_arm_plan_must_derive_from_frozen_rankings(rankings, manifest, buffer):
    """`IG-7`: 동결된 순위에서 나오지 않은 arm은 거부된다."""
    other = dict(rankings)
    other["score_align"] = list(reversed(other["score_align"]))
    plan_from_other = build_arms(other, seed=SEED)
    with pytest.raises(LockViolation, match="나오지 않았다"):
        create_lock2(rankings, plan_from_other, manifest, buffer)


def test_record_captures_provenance(record):
    """동결은 주장이 아니라 증거여야 한다."""
    assert record.grid_hash and record.split_manifest_hash and record.audit_buffer_hash
    assert record.frozen_at.endswith("+00:00")
    assert set(record.rankings) >= {"score_align", "score_mag"}


def test_grid_change_after_freeze_blocks_runner(record, tmp_path, monkeypatch):
    """동결 이후 그리드가 바뀌면 실기를 돌릴 수 없다."""
    p = tmp_path / "lock2.json"
    write_lock2(record, p)
    import edgeqgate.freeze as fz
    monkeypatch.setattr(fz, "grid_hash", lambda: "deadbeef")
    with pytest.raises(LockViolation, match="그리드가 동결 이후 바뀌었다"):
        require_lock2(p)
