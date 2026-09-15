"""`D6` 폴백 판정과 청크 인계 (§6, `EX-3`)."""
import pytest

from edgeqgate.fallback import FallbackConfig, FallbackState


def st(**kw):
    return FallbackState(config=FallbackConfig(**kw))


# ---- 타이밍 성립 조건 ----

def test_default_chunk_is_long_enough_for_roundtrip():
    """ACT chunk 100 @ 30fps = 3.33초. 왕복+여유보다 길어야 예측적 폴백이 성립한다."""
    c = FallbackConfig()
    assert c.chunk_duration_ms == pytest.approx(3333, abs=1)
    assert c.request_lead_ms == pytest.approx(1354, abs=1)
    assert c.is_feasible()


def test_short_chunk_makes_fallback_infeasible():
    """청크가 짧으면 응답이 오기 전에 제어가 빈다."""
    c = FallbackConfig(chunk_steps=20)
    assert c.chunk_duration_ms < c.request_lead_ms
    assert not c.is_feasible()


def test_higher_rtt_raises_required_lead():
    assert FallbackConfig(rtt_ms=2000).request_lead_ms > FallbackConfig(rtt_ms=854).request_lead_ms


# ---- 발동 조건 ----

def test_no_trigger_without_supervisor_fallback():
    """감사 점수만으로는 발동하지 않는다. 폴백은 EP-1의 표본을 깎는다."""
    s = st(audit_score_threshold=0.01)
    d = s.evaluate(1000, audit_score=99.0, supervisor_says_fallback=False)
    assert not d.should_request and "감독자" in d.reason


def test_supervisor_fallback_triggers():
    s = st()
    d = s.evaluate(1000, supervisor_says_fallback=True)
    assert d.should_request and "FALLBACK" in d.reason


def test_too_early_does_not_request():
    """조건이 맞아도 청크가 많이 남았으면 아직 보내지 않는다."""
    s = st()
    d = s.evaluate(3000, supervisor_says_fallback=True)
    assert not d.should_request and "이르다" in d.reason


def test_requests_exactly_at_lead_boundary():
    s = st()
    lead = s.config.request_lead_ms
    assert not s.evaluate(lead + 1, supervisor_says_fallback=True).should_request
    assert s.evaluate(lead - 1, supervisor_says_fallback=True).should_request


def test_audit_threshold_can_trigger_when_supervisor_not_required():
    s = st(audit_score_threshold=0.01, require_supervisor_fallback=False)
    d = s.evaluate(1000, audit_score=0.05)
    assert d.should_request and "감사 점수" in d.reason


def test_already_on_cloud_does_not_rerequest():
    s = st()
    s.active_source = "cloud"
    d = s.evaluate(100, supervisor_says_fallback=True)
    assert not d.should_request and d.source == "cloud"


# ---- 인계와 EX-3 ----

def test_on_time_arrival_switches_source():
    s = st()
    s.record_request(0, 1000, "테스트")
    late = s.record_arrival(900, 0, remaining_at_arrival_ms=100)
    assert not late and s.active_source == "cloud"


def test_late_arrival_does_not_switch_and_is_counted():
    """응답이 청크 소진 후 도착하면 제어가 빈 것이다. 그 사실을 EX-3에 남긴다."""
    s = st()
    s.record_request(0, 500, "테스트")
    late = s.record_arrival(1500, 0, remaining_at_arrival_ms=-200)
    assert late and s.active_source == "edge"
    assert s.ex3_summary()["late_arrivals"] == 1


def test_ex3_summary_shape():
    s = st()
    s.record_request(0, 1000, "r")
    s.record_arrival(900, 0, 100)
    ex3 = s.ex3_summary()
    assert ex3["n_requests"] == 1 and ex3["n_arrivals"] == 1
    assert ex3["rtt_ms"]["median"] == 900
    assert ex3["active_source_at_end"] == "cloud"
    assert ex3["feasible"] is True
    assert "config" in ex3          # 어떤 설정의 통계인지 남아야 해석할 수 있다


def test_ex3_reports_infeasible_config():
    s = st(chunk_steps=20)
    assert s.ex3_summary()["feasible"] is False
