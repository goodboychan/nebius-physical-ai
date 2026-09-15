"""리트리벌 동결 (`D5` 기반, §12의 재현성 요구).

문제: 검색 결과는 시간에 따라 변한다. 사전등록 연구가 검색 결과를 근거로 쓰려면
**언제 무엇을 받았는지**가 고정되어야 한다. 그렇지 않으면 리포트의 근거를 나중에
재현할 수 없고, "그때는 이렇게 나왔다"를 검증할 방법이 없다.

설계: 질의와 응답을 통째로 스냅샷하고 해시를 박는다. 이후 실행은 네트워크를 치지 않고
동결본을 replay한다. 동결본이 없으면 replay 모드는 실패한다 — 조용히 새 검색을 하지 않는다.

이 모듈은 Tavily에 의존하지 않는다. 검색 함수를 주입받으므로 테스트에서 네트워크 없이
동작을 검증할 수 있다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from .hashing import hash_obj

SNAPSHOT_DIR = Path("artifacts/retrieval")


class SnapshotMissing(RuntimeError):
    """동결본이 없는데 replay가 요청되었다. 조용히 새로 검색하지 않는다."""


def _result_digest(r: dict) -> str:
    """결과 항목의 내용 해시. url·제목·본문만 본다 (점수는 재현성 대상이 아니다)."""
    return hashlib.sha256(
        json.dumps({k: r.get(k, "") for k in ("url", "title", "content")},
                   sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class RetrievalSnapshot:
    schema: str
    frozen_at: str
    queries: list[str]
    results: dict[str, list[dict]]        # query -> 결과 목록
    result_digests: dict[str, list[str]]  # query -> 내용 해시 목록
    provider: str
    notes: list[str] = field(default_factory=list)

    @property
    def snapshot_hash(self) -> str:
        return hash_obj({"queries": self.queries, "digests": self.result_digests,
                         "provider": self.provider})

    def urls(self, query: str) -> list[str]:
        return [r.get("url", "") for r in self.results.get(query, [])]

    def all_urls(self) -> list[str]:
        seen, out = set(), []
        for q in self.queries:
            for u in self.urls(q):
                if u and u not in seen:
                    seen.add(u)
                    out.append(u)
        return out


def freeze(
    queries: Sequence[str],
    search_fn: Callable[[str], list[dict]],
    provider: str = "tavily",
    notes: Sequence[str] | None = None,
) -> RetrievalSnapshot:
    """질의를 실행하고 결과를 동결한다."""
    results, digests = {}, {}
    for q in queries:
        rs = list(search_fn(q))
        results[q] = rs
        digests[q] = [_result_digest(r) for r in rs]
    return RetrievalSnapshot(
        schema="edgeqgate/retrieval_snapshot/v1",
        frozen_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        queries=list(queries), results=results, result_digests=digests,
        provider=provider, notes=list(notes or []),
    )


def write_snapshot(snap: RetrievalSnapshot, path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(snap) | {"snapshot_hash": snap.snapshot_hash}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return snap.snapshot_hash


def load_snapshot(path: str | Path) -> RetrievalSnapshot:
    path = Path(path)
    if not path.is_file():
        raise SnapshotMissing(
            f"동결본이 없다: {path}. replay 모드는 새 검색을 하지 않는다 — "
            f"먼저 freeze를 수행하라."
        )
    p = json.loads(path.read_text(encoding="utf-8"))
    stored = p.pop("snapshot_hash", None)
    p.pop("schema", None)
    snap = RetrievalSnapshot(
        schema="edgeqgate/retrieval_snapshot/v1", frozen_at=p["frozen_at"],
        queries=p["queries"], results=p["results"], result_digests=p["result_digests"],
        provider=p["provider"], notes=p.get("notes", []),
    )
    if stored and stored != snap.snapshot_hash:
        raise SnapshotMissing(
            f"동결본이 변조되었다.\n  파일 해시: {stored}\n  재계산: {snap.snapshot_hash}"
        )
    return snap


def drift(a: RetrievalSnapshot, b: RetrievalSnapshot) -> dict:
    """두 시점의 동결본을 비교한다. 검색 결과가 얼마나 흔들리는지 정량화한다.

    `score_folklore`처럼 검색에 의존하는 점수를 사전등록에 넣을지 판단하는 근거가 된다.
    """
    out = {}
    for q in sorted(set(a.queries) & set(b.queries)):
        ua, ub = a.urls(q), b.urls(q)
        sa, sb = set(ua), set(ub)
        inter = sa & sb
        out[q] = {
            "n_a": len(ua), "n_b": len(ub),
            "same_set": sa == sb, "same_order": ua == ub,
            "jaccard": (len(inter) / len(sa | sb)) if (sa | sb) else 1.0,
            "only_a": sorted(sa - sb), "only_b": sorted(sb - sa),
            "content_changed": sorted(
                u for u in inter
                if _digest_of(a, q, u) != _digest_of(b, q, u)
            ),
        }
    return out


def _digest_of(snap: RetrievalSnapshot, query: str, url: str) -> str | None:
    for r, d in zip(snap.results.get(query, []), snap.result_digests.get(query, [])):
        if r.get("url") == url:
            return d
    return None
