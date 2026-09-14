"""감사 상태 버퍼 (§3.3).

audit 20 에피소드 -> 2,000 states.
에피소드 내 시간축 균등 샘플 + 에피소드 간 균등 배분. 시드 고정.

시간축 균등을 쓰는 이유: 무작위 샘플은 긴 에피소드를 과대표집하고, 태스크 후반
(디텐트 안착 구간 — 오차에 가장 민감한 구간)이 셀마다 다른 비율로 들어간다.
균등 격자는 셀 간 비교에서 이 교란을 제거한다.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Mapping, Sequence

import numpy as np

from .hashing import hash_obj, seed_from
from .splits import SplitManifest, assert_allowed

N_STATES_DEFAULT = 2000


@dataclass(frozen=True)
class BufferIndex:
    """버퍼가 가리키는 (에피소드, 프레임) 좌표. 상태 값 자체는 담지 않는다.

    좌표만 해시해두면 원본 데이터셋이 바뀌었는지(프레임 재인코딩 등)와 무관하게
    '어느 상태를 썼는지'가 고정된다.
    """

    schema: str
    seed: str
    n_states: int
    per_episode: int
    episodes: list[str]
    frames: dict[str, list[int]]
    spec_section: str = "§3.3"

    @property
    def buffer_hash(self) -> str:
        return hash_obj(asdict(self))

    def pairs(self) -> list[tuple[str, int]]:
        """(episode_id, frame_idx) 순서 고정 목록. 감사 점수의 상태 순서가 이것이다."""
        return [(ep, int(fr)) for ep in self.episodes for fr in self.frames[ep]]


def build_buffer(
    manifest: SplitManifest,
    episode_lengths: Mapping[str, int],
    seed: str,
    n_states: int = N_STATES_DEFAULT,
) -> BufferIndex:
    """audit 분할에서 균등 격자로 상태 좌표를 뽑는다.

    episode_lengths: 에피소드 id -> 프레임 수.
    """
    episodes = manifest.ids("audit")
    # 반대 방향 오염 방지: 여기 들어온 id가 정말 audit인지 가드로 확인 (§3.2)
    assert_allowed(manifest, episodes, "audit_scoring")

    n_ep = len(episodes)
    if n_states % n_ep != 0:
        raise ValueError(
            f"상태 수 {n_states}가 에피소드 수 {n_ep}로 나누어떨어지지 않는다. "
            f"'에피소드 간 균등 배분'(§3.3)이 깨진다."
        )
    per_episode = n_states // n_ep

    frames: dict[str, list[int]] = {}
    for ep in episodes:
        length = int(episode_lengths[ep])
        if length < per_episode:
            raise ValueError(
                f"에피소드 {ep}의 길이 {length}가 에피소드당 표본 수 {per_episode}보다 짧다. "
                f"중복 표본 없이는 균등 격자를 만들 수 없다."
            )
        # 양 끝(첫/마지막 프레임)을 포함하는 균등 격자. 정수 인덱스로 반올림 후 중복 제거가
        # 필요 없도록 length >= per_episode를 위에서 강제했다.
        grid = np.linspace(0, length - 1, per_episode)
        idx = np.unique(np.rint(grid).astype(int))
        if idx.size != per_episode:  # 반올림 충돌 — 격자를 앞으로 밀어 해소
            idx = np.unique(np.floor(grid).astype(int))
            k = 0
            while idx.size != per_episode and k < length:
                missing = per_episode - idx.size
                extra = np.setdiff1d(np.arange(length), idx)[:missing]
                idx = np.unique(np.concatenate([idx, extra]))
                k += 1
        frames[ep] = sorted(int(i) for i in idx)

    return BufferIndex(
        schema="edgeqgate/audit_buffer/v1",
        seed=seed,
        n_states=n_states,
        per_episode=per_episode,
        episodes=list(episodes),
        frames=frames,
    )


def bootstrap_indices(n: int, replicate: int, seed: str) -> np.ndarray:
    """부트스트랩 리샘플 인덱스 (§5.3).

    replicate 번호와 커밋된 시드만으로 결정되므로, 어느 잡이 어느 머신에서 돌든
    같은 리샘플을 쓴다. 잡 재실행 시에도 동일 — 실패한 잡만 재시도해도 결과가 일관된다.
    """
    rng = np.random.default_rng(seed_from(seed, "bootstrap", replicate))
    return rng.integers(0, n, size=n)


def subsample_states(
    states: np.ndarray, buffer: BufferIndex, order: Sequence[tuple[str, int]] | None = None
) -> np.ndarray:
    """호출부 편의: 전체 상태 배열에서 버퍼 순서대로 뽑기 (테스트/오프라인용)."""
    pairs = buffer.pairs() if order is None else list(order)
    if states.shape[0] < len(pairs):
        raise ValueError("상태 배열이 버퍼보다 작다")
    return states[: len(pairs)]
