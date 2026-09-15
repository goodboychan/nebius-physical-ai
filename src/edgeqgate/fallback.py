"""`D6` 엣지 → 클라우드 폴백 판정과 청크 인계 (§6, `EX-3`).

§6은 `D6`을 "감사 신호 초과 시 엣지 → 클라우드 전환"으로 규정한다.
이 모듈은 **네트워크에 의존하지 않는 판정·인계 로직**만 담는다.

## 측정에서 나온 설계 제약

왕복 지연이 웜 상태에서도 **854ms**다 (attempt-008, 연산이 0인 컨테이너 기준이므로
GR00T를 올리면 더 늘어난다). ACT의 액션 청크는 100스텝 @ 30fps = **3.33초** 분량이다.

따라서 폴백은 **예측적**이어야 한다. 현재 청크가 소진된 뒤에 요청하면 왕복 시간만큼
제어가 빈다. 남은 청크가 왕복 지연 + 여유보다 짧아지는 시점에 미리 요청해야 한다.

이 모듈은 그 시점을 계산하고, 요청이 늦게 도착했을 때 무엇을 할지 정한다.

## 폴백이 실패로 집계된다는 점

`docs/success_criterion.md`: "클라우드 폴백(`D6`) 발동 후 안착 → **실패**로 집계한다.
주 엔드포인트 `EP-1`은 **엣지 정책 단독** 성공률이다."

따라서 폴백은 성공률을 구하는 장치가 아니라 **안전 장치**다. 이 모듈이 폴백을
남발하면 `EP-1`의 표본이 줄어든다. 발동 조건을 보수적으로 두는 이유다.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Literal

Source = Literal["edge", "cloud"]


@dataclass
class FallbackConfig:
    chunk_steps: int = 100            # ACT 액션 청크 길이
    control_hz: float = 30.0          # 제어 주기
    rtt_ms: float = 854.0             # 웜 왕복 지연 실측 (attempt-008)
    safety_margin_ms: float = 500.0   # 왕복 변동 + 추론 시간 여유
    audit_score_threshold: float | None = None   # None이면 감사 신호로는 발동하지 않는다
    require_supervisor_fallback: bool = True     # D4의 FALLBACK 판정도 요구할지

    @property
    def chunk_duration_ms(self) -> float:
        return 1000.0 * self.chunk_steps / self.control_hz

    @property
    def request_lead_ms(self) -> float:
        """청크 소진 전 이만큼 남았을 때 요청해야 제어가 비지 않는다."""
        return self.rtt_ms + self.safety_margin_ms

    def is_feasible(self) -> bool:
        """청크가 왕복+여유보다 길어야 예측적 폴백이 성립한다."""
        return self.chunk_duration_ms > self.request_lead_ms


@dataclass
class FallbackDecision:
    should_request: bool
    reason: str
    remaining_ms: float
    source: Source = "edge"


@dataclass
class FallbackState:
    """한 trial 동안의 폴백 상태와 `EX-3` 집계."""
    config: FallbackConfig
    requests: list[dict] = field(default_factory=list)
    arrivals: list[dict] = field(default_factory=list)
    late_arrivals: int = 0
    active_source: Source = "edge"

    def evaluate(self, remaining_chunk_ms: float, audit_score: float | None = None,
                 supervisor_says_fallback: bool = False) -> FallbackDecision:
        """지금 클라우드에 요청을 보내야 하는가."""
        c = self.config
        if self.active_source == "cloud":
            return FallbackDecision(False, "이미 클라우드 사용 중", remaining_chunk_ms, "cloud")

        trigger = False
        why = []
        if c.audit_score_threshold is not None and audit_score is not None \
                and audit_score > c.audit_score_threshold:
            trigger = True
            why.append(f"감사 점수 {audit_score:.5f} > 임계 {c.audit_score_threshold:.5f}")
        if supervisor_says_fallback:
            if c.require_supervisor_fallback or not why:
                trigger = True
                why.append("D4 감독자가 FALLBACK 판정")
        if c.require_supervisor_fallback and not supervisor_says_fallback:
            # 감사 신호만으로는 발동하지 않는다. 폴백은 성공률을 깎으므로 보수적으로 둔다.
            return FallbackDecision(False, "감독자 FALLBACK 판정 없음", remaining_chunk_ms)

        if not trigger:
            return FallbackDecision(False, "발동 조건 미충족", remaining_chunk_ms)

        if remaining_chunk_ms > c.request_lead_ms:
            return FallbackDecision(
                False, f"조건 충족이나 아직 이르다 (남은 {remaining_chunk_ms:.0f}ms > "
                       f"리드 {c.request_lead_ms:.0f}ms)", remaining_chunk_ms)

        return FallbackDecision(True, " / ".join(why), remaining_chunk_ms)

    def record_request(self, t_ms: float, remaining_ms: float, reason: str) -> None:
        self.requests.append({"t_ms": t_ms, "remaining_ms": remaining_ms, "reason": reason})

    def record_arrival(self, t_ms: float, request_t_ms: float, remaining_at_arrival_ms: float) -> bool:
        """응답 도착. 제어가 비었는지(늦었는지) 반환한다."""
        late = remaining_at_arrival_ms <= 0
        self.arrivals.append({"t_ms": t_ms, "rtt_ms": t_ms - request_t_ms,
                              "remaining_ms": remaining_at_arrival_ms, "late": late})
        if late:
            self.late_arrivals += 1
        else:
            self.active_source = "cloud"
        return late

    def ex3_summary(self) -> dict:
        rtts = sorted(a["rtt_ms"] for a in self.arrivals)
        return {
            "n_requests": len(self.requests),
            "n_arrivals": len(self.arrivals),
            "late_arrivals": self.late_arrivals,
            "active_source_at_end": self.active_source,
            "rtt_ms": {"median": rtts[len(rtts) // 2], "max": rtts[-1]} if rtts else None,
            "config": asdict(self.config),
            "feasible": self.config.is_feasible(),
        }
