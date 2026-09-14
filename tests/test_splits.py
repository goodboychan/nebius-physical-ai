"""§3.2 분할과 `IG-1`/`IG-2` 가드."""
import pytest

from edgeqgate.splits import (IntegrityViolation, PURPOSE_ALLOWED, assert_allowed,
                              determine_splits, load_manifest, write_manifest)

SEED = "PREREG-SEED-TEST"


def test_split_sizes(manifest):
    assert {k: len(v) for k, v in manifest.assignment.items()} == {"train": 80, "val": 20, "audit": 20}


def test_split_is_deterministic_and_order_independent(episode_ids):
    """수집 순서(= 시간 드리프트)가 분할에 새어들면 안 된다."""
    a = determine_splits(episode_ids, seed=SEED)
    b = determine_splits(list(reversed(episode_ids)), seed=SEED)
    assert a.manifest_hash == b.manifest_hash


def test_different_seed_gives_different_split(episode_ids):
    a = determine_splits(episode_ids, seed=SEED)
    b = determine_splits(episode_ids, seed=SEED + "x")
    assert a.manifest_hash != b.manifest_hash


def test_splits_are_disjoint_and_complete(manifest, episode_ids):
    sets = [set(manifest.ids(s)) for s in ("train", "val", "audit")]
    assert set.union(*sets) == set(episode_ids)
    for i in range(3):
        for j in range(i + 1, 3):
            assert not sets[i] & sets[j]


def test_wrong_episode_count_raises(episode_ids):
    with pytest.raises(ValueError, match="분할 합계"):
        determine_splits(episode_ids[:100], seed=SEED)


def test_duplicate_ids_raise():
    with pytest.raises(ValueError, match="중복"):
        determine_splits(["a", "a"], seed=SEED, sizes={"train": 1, "val": 1, "audit": 0})


# ---- IG-1 / IG-2 ----

def test_audit_blocked_from_calibration(manifest):
    with pytest.raises(IntegrityViolation, match="IG-1"):
        assert_allowed(manifest, manifest.ids("audit")[:1], "calibration")


def test_audit_blocked_from_training(manifest):
    with pytest.raises(IntegrityViolation, match="IG-1"):
        assert_allowed(manifest, manifest.ids("train")[:2] + manifest.ids("audit")[:1],
                       "policy_training")


def test_val_blocked_from_calibration(manifest):
    """§3.2: val은 '캘리브레이션 사용 금지'."""
    with pytest.raises(IntegrityViolation):
        assert_allowed(manifest, manifest.ids("val")[:1], "calibration")


def test_val_allowed_for_training(manifest):
    """§3.2: val은 조기종료·하이퍼파라미터용으로 허용."""
    assert_allowed(manifest, manifest.ids("val")[:3], "policy_training")


def test_progress_regressor_is_train_only(manifest):
    """`IG-2`."""
    assert_allowed(manifest, manifest.ids("train")[:3], "progress_regressor")
    with pytest.raises(IntegrityViolation, match="IG-2"):
        assert_allowed(manifest, manifest.ids("val")[:1], "progress_regressor")


def test_reverse_contamination_blocked(manifest):
    """학습 데이터가 감사 버퍼로 새는 반대 방향도 막는다."""
    with pytest.raises(IntegrityViolation):
        assert_allowed(manifest, manifest.ids("train")[:1], "audit_scoring")


def test_unknown_purpose_raises(manifest):
    """새 용도는 사전등록 개정 없이 추가할 수 없다."""
    with pytest.raises(IntegrityViolation, match="등록되지 않은 용도"):
        assert_allowed(manifest, manifest.ids("train")[:1], "some_new_purpose")


def test_purpose_table_matches_spec():
    assert PURPOSE_ALLOWED["calibration"] == frozenset({"train"})
    assert PURPOSE_ALLOWED["progress_regressor"] == frozenset({"train"})
    assert PURPOSE_ALLOWED["audit_scoring"] == frozenset({"audit"})
    assert "audit" not in PURPOSE_ALLOWED["policy_training"]


def test_manifest_roundtrip(manifest, tmp_path):
    p = tmp_path / "split.yaml"
    h = write_manifest(manifest, p)
    assert load_manifest(p).manifest_hash == h
