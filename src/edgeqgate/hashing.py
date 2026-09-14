"""정준 해시 유틸 — §3.2, §4.1, §5.3, §8의 해시 커밋에 공통으로 쓰인다.

원칙: 해시는 "무엇을 해시했는지"가 재현 가능해야 한다. 따라서
  - 구조화 데이터는 정렬된 키 + 고정 구분자의 JSON(UTF-8, NFC 미적용 ASCII 이스케이프)으로 직렬화
  - 부동소수는 repr 대신 17자리 유효숫자 고정 포맷으로 직렬화 (플랫폼 간 재현성)
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

_DIGEST = "sha256"


def _normalize(obj: Any) -> Any:
    """직렬화 전 정규화. float는 고정 포맷 문자열로 바꿔 플랫폼 차이를 없앤다."""
    if isinstance(obj, float):
        if math.isnan(obj):
            return "__nan__"
        if math.isinf(obj):
            return "__inf__" if obj > 0 else "__-inf__"
        # 17 유효숫자면 IEEE754 double을 무손실 왕복할 수 있다.
        return f"{obj:.17g}"
    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    # numpy 스칼라/배열 등
    if hasattr(obj, "tolist"):
        return _normalize(obj.tolist())
    raise TypeError(f"해시할 수 없는 타입: {type(obj)!r}")


def canonical_bytes(obj: Any) -> bytes:
    """정준 직렬화 바이트열."""
    return json.dumps(
        _normalize(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def hash_obj(obj: Any) -> str:
    """구조화 객체의 정준 해시 (sha256 hex)."""
    return hashlib.new(_DIGEST, canonical_bytes(obj)).hexdigest()


def hash_file(path: str | Path) -> str:
    """파일 바이트열의 해시."""
    h = hashlib.new(_DIGEST)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def seed_from(*parts: Any) -> int:
    """커밋된 시드 문자열 + 용도 라벨에서 결정적 32bit 시드를 만든다.

    같은 (seed, 용도)면 항상 같은 값. 용도를 섞어 쓰면 축 간 상관이 생기므로
    호출부는 반드시 용도 라벨을 명시한다.
    """
    digest = hashlib.new(_DIGEST, canonical_bytes(list(parts))).digest()
    return int.from_bytes(digest[:4], "big")
