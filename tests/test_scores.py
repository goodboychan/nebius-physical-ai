"""§5.1, §5.1b 감사 점수 5종과 `IG-9`."""
import numpy as np
import pytest

from edgeqgate.grid import audited_variants, by_code
from edgeqgate.scores import (SCORE_NAMES, action_error, aligned_components, bottom_k,
                              rank_cells, ranking_hash, score_align, score_cheap_A,
                              score_cheap_B, score_cheap_C, score_mag, top_k,
                              upper_tail_stat)


@pytest.fixture
def err_and_dirs():
    rng = np.random.default_rng(1)
    err = rng.normal(size=(2000, 4)) * 0.05
    u = rng.normal(size=(2000, 4))
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    return err, u


def test_five_scores_registered():
    assert len(SCORE_NAMES) == 5
    assert set(SCORE_NAMES) == {"score_align", "score_mag",
                                "score_cheap_A", "score_cheap_B", "score_cheap_C"}


def test_upper_tail_is_conditional_mean_of_tail():
    v = np.arange(100.0)
    # q=0.9 -> 상위 10% (90..99) 의 평균
    assert upper_tail_stat(v, 0.9) == pytest.approx(np.arange(90, 100).mean())


def test_upper_tail_handles_degenerate_constant():
    assert upper_tail_stat(np.full(50, 3.0)) == 3.0


def test_upper_tail_rejects_empty():
    with pytest.raises(ValueError):
        upper_tail_stat(np.array([]))


def test_aligned_component_never_exceeds_norm(err_and_dirs):
    """코시-슈바르츠: 단위벡터에 투영한 성분은 노름을 넘을 수 없다."""
    err, u = err_and_dirs
    assert np.all(aligned_components(err, u) <= np.linalg.norm(err, axis=1) + 1e-12)


def test_align_le_mag(err_and_dirs):
    err, u = err_and_dirs
    assert (score_align(err, u, cell="VC-001").value
            <= score_mag(err, cell="VC-001").value + 1e-12)


def test_zero_direction_gives_zero_alignment(err_and_dirs):
    """민감도 0인 상태는 정렬 성분이 0이어야 한다 (없는 신호를 만들지 않는다)."""
    err, _ = err_and_dirs
    z = np.zeros_like(err)
    assert score_align(err, z, cell="VC-001").value == 0.0


def test_direction_shape_mismatch_raises(err_and_dirs):
    err, u = err_and_dirs
    with pytest.raises(ValueError, match="모양"):
        score_align(err, u[:, :2], cell="VC-001")


def test_action_error_requires_2d():
    with pytest.raises(ValueError):
        action_error(np.zeros(4), np.zeros(4))


def test_larger_error_gives_larger_score():
    """규약: 점수는 '낮을수록 안전'."""
    rng = np.random.default_rng(3)
    small = rng.normal(size=(500, 3)) * 0.01
    assert score_mag(small, cell="a").value < score_mag(small * 10, cell="a").value


# ---- §5.1b 공짜 예측기 ----

def test_cheap_A_selects_exactly_the_max_calib_per_channel_cells():
    """`ES-2`가 3셀 대조로 성립하려면 상위 3셀이 정확히 이 조합이어야 한다."""
    vals = {v.code: score_cheap_A(v).value for v in audited_variants()}
    top = top_k(vals, 3)
    assert set(top) == {"VC-020", "VC-022", "VC-024"}
    for c in top:
        v = by_code(c)
        assert v.calib_size == 1024 and v.granularity == "per-channel"


def test_cheap_A_is_data_independent():
    """데이터를 보지 않으므로 부트스트랩에서 불변이다."""
    v = by_code("VC-020")
    assert score_cheap_A(v).value == score_cheap_A(v, replicate=17).value


def test_cheap_A_ranks_fp16_last():
    vals = {v.code: score_cheap_A(v).value for v in audited_variants()}
    assert rank_cells(vals)[-1] == "VC-025"


def test_cheap_B_uses_mean_squared_error():
    e = np.full((10, 2), 3.0)
    assert score_cheap_B(e, cell="x").value == pytest.approx(18.0)


def test_cheap_C_uses_median_latency():
    assert score_cheap_C(np.array([1.0, 2.0, 100.0]), cell="x").value == 2.0


# ---- 순위와 IG-9 ----

def test_rank_is_ascending_and_tie_broken_by_code():
    """동점 순서가 실행마다 달라지면 LOCK-2 동결 순위와 어긋난다."""
    r = rank_cells({"VC-003": 1.0, "VC-001": 1.0, "VC-002": 0.5})
    assert r == ["VC-002", "VC-001", "VC-003"]


def test_bottom_k_starts_from_worst():
    r = bottom_k({"a": 1.0, "b": 2.0, "c": 3.0}, 2)
    assert r == ["c", "b"]


def test_ig9_requires_all_five_scores(rankings):
    ranking_hash(rankings)                       # 5개 다 있으면 통과
    partial = {k: v for k, v in rankings.items() if k != "score_cheap_C"}
    with pytest.raises(ValueError, match="IG-9"):
        ranking_hash(partial)


def test_ranking_hash_is_order_sensitive(rankings):
    mutated = dict(rankings)
    mutated["score_align"] = list(reversed(mutated["score_align"]))
    assert ranking_hash(mutated) != ranking_hash(rankings)
