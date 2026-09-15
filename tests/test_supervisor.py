"""`D4` 런타임 감독자 (§6, `EX-3`)."""
import pytest

from edgeqgate.supervisor import (Supervisor, SupervisorConfig, Verdict, parse_decision)


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t
    def advance(self, sec): self.t += sec


def make(responses, cfg=None, clock=None):
    it = iter(responses)
    return Supervisor(infer=lambda f: next(it), grab_frame=lambda: None,
                      config=cfg or SupervisorConfig(), clock=clock or Clock())


# ---- 파싱 ----

@pytest.mark.parametrize("text,expected", [
    ("CONTINUE", "CONTINUE"), ("abort", "ABORT"), ("  FALLBACK  ", "FALLBACK"),
    ("I think we should ABORT", "ABORT"), ("", "UNKNOWN"), ("뭐라고요?", "UNKNOWN"),
])
def test_parse_decision(text, expected):
    assert parse_decision(text) == expected


def test_unparseable_is_unknown_not_continue():
    """모르는 출력을 CONTINUE로 읽으면 감독자가 조용히 무력화된다."""
    assert parse_decision("어쩌구 저쩌구") == "UNKNOWN"


# ---- 개입 규칙 ----

def test_single_abort_does_not_intervene():
    """단발 오탐으로 trial을 죽이지 않는다."""
    s = make(["ABORT"])
    s.step()
    d, info = s.current()
    assert d == "CONTINUE" and "연속" in info["reason"]


def test_consecutive_aborts_intervene():
    s = make(["ABORT", "ABORT"])
    s.step(); s.step()
    d, _ = s.current()
    assert d == "ABORT"


def test_abort_streak_resets_on_continue():
    s = make(["ABORT", "CONTINUE", "ABORT"])
    s.step(); s.step(); s.step()
    d, info = s.current()
    assert d == "CONTINUE" and info["consecutive_abort"] == 1


def test_fallback_applies_immediately():
    """FALLBACK은 abort와 달리 되돌릴 수 있으므로 연속 요건을 걸지 않는다."""
    s = make(["FALLBACK"])
    s.step()
    assert s.current()[0] == "FALLBACK"


# ---- 신선도 ----

def test_stale_verdict_does_not_abort_by_default():
    """네트워크 지연으로 걸린 abort가 성공률을 오염시키면 안 된다.
    success_criterion.md가 D4 abort를 실패(unsafe)로 집계하기 때문이다."""
    c = Clock()
    s = make(["ABORT", "ABORT"], clock=c)
    s.step(); s.step()
    assert s.current()[0] == "ABORT"
    c.advance(2.0)                       # stale_after_ms=1500 초과
    d, info = s.current()
    assert d == "CONTINUE" and info["stale"] is True
    assert "개입하지 않음" in info["reason"]


def test_abort_on_stale_is_opt_in():
    c = Clock()
    s = make(["ABORT", "ABORT"], cfg=SupervisorConfig(abort_on_stale=True), clock=c)
    s.step(); s.step()
    c.advance(2.0)
    assert s.current()[0] == "ABORT"


def test_no_verdict_yet_continues():
    s = make([])
    d, info = s.current()
    assert d == "CONTINUE" and info["stale"] is True


# ---- 오류 처리 ----

def test_inference_error_becomes_unknown_and_does_not_intervene():
    def boom(_): raise RuntimeError("network down")
    s = Supervisor(infer=boom, grab_frame=lambda: None, clock=Clock())
    v = s.step()
    assert v.decision == "UNKNOWN" and "network down" in v.error
    assert s.current()[0] == "CONTINUE"


# ---- EX-3 ----

def test_ex3_summary_counts_decisions_and_latency():
    c = Clock()
    def infer(_):
        c.advance(0.4)                  # 400ms 지연을 흉내
        return next(it)
    it = iter(["CONTINUE", "ABORT", "CONTINUE"])
    s = Supervisor(infer=infer, grab_frame=lambda: None, clock=c)
    for _ in range(3): s.step()
    ex3 = s.ex3_summary()
    assert ex3["n_verdicts"] == 3
    assert ex3["decisions"]["CONTINUE"] == 2 and ex3["decisions"]["ABORT"] == 1
    assert ex3["latency_ms"]["median"] == pytest.approx(400, abs=1)
    assert ex3["n_errors"] == 0


def test_ex3_counts_singleton_aborts_as_false_positive_candidates():
    s = make(["ABORT", "CONTINUE", "ABORT", "ABORT"])
    for _ in range(4): s.step()
    assert s.ex3_summary()["singleton_aborts"] == 1


def test_ex3_records_config_for_provenance():
    """어떤 설정으로 얻은 통계인지 남지 않으면 EX-3를 해석할 수 없다."""
    s = make(["CONTINUE"]); s.step()
    cfg = s.ex3_summary()["config"]
    assert cfg["rate_hz"] == 2.0 and cfg["abort_on_stale"] is False
