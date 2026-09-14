"""`D3` 리포트의 날조 검증기 (§6).

LLM이 쓴 문서를 그대로 신뢰하지 않기 위한 장치다. **완전한 보증이 아니라 경고**다 —
증거의 어떤 값과 우연히 일치하는 날조는 통과한다. 그 한계를 테스트로 명시해둔다.
"""
import sys

import pytest

sys.path.insert(0, "scripts")
from d3_report_agent import _normalize_separators, verify_numbers

EV = {"latency": {"median_ms": 16.2246, "throughput_qps": 64.0675},
      "engine_bytes": 101866996, "n_layers": 236}


def test_clean_report_has_no_findings():
    r = "지연 중앙값은 16.2246 ms이고 처리량은 64.0675 qps다."
    assert verify_numbers(r, EV) == []


def test_fabricated_number_is_flagged():
    r = "지연 중앙값은 7.31 ms였다."
    assert "7.31" in verify_numbers(r, EV)


@pytest.mark.parametrize("sep", [",", " ", " ", " ", " "])
def test_thousands_separators_do_not_cause_false_positives(sep):
    """모델은 쉼표·보통공백·NBSP·NNBSP를 섞어 쓴다. 정규화하지 않으면
    101866996이 세 조각으로 쪼개져 오탐이 된다."""
    r = f"엔진 크기는 101{sep}866{sep}996 바이트다."
    assert verify_numbers(r, EV) == []


def test_identifier_digits_are_not_values():
    """p90_ms, VC-001, INT8의 숫자는 값이 아니라 이름이다."""
    assert verify_numbers("p90_ms 와 p99_ms 열, VC-001 셀, INT8 정밀도", EV) == []


def test_normalizer_joins_only_三digit_groups():
    assert _normalize_separators("101,866,996") == "101866996"
    assert _normalize_separators("1,23") == "1,23"          # 3자리 그룹이 아니면 건드리지 않는다
    assert _normalize_separators("16.2246 ms") == "16.2246 ms"


def test_small_integers_are_skipped():
    """셀 번호·섹션 번호는 대조 대상이 아니다."""
    assert verify_numbers("§4.1의 24개 셀과 3개 축", EV) == []


def test_derived_units_are_accepted():
    """바이트를 MB로 환산해 쓰는 것은 날조가 아니다."""
    assert verify_numbers("엔진은 약 101.9 MB다.", EV) == []


def test_known_limitation_coincidental_match_passes():
    """**한계**: 증거의 어떤 값과 허용오차 내에서 우연히 일치하는 날조는 통과한다.
    이 검증기는 보증이 아니라 경고다. 사람의 검토를 대체하지 않는다."""
    r = "성공률은 236 %였다."     # 236은 n_layers와 일치하므로 통과한다
    assert verify_numbers(r, EV) == []
