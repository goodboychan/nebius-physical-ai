"""순서 잠금 (§8 `LOCK`) 과 그 강제.

핵심은 `LOCK-2`다: **감사 점수 전량 산출·동결·해시 커밋 -> 이후 최초 실기 trial 실행.**
§12가 이를 "CI 체크로 강제 (점수 해시 파일 없으면 러너 실행 거부)"하라고 지정한다.

설계 의도: 사전등록의 신뢰성은 "순서를 지켰다"는 **주장**이 아니라 검증 가능한
**증거**에서 나온다. 동결 기록은 그 증거이며, 다음을 담는다.

  - 5개 점수의 순위 전체와 그 결합 해시 (`IG-9`)
  - arm 구성과 그 해시 (`IG-7`)
  - 그리드 해시, 분할 manifest 해시, 감사 버퍼 해시
  - 동결 시점과 그 시점의 git 커밋

실기 러너는 `require_lock2()`를 통과하지 못하면 실행을 거부한다.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path

from .arms import ArmPlan
from .audit_buffer import BufferIndex
from .grid import grid_hash
from .hashing import hash_obj
from .scores import SCORE_NAMES, ranking_hash
from .splits import SplitManifest

FREEZE_PATH = Path("artifacts/freeze/lock2.json")


class LockViolation(RuntimeError):
    """순서 잠금 위반. 이 예외를 무시하면 사전등록의 의미가 사라진다."""


def _git_commit() -> str | None:
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


def _git_dirty() -> bool | None:
    try:
        p = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=10)
        return bool(p.stdout.strip()) if p.returncode == 0 else None
    except Exception:
        return None


@dataclass(frozen=True)
class Lock2Record:
    schema: str
    frozen_at: str
    git_commit: str | None
    git_dirty: bool | None
    grid_hash: str
    split_manifest_hash: str
    audit_buffer_hash: str
    rankings: dict[str, list[str]]
    ranking_hash: str
    arm_plan: dict
    arm_plan_hash: str
    coverage: dict = field(default_factory=dict)
    spec_section: str = "§8 LOCK-2"
    notes: list[str] = field(default_factory=list)

    @property
    def record_hash(self) -> str:
        return hash_obj(asdict(self))


def create_lock2(
    rankings: dict[str, list[str]],
    plan: ArmPlan,
    manifest: SplitManifest,
    buffer: BufferIndex,
    coverage: dict | None = None,
    notes: list[str] | None = None,
) -> Lock2Record:
    """동결 기록을 만든다. 5개 점수가 모두 있어야 한다 (`IG-9`)."""
    rh = ranking_hash(rankings)   # IG-9 검사가 여기서 먼저 돈다
    if plan.ranking_hash != rh:
        raise LockViolation(
            f"arm 구성이 이 순위에서 나오지 않았다.\n"
            f"  plan.ranking_hash = {plan.ranking_hash}\n"
            f"  전달된 순위 해시  = {rh}\n"
            f"  -> arm을 다시 만들지 말고, 어느 쪽이 맞는지 먼저 확인하라."
        )
    return Lock2Record(
        schema="edgeqgate/lock2/v1",
        frozen_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        git_commit=_git_commit(),
        git_dirty=_git_dirty(),
        grid_hash=grid_hash(),
        split_manifest_hash=manifest.manifest_hash,
        audit_buffer_hash=buffer.buffer_hash,
        rankings={k: list(v) for k, v in rankings.items()},
        ranking_hash=rh,
        arm_plan=asdict(plan),
        arm_plan_hash=plan.plan_hash,
        coverage=coverage or {},
        notes=notes or [],
    )


def write_lock2(record: Lock2Record, path: Path = FREEZE_PATH) -> str:
    """동결 기록을 쓴다. **이미 있으면 덮어쓰지 않는다** — 재동결은 개정 사항이다."""
    path = Path(path)
    if path.exists():
        raise LockViolation(
            f"{path}가 이미 존재한다. LOCK-2는 한 번만 일어난다.\n"
            f"재동결이 필요하면 기존 파일을 보존한 채 docs/decision_log.md에 개정으로 기록하고, "
            f"변경 사유와 **결과 열람 여부**를 명시하라 (§13)."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(record) | {"record_hash": record.record_hash}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return record.record_hash


def load_lock2(path: Path = FREEZE_PATH) -> Lock2Record:
    path = Path(path)
    if not path.exists():
        raise LockViolation(f"동결 기록이 없다: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    stored = payload.pop("record_hash", None)
    payload.pop("spec_section", None)
    rec = Lock2Record(
        schema=payload["schema"], frozen_at=payload["frozen_at"],
        git_commit=payload.get("git_commit"), git_dirty=payload.get("git_dirty"),
        grid_hash=payload["grid_hash"],
        split_manifest_hash=payload["split_manifest_hash"],
        audit_buffer_hash=payload["audit_buffer_hash"],
        rankings=payload["rankings"], ranking_hash=payload["ranking_hash"],
        arm_plan=payload["arm_plan"], arm_plan_hash=payload["arm_plan_hash"],
        coverage=payload.get("coverage", {}), notes=payload.get("notes", []),
    )
    if stored and stored != rec.record_hash:
        raise LockViolation(
            f"동결 기록이 변조되었다.\n  파일에 적힌 해시: {stored}\n  재계산한 해시: {rec.record_hash}"
        )
    return rec


def require_lock2(path: Path = FREEZE_PATH) -> Lock2Record:
    """**실기 러너의 진입 조건.** 통과하지 못하면 trial을 시작할 수 없다 (§12).

    확인 항목:
      1. 동결 기록이 존재하는가
      2. 기록이 변조되지 않았는가 (record_hash 재계산)
      3. 5개 점수가 모두 동결되었는가 (`IG-9`)
      4. 현재 그리드가 동결 시점의 그리드와 같은가
      5. arm 구성이 동결된 순위에서 나온 것인가
    """
    rec = load_lock2(path)

    missing = set(SCORE_NAMES) - set(rec.rankings)
    if missing:
        raise LockViolation(f"[IG-9] 동결된 점수에 {sorted(missing)}이(가) 없다. 실기 실행 거부.")

    now = grid_hash()
    if rec.grid_hash != now:
        raise LockViolation(
            f"그리드가 동결 이후 바뀌었다. 실기 실행 거부.\n"
            f"  동결 시점: {rec.grid_hash}\n  현재:      {now}"
        )

    if ranking_hash(rec.rankings) != rec.ranking_hash:
        raise LockViolation("동결된 순위와 기록된 순위 해시가 맞지 않는다. 실기 실행 거부.")

    if rec.arm_plan.get("ranking_hash") != rec.ranking_hash:
        raise LockViolation(
            "[IG-7] arm 구성이 동결된 순위에서 나오지 않았다. 실기 실행 거부."
        )

    return rec


def lock2_status(path: Path = FREEZE_PATH) -> dict:
    """CI/보고용 상태 요약. 예외를 던지지 않는다."""
    try:
        rec = require_lock2(path)
        return {"locked": True, "frozen_at": rec.frozen_at, "git_commit": rec.git_commit,
                "git_dirty": rec.git_dirty, "ranking_hash": rec.ranking_hash,
                "arm_plan_hash": rec.arm_plan_hash, "record_hash": rec.record_hash}
    except LockViolation as e:
        return {"locked": False, "reason": str(e).splitlines()[0]}
