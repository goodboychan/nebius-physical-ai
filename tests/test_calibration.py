"""§4.1 캘리브레이션 세트 선정과 `IG-1`."""
import pytest

from edgeqgate.calibration import (COMPOSITIONS, CalibrationUnavailable, LATE_PHASE_FRACTION,
                                   build_calibration_set, verify_no_audit_leak)
from edgeqgate.splits import IntegrityViolation

SEED = "PREREG-SEED-TEST"


@pytest.fixture
def lengths(episode_ids):
    return {e: 300 for e in episode_ids}


@pytest.fixture
def success(manifest):
    """train 에피소드의 절반만 성공으로 둔 가짜 라벨."""
    tr = manifest.ids("train")
    return {e: (i % 2 == 0) for i, e in enumerate(tr)}


def make(manifest, lengths, size=64, comp="mixed", success=None, cell="VC-001"):
    return build_calibration_set(cell, size, comp, manifest, lengths, SEED, success)


def test_returns_requested_size(manifest, lengths):
    cs = make(manifest, lengths, size=256)
    assert cs.actual == cs.requested == 256
    assert len(set(cs.frames)) == 256


def test_all_compositions_supported(manifest, lengths, success):
    for comp in COMPOSITIONS:
        cs = make(manifest, lengths, comp=comp, success=success)
        assert cs.composition == comp


def test_only_train_episodes_selected(manifest, lengths):
    cs = make(manifest, lengths, size=512)
    chosen = {ep for ep, _ in cs.frames}
    assert chosen <= set(manifest.ids("train"))
    assert not chosen & set(manifest.ids("audit"))
    assert not chosen & set(manifest.ids("val"))


def test_leak_verifier_passes_on_clean_set(manifest, lengths):
    verify_no_audit_leak(make(manifest, lengths), manifest)


def test_leak_verifier_catches_injected_audit(manifest, lengths):
    cs = make(manifest, lengths)
    bad = cs.__class__(**{**cs.__dict__,
                          "frames": cs.frames + [(manifest.ids("audit")[0], 0)]})
    with pytest.raises(IntegrityViolation, match="IG-1"):
        verify_no_audit_leak(bad, manifest)


def test_late_phase_only_restricts_to_tail(manifest, lengths):
    cs = make(manifest, lengths, comp="late-phase-only", size=256)
    cutoff = int(300 * (1 - LATE_PHASE_FRACTION))
    assert all(fi >= cutoff for _, fi in cs.frames)


def test_success_only_excludes_failures(manifest, lengths, success):
    cs = make(manifest, lengths, comp="success-only", success=success, size=256)
    assert all(success[ep] for ep, _ in cs.frames)


def test_mixed_includes_failures(manifest, lengths, success):
    cs = make(manifest, lengths, comp="mixed", success=success, size=2000)
    assert any(not success[ep] for ep, _ in cs.frames)


def test_success_only_without_labels_is_flagged(manifest, lengths):
    """라벨이 없으면 success-only가 mixed와 같아진다 — 조용히 넘어가면 안 된다."""
    cs = make(manifest, lengths, comp="success-only", success=None)
    assert cs.approximated is True
    assert make(manifest, lengths, comp="mixed").approximated is False


def test_selection_is_deterministic(manifest, lengths):
    a = make(manifest, lengths)
    b = make(manifest, lengths)
    assert a.set_hash == b.set_hash and a.frames == b.frames


def test_different_cells_get_different_sets(manifest, lengths):
    a = make(manifest, lengths, cell="VC-001")
    b = make(manifest, lengths, cell="VC-003")
    assert a.frames != b.frames


def test_same_factors_same_frames_regardless_of_cell_code(manifest, lengths):
    """시드가 (셀, 구성, 크기)에 걸리므로 셀이 다르면 세트도 다르다 —
    이것은 의도된 동작이며, 셀 간 차이가 요인 조합에서만 오도록 하려면
    오히려 같아야 한다는 주장도 가능하다. 현재 설계를 테스트로 고정해둔다."""
    a = make(manifest, lengths, cell="VC-001", comp="mixed", size=64)
    b = make(manifest, lengths, cell="VC-002", comp="mixed", size=64)
    assert a.frames != b.frames


def test_oversized_request_fails_loudly(manifest, lengths):
    """중복 표본으로 채우면 셀 간 비교가 깨진다."""
    small = {e: 2 for e in lengths}
    with pytest.raises(CalibrationUnavailable, match="적다"):
        build_calibration_set("VC-001", 1024, "mixed", manifest, small, SEED)


def test_unknown_composition_rejected(manifest, lengths):
    with pytest.raises(ValueError, match="알 수 없는 구성"):
        make(manifest, lengths, comp="nonsense")
