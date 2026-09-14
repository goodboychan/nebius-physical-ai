"""§4.1 변형 그리드."""
import pytest

from edgeqgate.grid import (CALIB_SIZES, CALIB_COMPOSITIONS, GRANULARITIES,
                            audited_variants, by_code, canonical_variants,
                            grid_hash, grid_payload, load_grid)
from edgeqgate.hashing import hash_obj


def test_cell_count_matches_spec():
    """26셀 = VC-000 + 24 INT8 + VC-025 (§4.1)."""
    v = canonical_variants()
    assert len(v) == 26
    assert len([x for x in v if x.precision == "int8"]) == 24
    assert len(CALIB_SIZES) * len(CALIB_COMPOSITIONS) * len(GRANULARITIES) == 24


def test_codes_are_contiguous_and_unique():
    codes = [v.code for v in canonical_variants()]
    assert codes == sorted(codes)
    assert len(set(codes)) == 26
    assert codes[0] == "VC-000" and codes[-1] == "VC-025"


def test_every_factor_combination_appears_exactly_once():
    combos = [(v.calib_size, v.calib_composition, v.granularity)
              for v in canonical_variants() if v.precision == "int8"]
    assert len(set(combos)) == 24


def test_ordering_is_size_outer_granularity_inner():
    """중첩 순서가 바뀌면 셀 번호 ↔ 조합 대응이 깨진다 (§4.1)."""
    v = by_code("VC-001")
    assert (v.calib_size, v.calib_composition, v.granularity) == (16, "success-only", "per-tensor")
    assert by_code("VC-002").granularity == "per-channel"     # 가장 안쪽 축
    assert by_code("VC-003").calib_composition == "mixed"     # 중간 축
    assert by_code("VC-007").calib_size == 64                 # 바깥 축


def test_vc000_excluded_from_audit_ranking():
    """VC-000은 오차의 기준점이므로 점수가 정의되지 않는다 (§5.2의 25셀)."""
    assert by_code("VC-000").is_audited is False
    assert len(audited_variants()) == 25


def test_yaml_matches_canonical_generator():
    """손으로 고친 그리드는 로드 단계에서 거부된다."""
    assert load_grid() == canonical_variants()


def test_grid_hash_is_stable():
    assert grid_hash() == hash_obj(grid_payload())
    assert grid_hash() == grid_hash()


def test_unknown_code_raises():
    with pytest.raises(KeyError):
        by_code("VC-999")
