"""데이터 분할과 무결성 가드 (§3.2, §4.2, `IG-1`, `IG-2`).

분할은 커밋된 시드에서 SHA 키로 결정한다. 시드 문자열과 manifest 해시를 리포지토리에 기록하면
분할이 사후에 바뀌지 않았음을 누구나 재계산으로 확인할 수 있다.

가드의 설계 의도: `audit` 오염은 **조용히** 일어나고 결과를 통째로 무효화한다(§3.2).
따라서 "쓰지 말자"는 규약이 아니라 로더가 예외를 던지는 형태로 강제한다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Iterable, Sequence

import yaml

from .hashing import hash_obj, canonical_bytes

SPLIT_NAMES = ("train", "val", "audit")
DEFAULT_SIZES = {"train": 80, "val": 20, "audit": 20}

# 용도 -> 허용 분할. §3.2 접근 제한 표와 §4.2, `IG-2`를 그대로 옮긴 것이다.
# 여기 없는 용도는 예외 — 새 용도를 추가하려면 사전등록 개정이 필요하다.
PURPOSE_ALLOWED: dict[str, frozenset[str]] = {
    # 정책 학습: val은 조기종료/하이퍼파라미터 용도로 허용 (§3.2)
    "policy_training": frozenset({"train", "val"}),
    # 양자화 캘리브레이션: train만. §4.2 "캘리브레이션 데이터는 전부 train 분할에서만 추출"
    "calibration": frozenset({"train"}),
    # 진행도 회귀기 g: train만. `IG-2`
    "progress_regressor": frozenset({"train"}),
    # 감사 점수 산출: audit만. 반대 방향 오염(학습 데이터가 감사 버퍼에 섞임)도 막는다
    "audit_scoring": frozenset({"audit"}),
}


class IntegrityViolation(RuntimeError):
    """무결성 가드 위반. 이 예외는 잡아서 넘기면 안 된다 — 결과가 무효가 된다."""


@dataclass(frozen=True)
class SplitManifest:
    schema: str
    seed: str
    n_episodes: int
    sizes: dict[str, int]
    assignment: dict[str, list[str]]  # split -> episode ids (정렬됨)
    spec_section: str = "§3.2"
    notes: list[str] = field(default_factory=list)

    @property
    def manifest_hash(self) -> str:
        return hash_obj(asdict(self))

    def split_of(self, episode_id: str) -> str:
        for name, ids in self.assignment.items():
            if episode_id in ids:
                return name
        raise KeyError(f"분할에 없는 에피소드: {episode_id}")

    def ids(self, split: str) -> list[str]:
        if split not in self.assignment:
            raise KeyError(f"알 수 없는 분할: {split}")
        return list(self.assignment[split])


def _sha_key(seed: str, episode_id: str) -> str:
    """분할 결정용 SHA 키. 시드와 에피소드 id만으로 결정되며 순서에 의존하지 않는다."""
    return hashlib.sha256(canonical_bytes(["split-assignment/v1", seed, episode_id])).hexdigest()


def determine_splits(
    episode_ids: Sequence[str],
    seed: str,
    sizes: dict[str, int] | None = None,
) -> SplitManifest:
    """커밋된 시드에서 분할을 결정한다 (§3.2).

    SHA 키로 전체 순서를 매기고 앞에서부터 train/val/audit을 잘라낸다.
    에피소드 수집 순서(= 시간순 드리프트)가 분할에 새어들지 않도록 정렬 키는 해시만 쓴다.
    """
    sizes = dict(sizes or DEFAULT_SIZES)
    ids = list(episode_ids)
    if len(set(ids)) != len(ids):
        raise ValueError("에피소드 id에 중복이 있다")
    total = sum(sizes.values())
    if len(ids) != total:
        raise ValueError(
            f"에피소드 수({len(ids)})와 분할 합계({total})가 다르다. "
            f"수집이 부족하면 `K5`(< 80 에피소드) 판정을 먼저 확인하라."
        )
    ordered = sorted(ids, key=lambda e: _sha_key(seed, e))
    assignment: dict[str, list[str]] = {}
    cursor = 0
    for name in SPLIT_NAMES:
        n = sizes[name]
        assignment[name] = sorted(ordered[cursor : cursor + n])
        cursor += n
    return SplitManifest(
        schema="edgeqgate/split_manifest/v1",
        seed=seed,
        n_episodes=len(ids),
        sizes=sizes,
        assignment=assignment,
        notes=[
            "audit 분할은 학습·캘리브레이션 경로에서 IG-1로 차단된다",
            "이 manifest의 해시는 LOCK-1 시점에 커밋된다",
        ],
    )


def write_manifest(manifest: SplitManifest, path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 자동 생성 (edgeqgate.splits). 손으로 고치지 말 것.\n")
        f.write(f"# manifest_hash = {manifest.manifest_hash}\n")
        yaml.safe_dump(asdict(manifest), f, sort_keys=False, allow_unicode=True, width=100)
    return manifest.manifest_hash


def load_manifest(path: str | Path) -> SplitManifest:
    with open(path, encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    payload.pop("spec_section", None)
    return SplitManifest(
        schema=payload["schema"],
        seed=payload["seed"],
        n_episodes=payload["n_episodes"],
        sizes=payload["sizes"],
        assignment=payload["assignment"],
        notes=payload.get("notes", []),
    )


def assert_allowed(
    manifest: SplitManifest,
    episode_ids: Iterable[str],
    purpose: str,
) -> list[str]:
    """`IG-1`/`IG-2` 가드. 용도에 허용되지 않은 분할의 에피소드가 하나라도 있으면 예외.

    모든 데이터 로더는 배치를 내주기 **전에** 이 함수를 통과해야 한다.
    반환값은 검증된 id 목록이며, 호출부가 반환값을 쓰도록 강제해 가드 우회를 어렵게 한다.
    """
    if purpose not in PURPOSE_ALLOWED:
        raise IntegrityViolation(
            f"등록되지 않은 용도: {purpose!r}. 허용된 용도: {sorted(PURPOSE_ALLOWED)}. "
            f"새 용도는 사전등록 개정(docs/decision_log.md) 없이는 추가할 수 없다."
        )
    allowed = PURPOSE_ALLOWED[purpose]
    ids = list(episode_ids)
    offenders: dict[str, list[str]] = {}
    for eid in ids:
        split = manifest.split_of(eid)
        if split not in allowed:
            offenders.setdefault(split, []).append(eid)
    if offenders:
        detail = "; ".join(f"{s}: {len(v)}개 (예: {v[:3]})" for s, v in sorted(offenders.items()))
        guard = "IG-2" if purpose == "progress_regressor" else "IG-1"
        raise IntegrityViolation(
            f"[{guard}] 용도 {purpose!r}에 허용되지 않은 분할이 섞였다 — {detail}. "
            f"허용: {sorted(allowed)}. 이 오염이 통과하면 감사 결과 전체가 무효다(§3.2)."
        )
    return ids
