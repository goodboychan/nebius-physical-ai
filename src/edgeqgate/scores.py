"""감사 점수 5종 (§5.1, §5.1b) — `IG-9`에 따라 **동시에** 산출·동결한다.

| 점수 | 종류 | 역할 |
|---|---|---|
| `score_align`  | 정렬 기반   | 주장군 (§5.1) |
| `score_mag`    | 크기 기반   | 비교군 (§5.1) |
| `score_cheap_A`| 고정 휴리스틱 | 실무 기본 선택 (§5.1b) |
| `score_cheap_B`| 오픈루프 MSE | 대부분의 팀이 실제로 보는 지표 (§5.1b) |
| `score_cheap_C`| 추론 지연    | 무의미 예측기 / sanity check (§5.1b) |

규약: **모든 점수는 "낮을수록 안전하다고 예측"** 방향으로 정규화한다.
순위는 오름차순이며 1위가 가장 안전한 셀이다. 이 규약을 어기면 `score_cheap_C`처럼
의미가 자명하지 않은 축에서 부호 실수가 조용히 결론을 뒤집는다.

대표 통계량은 **상위 10% 조건부 평균(CVaR@90)**으로 고정한다. 근거는 docs/decision_log.md.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field

import numpy as np

from .grid import Variant, CALIB_SIZES
from .hashing import hash_obj

TAIL_Q_DEFAULT = 0.90
SCORE_NAMES = ("score_align", "score_mag", "score_cheap_A", "score_cheap_B", "score_cheap_C")


def upper_tail_stat(values: np.ndarray, q: float = TAIL_Q_DEFAULT) -> float:
    """상위 (1-q) 꼬리의 조건부 평균 (CVaR@q).

    단일 분위수 대신 꼬리 평균을 쓰는 이유: 부트스트랩 리샘플에서 단일 분위수는
    소수의 상태가 들락거리면서 크게 튄다. 클로즈드루프 실패가 사는 곳은 꼬리 전체이지
    한 점이 아니다.
    """
    v = np.asarray(values, dtype=float).reshape(-1)
    if v.size == 0:
        raise ValueError("빈 배열의 꼬리 통계는 정의되지 않는다")
    thr = np.quantile(v, q)
    tail = v[v >= thr]
    if tail.size == 0:  # 전부 동일값인 축퇴 케이스
        return float(v.max())
    return float(tail.mean())


def diagnostics(values: np.ndarray) -> dict[str, float]:
    """진단용 분포 요약. 순위 산출에는 **쓰지 않는다** (`EX-4` 양봉 구조 점검용)."""
    v = np.asarray(values, dtype=float).reshape(-1)
    qs = np.quantile(v, [0.5, 0.9, 0.95, 0.99])
    return {
        "mean": float(v.mean()),
        "q50": float(qs[0]),
        "q90": float(qs[1]),
        "q95": float(qs[2]),
        "q99": float(qs[3]),
        "max": float(v.max()),
        "n": int(v.size),
    }


@dataclass(frozen=True)
class ScoreResult:
    """한 셀 × 한 점수의 산출 결과."""

    cell: str
    score_name: str
    value: float
    diag: dict[str, float] = field(default_factory=dict)
    replicate: int | None = None   # None = 전체 표본 (포인트 추정)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# §5.1 — 상태 수준 점수
# --------------------------------------------------------------------------

def action_error(action_int8: np.ndarray, action_ref: np.ndarray) -> np.ndarray:
    """행동 오차 벡터 (N, A). 레퍼런스는 §4.1 `VC-000` 계열 FP32 정책의 행동."""
    e = np.asarray(action_int8, dtype=float) - np.asarray(action_ref, dtype=float)
    if e.ndim != 2:
        raise ValueError(f"행동 오차는 (N, A) 2차원이어야 한다: {e.shape}")
    return e


def score_mag(
    err: np.ndarray, *, cell: str, q: float = TAIL_Q_DEFAULT, replicate: int | None = None
) -> ScoreResult:
    """`score_mag` — 행동 차이 L2 노름의 상위 분위수 통계 (§5.1)."""
    per_state = np.linalg.norm(err, axis=1)
    return ScoreResult(cell, "score_mag", upper_tail_stat(per_state, q),
                       diagnostics(per_state), replicate)


def score_align(
    err: np.ndarray,
    directions: np.ndarray,
    *,
    cell: str,
    q: float = TAIL_Q_DEFAULT,
    replicate: int | None = None,
) -> ScoreResult:
    """`score_align` — 오차를 태스크 민감 방향에 투영한 성분의 크기 통계 (§5.1).

    directions: (N, A) 단위 민감 방향 u. progress.sensitivity_directions()의 출력.
    민감도가 수치적으로 0인 상태는 u = 0이므로 정렬 성분도 0이 된다 — 의도된 동작이다.
    """
    u = np.asarray(directions, dtype=float)
    if u.shape != err.shape:
        raise ValueError(f"방향 배열 {u.shape}과 오차 배열 {err.shape}의 모양이 다르다")
    comp = np.abs(np.einsum("na,na->n", err, u))
    return ScoreResult(cell, "score_align", upper_tail_stat(comp, q),
                       diagnostics(comp), replicate)


def aligned_components(err: np.ndarray, directions: np.ndarray) -> np.ndarray:
    """상태별 정렬 성분 (N,). Jobs 산출물의 '상태별 정렬 성분 벡터'(§5.3)."""
    return np.abs(np.einsum("na,na->n", err, np.asarray(directions, dtype=float)))


# --------------------------------------------------------------------------
# §5.1b — 공짜 예측기
# --------------------------------------------------------------------------

def score_cheap_A(variant: Variant, *, replicate: int | None = None) -> ScoreResult:
    """고정 휴리스틱: "`calib_size` 최대 + per-channel"이 가장 안전하다는 실무 기본값.

    데이터를 전혀 보지 않는다. 셀의 요인 조합만으로 결정되므로 부트스트랩에서 불변이다.

    순위 규약(낮을수록 안전)에 맞추기 위해 다음 우선순위로 값을 만든다:
      1순위: 선호 조합(최대 calib_size AND per-channel)이면 0, 아니면 1
      2순위: calib_size가 클수록 낮은 값
      3순위: per-channel이 per-tensor보다 낮은 값
    INT8이 아닌 셀(FP16 `VC-025`)은 이 휴리스틱의 적용 대상이 아니므로 최하위로 보낸다.
    """
    max_size = max(CALIB_SIZES)
    if variant.precision != "int8":
        value = 9.0
    else:
        preferred = (variant.calib_size == max_size) and (variant.granularity == "per-channel")
        size_rank = 1.0 - (CALIB_SIZES.index(variant.calib_size) / (len(CALIB_SIZES) - 1))
        gran_rank = 0.0 if variant.granularity == "per-channel" else 1.0
        value = (0.0 if preferred else 4.0) + size_rank + 0.1 * gran_rank
    return ScoreResult(variant.code, "score_cheap_A", float(value), {}, replicate)


def score_cheap_B(
    err_train_states: np.ndarray, *, cell: str, replicate: int | None = None
) -> ScoreResult:
    """오픈루프 action MSE — **`train` 상태에서**. 홀드아웃이 아니다 (§5.1b).

    의도적으로 실무의 나쁜 습관을 그대로 재현한다: 대부분의 팀은 학습 데이터 위에서
    오픈루프 오차를 보고 양자화 품질을 판단한다. 이 비교군이 이기면 감사 파이프라인은
    불필요하다는 것이 결론이다(§5.1b).
    """
    e = np.asarray(err_train_states, dtype=float)
    per_state = np.sum(e**2, axis=1)
    return ScoreResult(cell, "score_cheap_B", float(per_state.mean()),
                       diagnostics(per_state), replicate)


def score_cheap_C(
    latencies_ms: np.ndarray, *, cell: str, replicate: int | None = None
) -> ScoreResult:
    """Jetson 추론 지연 — 태스크와 무관한 축. 무의미 예측기 (§5.1b).

    이 점수가 `score_align`을 이기면 실험 설계에 결함이 있다는 신호다.
    지연은 `EX-2`로도 별도 보고되지만, 여기서는 **예측기로서** 순위를 만든다.
    """
    v = np.asarray(latencies_ms, dtype=float).reshape(-1)
    return ScoreResult(cell, "score_cheap_C", float(np.median(v)), diagnostics(v), replicate)


# --------------------------------------------------------------------------
# 순위
# --------------------------------------------------------------------------

def rank_cells(results: dict[str, float]) -> list[str]:
    """점수 dict(cell -> value)에서 오름차순 순위. 동점은 셀 코드 사전순으로 결정적 처리.

    동점 처리를 셀 코드로 고정하는 이유: 동점이 생겼을 때 순서가 실행마다 달라지면
    `LOCK-2`에서 동결한 순위와 분석 시점의 순위가 달라질 수 있다.
    """
    return [c for c, _ in sorted(results.items(), key=lambda kv: (kv[1], kv[0]))]


def top_k(results: dict[str, float], k: int) -> list[str]:
    return rank_cells(results)[:k]


def bottom_k(results: dict[str, float], k: int) -> list[str]:
    return rank_cells(results)[-k:][::-1]   # 최하위부터


def ranking_hash(rankings: dict[str, list[str]]) -> str:
    """5개 점수의 순위를 한 덩어리로 해시 (`IG-9`)."""
    missing = set(SCORE_NAMES) - set(rankings)
    if missing:
        raise ValueError(
            f"[IG-9] 점수 {sorted(missing)}의 순위가 빠졌다. 5개 점수는 동시에 동결해야 한다. "
            f"일부만 동결하면 실기 결과를 본 뒤 나머지 점수 정의를 조정하는 경로가 열린다."
        )
    return hash_obj({name: rankings[name] for name in sorted(rankings)})
