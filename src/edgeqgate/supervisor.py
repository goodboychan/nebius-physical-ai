"""`D4` 런타임 감독자의 판정 관리 (§6, `EX-3`).

§6은 `D4`를 "오버헤드 프레임 + 텔레메트리를 2Hz로 보고 abort / 폴백 / 계속 판정"으로
규정한다. 이 모듈은 **모델에 의존하지 않는 판정 관리 부분**만 담는다 — 속도 제한,
판정 신선도, 결정 로그. 실제 추론은 주입받는다. 그래서 네트워크 없이 테스트된다.

## 설계상 가장 중요한 결정: 판정이 낡았을 때 abort하지 않는다

측정된 사실(attempt-008, attempt-013): Token Factory 왕복이 중앙 381ms이고
그중 약 315ms가 네트워크 RTT다. 2Hz 예산 500ms에 대한 마진이 얇고,
경로가 나빠지면 그대로 넘긴다.

그런데 `docs/success_criterion.md`는 **`D4`의 abort를 실패(unsafe)로 집계**하고
성공률 계산에서 예외 처리하지 않는다. 따라서 네트워크 지연으로 abort가 걸리면
**정책과 무관한 실패가 성공률에 섞인다.** 그것은 측정하려는 대상이 아니다.

그래서 이 구현은 판정이 낡았을 때 `CONTINUE`를 유지하고 `stale` 플래그만 기록한다.
감독자가 "모르는 상태"에서 개입하지 않는다. 안전 관점에서는 보수적이지 않은 선택이며,
그 대가로 **성공률이 네트워크 상태에 오염되지 않는다.**

이 교환은 §6이 `D4`를 제품 구성요소로 규정하고 가설 검정 대상에서 뺐기 때문에 가능하다.
안전이 실제로 걸린 배포였다면 반대로 잡아야 한다.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, asdict, field
from typing import Callable, Literal

Decision = Literal["CONTINUE", "ABORT", "FALLBACK", "UNKNOWN"]
VALID: tuple[Decision, ...] = ("CONTINUE", "ABORT", "FALLBACK", "UNKNOWN")


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    frame_ts: float          # 프레임이 잡힌 시각
    verdict_ts: float        # 판정이 도착한 시각
    latency_ms: float
    raw: str = ""
    error: str | None = None

    @property
    def age_ms_at(self) -> Callable[[float], float]:
        return lambda now: (now - self.verdict_ts) * 1000.0


def parse_decision(text: str) -> Decision:
    """모델 출력에서 판정을 뽑는다. 모르면 UNKNOWN — 임의로 CONTINUE로 읽지 않는다."""
    t = (text or "").strip().upper()
    for d in ("ABORT", "FALLBACK", "CONTINUE"):
        if d in t:
            return d
    return "UNKNOWN"


@dataclass
class SupervisorConfig:
    rate_hz: float = 2.0
    stale_after_ms: float = 1500.0     # 이보다 오래된 판정은 신선하지 않다고 본다
    abort_on_stale: bool = False       # 위 docstring 참조. 기본값 False가 핵심이다
    consecutive_for_abort: int = 2     # 단발 오탐으로 trial을 죽이지 않는다


class Supervisor:
    """배경 스레드가 가능한 속도로 판정하고, 제어 루프는 최신 판정을 읽는다.

    `rate_hz`는 **판정 지연이 아니라 프레임 샘플링 주기**다. 판정은 항상
    1프레임 이상 과거 정보에 기반한다 — `EX-3`에 명시해야 하는 사실이다.
    """

    def __init__(self, infer: Callable[[object], str], grab_frame: Callable[[], object],
                 config: SupervisorConfig | None = None, clock: Callable[[], float] = time.time):
        self.infer = infer
        self.grab_frame = grab_frame
        self.cfg = config or SupervisorConfig()
        self.clock = clock
        self._latest: Verdict | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.log: list[dict] = []
        self._consecutive_abort = 0

    # ---- 한 번의 판정 주기 (테스트에서 직접 호출 가능) ----

    def step(self) -> Verdict:
        frame = self.grab_frame()
        t0 = self.clock()
        err = None
        try:
            raw = self.infer(frame)
        except Exception as e:                      # 추론 실패는 UNKNOWN이다
            raw, err = "", f"{type(e).__name__}: {e}"
        t1 = self.clock()
        v = Verdict(decision=parse_decision(raw) if not err else "UNKNOWN",
                    frame_ts=t0, verdict_ts=t1, latency_ms=(t1 - t0) * 1000.0,
                    raw=(raw or "")[:120], error=err)
        with self._lock:
            self._latest = v
            if v.decision == "ABORT":
                self._consecutive_abort += 1
            else:
                self._consecutive_abort = 0
            self.log.append(asdict(v) | {"consecutive_abort": self._consecutive_abort})
        return v

    # ---- 제어 루프가 읽는 지점 ----

    def current(self) -> tuple[Decision, dict]:
        """지금 시점에 제어 루프가 따라야 할 결정과 그 근거."""
        now = self.clock()
        with self._lock:
            v = self._latest
            consec = self._consecutive_abort
        if v is None:
            return "CONTINUE", {"reason": "판정 없음(시작 직후)", "stale": True, "age_ms": None}
        age = (now - v.verdict_ts) * 1000.0
        stale = age > self.cfg.stale_after_ms
        info = {"age_ms": round(age, 1), "stale": stale, "latency_ms": round(v.latency_ms, 1),
                "raw_decision": v.decision, "error": v.error, "consecutive_abort": consec}
        if stale and not self.cfg.abort_on_stale:
            # 네트워크 지연이 성공률을 오염시키지 않도록 개입하지 않는다.
            info["reason"] = "판정이 낡아 개입하지 않음"
            return "CONTINUE", info
        if v.decision == "ABORT" and consec < self.cfg.consecutive_for_abort:
            info["reason"] = f"ABORT {consec}회 — 연속 {self.cfg.consecutive_for_abort}회 필요"
            return "CONTINUE", info
        if v.decision == "UNKNOWN":
            info["reason"] = "판정 불명 — 개입하지 않음"
            return "CONTINUE", info
        info["reason"] = "판정 적용"
        return v.decision, info

    # ---- 배경 실행 ----

    def start(self) -> None:
        if self._thread:
            return
        self._stop.clear()
        period = 1.0 / self.cfg.rate_hz

        def loop():
            while not self._stop.is_set():
                t0 = self.clock()
                try:
                    self.step()
                except Exception:
                    pass
                # 다음 샘플까지 남은 시간만 쉰다. 판정이 예산을 넘으면 즉시 다음 프레임.
                rest = period - (self.clock() - t0)
                if rest > 0:
                    self._stop.wait(rest)

        self._thread = threading.Thread(target=loop, daemon=True, name="d4-supervisor")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    # ---- `EX-3` 기술 통계 ----

    def ex3_summary(self) -> dict:
        """§7.4 `EX-3`: 개입 횟수, 오탐 abort 횟수, 개입 지연."""
        n = len(self.log)
        if n == 0:
            return {"n_verdicts": 0}
        lat = sorted(e["latency_ms"] for e in self.log)
        counts: dict[str, int] = {}
        for e in self.log:
            counts[e["decision"]] = counts.get(e["decision"], 0) + 1
        # 연속 요건을 채우지 못하고 사라진 ABORT = 단발 오탐 후보
        singleton_aborts = sum(
            1 for i, e in enumerate(self.log)
            if e["decision"] == "ABORT" and e["consecutive_abort"] == 1
            and (i + 1 >= n or self.log[i + 1]["decision"] != "ABORT")
        )
        return {
            "n_verdicts": n,
            "decisions": counts,
            "n_errors": sum(1 for e in self.log if e["error"]),
            "latency_ms": {"median": lat[n // 2], "p90": lat[int(n * 0.9) - 1] if n > 1 else lat[0],
                           "max": lat[-1]},
            "singleton_aborts": singleton_aborts,
            "config": asdict(self.cfg),
        }
