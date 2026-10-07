"""캘리브레이션 세트 선정 (§4.1의 `calib_size` x `calib_composition` 축).

`IG-1`/§4.2: 캘리브레이션 데이터는 **`train` 분할에서만** 추출한다.
선정은 커밋된 시드에서 결정되므로, 같은 (구성, 크기, 시드)면 언제 어디서 돌려도 같은 프레임이 뽑힌다.

2026-10-07 결정(decision_log): 시드에 **셀 코드를 넣지 않는다.** 같은 요인 조합이면 셀이 달라도 같은 프레임이다.
크기 축은 **중첩 표본**이다: 구성마다 후보를 한 번 섞고(시드 = 구성), 크기 N은 그 순서의 앞 N개다.
그래서 16 ⊂ 64 ⊂ 256 ⊂ 1024이고, 크기 축의 효과에 독립 추첨 잡음(attempt-023: 약 0.5%)이 섞이지 않는다.

구성 축의 정의 (§4.1):
  - `success-only`     : 성공한 시연의 프레임만
  - `early-phase-only` : 에피소드 전반 구간만 (2026-10-07 개정: 원래 `mixed`(실패·복구 포함)였으나
                         데모 120개가 모두 성공이라 `success-only`와 후보가 같아져 교체했다)
  - `late-phase-only`  : 에피소드 후반 구간만

attempt-010에서 확인한 사실: 캘리브레이션은 **활성화 양자화기에만** 작용한다.
가중치 스케일은 체크포인트가 고정하므로 이 축이 바꾸는 파라미터는 전체의 약 0.13%다.
그 사실이 축을 무의미하게 만들지는 않지만, 결과 해석 시 함께 보고해야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Mapping, Sequence

import numpy as np

from .hashing import hash_obj, seed_from
from .splits import SplitManifest, assert_allowed

COMPOSITIONS = ("success-only", "early-phase-only", "late-phase-only")
LATE_PHASE_FRACTION = 1 / 3   # 후반 구간의 정의. 사전등록 시점에 고정한다.
EARLY_PHASE_FRACTION = 1 / 3  # 전반 구간의 정의 (2026-10-07 개정과 함께 고정)


class CalibrationUnavailable(RuntimeError):
    """요청한 구성으로 충분한 프레임을 모을 수 없다."""


@dataclass(frozen=True)
class CalibrationSet:
    cell: str
    calib_size: int
    composition: str
    seed: str
    frames: list[tuple[str, int]]     # (episode_id, frame_index)
    requested: int
    actual: int
    approximated: bool = False        # 성공 라벨이 없어 위상으로 근사했는가

    @property
    def set_hash(self) -> str:
        return hash_obj(asdict(self))


def _eligible(
    episode_ids: Sequence[str],
    episode_lengths: Mapping[str, int],
    success: Mapping[str, bool] | None,
    composition: str,
) -> list[tuple[str, int]]:
    """구성별 후보 프레임 좌표."""
    if composition not in COMPOSITIONS:
        raise ValueError(f"알 수 없는 구성: {composition!r}. 허용: {COMPOSITIONS}")

    out: list[tuple[str, int]] = []
    for ep in episode_ids:
        length = int(episode_lengths[ep])
        if length < 1:
            continue
        if composition == "success-only":
            if success is not None and not success.get(ep, False):
                continue
            lo = 0
        elif composition == "early-phase-only":
            hi = max(1, int(length * EARLY_PHASE_FRACTION))
            out.extend((ep, i) for i in range(0, hi))
            continue
        else:                           # late-phase-only
            lo = int(length * (1 - LATE_PHASE_FRACTION))
        out.extend((ep, i) for i in range(lo, length))
    return out


def build_calibration_set(
    cell: str,
    calib_size: int,
    composition: str,
    manifest: SplitManifest,
    episode_lengths: Mapping[str, int],
    seed: str,
    success: Mapping[str, bool] | None = None,
) -> CalibrationSet:
    """한 셀의 캘리브레이션 프레임을 결정한다.

    success: 에피소드별 성공 여부. `None`이면 성공 라벨이 없다는 뜻이며,
             `success-only`가 전체 프레임과 같아지므로 `approximated=True`로 표시한다.
             공개 데이터셋 드라이런에서만 발생해야 한다 — 본 실험에서는 라벨이 있다.
    """
    train_eps = manifest.ids("train")
    # `IG-1`: 캘리브레이션은 train 분할에서만. audit이 섞이면 여기서 예외.
    assert_allowed(manifest, train_eps, "calibration")

    pool = _eligible(train_eps, episode_lengths, success, composition)
    if not pool:
        raise CalibrationUnavailable(
            f"{cell}: 구성 {composition!r}로 뽑을 수 있는 프레임이 없다"
        )
    if len(pool) < calib_size:
        raise CalibrationUnavailable(
            f"{cell}: 구성 {composition!r}의 후보가 {len(pool)}개로 요청 {calib_size}개보다 적다. "
            f"중복 표본으로 채우면 셀 간 비교가 깨지므로 실패로 처리한다."
        )

    # 셀 코드·크기는 시드에 넣지 않는다: 구성마다 한 번 섞은 순서의 앞 N개(중첩 표본)
    order = np.random.default_rng(seed_from(seed, "calibration", composition)).permutation(len(pool))
    frames = sorted(pool[i] for i in order[:calib_size])

    return CalibrationSet(
        cell=cell, calib_size=calib_size, composition=composition, seed=seed,
        frames=frames, requested=calib_size, actual=len(frames),
        approximated=(composition == "success-only" and success is None),
    )


def verify_no_audit_leak(cs: CalibrationSet, manifest: SplitManifest) -> None:
    """선정 결과에 audit 에피소드가 섞이지 않았는지 재확인한다.

    `build_calibration_set`이 이미 train만 넘기지만, 이 함수는 **결과물**을 검사한다.
    입력 검사와 출력 검사를 모두 두는 이유는 §3.2가 이 오염을 "전체 결과 무효"로
    규정하기 때문이다. 비용이 거의 없는 이중 확인이다.
    """
    audit = set(manifest.ids("audit"))
    bad = sorted({ep for ep, _ in cs.frames} & audit)
    if bad:
        from .splits import IntegrityViolation
        raise IntegrityViolation(
            f"[IG-1] 캘리브레이션 세트 {cs.cell}에 audit 에피소드가 있다: {bad}"
        )
