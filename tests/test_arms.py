"""§7.1 arm 구성, `IG-7`, §12 축소 순서."""
import pytest

from edgeqgate.arms import (ARM_SPEC, REDUCTION_ORDER, TOTAL_TRIALS, apply_reduction,
                            build_arms, coverage_report)

SEED = "PREREG-SEED-TEST"


@pytest.fixture
def plan(rankings):
    return build_arms(rankings, seed=SEED)


def test_total_trials_matches_spec(plan):
    """기본 225 + ARM-CHEAP(다른 arm에 없는 cheap_A 상위 셀당 10, 최대 +30) (2026-10-07)."""
    assert TOTAL_TRIALS == 225
    assert plan.total_trials() == 225 + 10 * len(plan.arms["ARM-CHEAP"]) <= 255


def test_arm_sizes_match_spec(plan):
    for arm, spec in ARM_SPEC.items():
        if arm == "ARM-CHEAP":
            assert len(plan.arms[arm]) <= spec["n_cells"]
        else:
            assert len(plan.arms[arm]) == spec["n_cells"]
        assert plan.trials_per_cell[arm] == spec["trials_per_cell"]


def test_es2_cells_always_have_trials(plan, rankings):
    """ES-2 커버리지 보장: score_cheap_A 상위 3셀(INT8)은 반드시 어느 arm엔가 있다."""
    top3 = [c for c in rankings["score_cheap_A"] if c != "VC-025"][:3]
    assert set(top3) <= plan.cells_with_trials()


def test_fp16_cell_excluded_from_arms(plan):
    """VC-025(FP16)는 순위·arm 풀에서 빠진다 (2026-10-07, manual_actions #3)."""
    assert "VC-025" not in plan.cells_with_trials()


def test_audit_arm_is_score_align_top3(plan, rankings):
    assert plan.arms["ARM-AUDIT"] == [c for c in rankings["score_align"] if c != "VC-025"][:3]


def test_low_arm_is_score_align_bottom2_worst_first(plan, rankings):
    assert plan.arms["ARM-LOW"] == [c for c in rankings["score_align"] if c != "VC-025"][-2:][::-1]


def test_random_arm_excludes_audit_and_low(plan):
    """§7.1: 추출 풀은 ARM-AUDIT·ARM-LOW를 제외한 나머지."""
    r = set(plan.arms["ARM-RANDOM"])
    assert not r & set(plan.arms["ARM-AUDIT"])
    assert not r & set(plan.arms["ARM-LOW"])


def test_fp32_arm_is_vc000(plan):
    assert plan.arms["ARM-FP32"] == ["VC-000"]


def test_retest_cell_comes_from_audit_arm(plan):
    """§7.4 `ES-5`는 ARM-AUDIT 셀의 재측정이다."""
    assert plan.retest_cell in plan.arms["ARM-AUDIT"]


def test_ig7_draw_is_deterministic(rankings):
    """추출 후 교체·재추출 금지 — 같은 시드면 같은 셀이 나와야 한다."""
    a = build_arms(rankings, seed=SEED)
    b = build_arms(rankings, seed=SEED)
    assert a.plan_hash == b.plan_hash
    assert a.arms["ARM-RANDOM"] == b.arms["ARM-RANDOM"]


def test_ig7_draw_depends_on_frozen_rankings(rankings):
    """순위가 바뀌면 무작위 추출도 달라진다 — 순위 동결이 arm을 고정한다."""
    mutated = dict(rankings)
    mutated["score_align"] = list(reversed(mutated["score_align"]))
    assert build_arms(mutated, seed=SEED).plan_hash != build_arms(rankings, seed=SEED).plan_hash


def test_cells_are_plain_strings(plan):
    """numpy 문자열이 섞이면 yaml/json 직렬화가 깨진다."""
    for cells in plan.arms.values():
        for c in cells:
            assert type(c) is str


def test_rejects_incomplete_ranking(rankings):
    bad = dict(rankings)
    bad["score_align"] = bad["score_align"][:10]
    with pytest.raises(ValueError, match="순위 대상"):
        build_arms(bad, seed=SEED)


def test_ig9_enforced_before_arm_construction(rankings):
    partial = {k: v for k, v in rankings.items() if k != "score_mag"}
    with pytest.raises(ValueError, match="IG-9"):
        build_arms(partial, seed=SEED)


# ---- §7.3 커버리지 ----

def test_coverage_report_flags_uncomputable_endpoints(plan, rankings):
    """§7.1 arm 표는 score_align 기준으로만 셀을 고르므로, 다른 점수의 top3가
    trial을 못 받을 수 있다. 그 사실을 LOCK-2 시점에 드러내야 한다."""
    rep = coverage_report(plan, rankings)
    for ep in ("ES-1", "ES-2", "ES-3"):
        assert set(rep[ep]) >= {"score", "top_k", "covered", "missing", "computable"}
        assert rep[ep]["computable"] == (len(rep[ep]["missing"]) == 0)


def test_coverage_summary_counts_cells_with_trials(plan, rankings):
    rep = coverage_report(plan, rankings)
    assert rep["_summary"]["n_cells_with_trials"] == len(plan.cells_with_trials())
    assert "VC-000" in rep["_summary"]["cells_with_trials"]


# ---- §12 축소 순서 ----

def test_reduction_order_is_fixed_in_code():
    """결과를 본 뒤 축소 대상을 고르지 않기 위해 코드에 박는다."""
    assert [a for a, _, _ in REDUCTION_ORDER] == ["ARM-LOW", "ARM-AUDIT", "ARM-RANDOM"]


def test_reduction_never_touches_retest_first(plan):
    """§12: ARM-RETEST는 절대 먼저 자르지 않는다."""
    reduced = apply_reduction(plan, len(REDUCTION_ORDER))
    assert reduced.trials_per_cell["ARM-RETEST"] == plan.trials_per_cell["ARM-RETEST"]


def test_reduction_reduces_total(plan):
    assert apply_reduction(plan, 1).total_trials() < plan.total_trials()


def test_reduction_records_amendment_note(plan):
    assert any("축소" in n for n in apply_reduction(plan, 1).notes)
