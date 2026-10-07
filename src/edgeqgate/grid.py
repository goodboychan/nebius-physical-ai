"""변형 그리드 (§4) — `VC` 시리즈.

§4.1 요인 설계: calib_size(4) x calib_composition(3) x granularity(2) = 24 INT8 셀
              + VC-000 (FP32, GX10) + VC-025 (FP16, Jetson TRT) = 26 셀

셀 번호 ↔ 요인 조합 매핑은 configs/variant_grid.yaml에 **고정**되며, 이 모듈의 정준
생성기와 일치해야 한다(§4.1). 불일치는 즉시 예외다 — 손으로 고친 그리드로 감사가 돌면
셀 번호와 조합의 대응이 깨져 전체 결과 해석이 무효가 된다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from itertools import product
from pathlib import Path
from typing import Iterator

import yaml

from .hashing import hash_obj

# 축 수준. 순서가 곧 셀 번호 순서이므로 **절대 재정렬 금지**.
CALIB_SIZES = (16, 64, 256, 1024)
CALIB_COMPOSITIONS = ("success-only", "early-phase-only", "late-phase-only")  # 2026-10-07: mixed → early-phase-only
GRANULARITIES = ("per-tensor", "per-channel")

def _default_grid_path() -> Path:
    """그리드 yaml 위치를 찾는다.

    패키지 상대 경로만 쓰면 컨테이너나 Jobs 환경에서 깨진다 (설치 위치가 다르다).
    우선순위: 환경변수 -> 패키지 기준 -> 현재 작업 디렉토리 기준.
    """
    env = os.environ.get("EDGEQGATE_GRID_PATH")
    if env:
        return Path(env)
    pkg = Path(__file__).resolve().parents[2] / "configs" / "variant_grid.yaml"
    if pkg.is_file():
        return pkg
    cwd = Path.cwd() / "configs" / "variant_grid.yaml"
    return cwd if cwd.is_file() else pkg


GRID_PATH = _default_grid_path()


@dataclass(frozen=True)
class Variant:
    code: str
    precision: str                 # fp32 | fp16 | int8
    target: str                    # gx10 | jetson-trt
    calib_size: int | None
    calib_composition: str | None
    granularity: str | None
    role: str                      # 셀의 역할 서술 (§4.1)

    @property
    def is_audited(self) -> bool:
        """감사 점수 산출 대상인가.

        VC-000(FP32)은 오차의 기준점 자체이므로 점수가 정의되지 않는다(자기 자신과의 차 = 0).
        §5.2 "25개 INT8/FP16 셀의 전체 순위"는 VC-000을 제외한 25셀을 뜻한다.
        """
        return self.code != "VC-000"


def canonical_variants() -> list[Variant]:
    """정준 그리드. 이 함수가 셀 번호 매핑의 단일 진실 공급원이다."""
    variants = [
        Variant(
            code="VC-000",
            precision="fp32",
            target="gx10",
            calib_size=None,
            calib_composition=None,
            granularity=None,
            role="상한 기준선 / 행동 오차의 레퍼런스",
        )
    ]
    # 중첩 순서: calib_size(외) -> composition(중) -> granularity(내). 고정.
    idx = 0
    for size, comp, gran in product(CALIB_SIZES, CALIB_COMPOSITIONS, GRANULARITIES):
        idx += 1
        variants.append(
            Variant(
                code=f"VC-{idx:03d}",
                precision="int8",
                target="jetson-trt",
                calib_size=size,
                calib_composition=comp,
                granularity=gran,
                role="INT8 요인 셀",
            )
        )
    assert idx == 24, f"INT8 셀이 24개가 아니다: {idx}"
    variants.append(
        Variant(
            code="VC-025",
            precision="fp16",
            target="jetson-trt",
            calib_size=None,
            calib_composition=None,
            granularity=None,
            role="정밀도 축 대조",
        )
    )
    return variants


def grid_payload() -> dict:
    """yaml로 직렬화할 정준 페이로드."""
    return {
        "schema": "edgeqgate/variant_grid/v1",
        "spec_section": "§4.1",
        "axes": {
            "calib_size": list(CALIB_SIZES),
            "calib_composition": list(CALIB_COMPOSITIONS),
            "granularity": list(GRANULARITIES),
        },
        "ordering": "calib_size(outer) -> calib_composition(middle) -> granularity(inner)",
        "variants": [asdict(v) for v in canonical_variants()],
    }


def write_grid(path: Path = GRID_PATH) -> str:
    """정준 그리드를 yaml로 쓰고 해시를 반환."""
    payload = grid_payload()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 자동 생성: python -m edgeqgate.grid write\n")
        f.write("# 손으로 고치지 말 것. 이 파일은 edgeqgate.grid.canonical_variants()와\n")
        f.write("# 일치해야 하며, 불일치 시 load_grid()가 예외를 던진다 (§4.1).\n")
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True, width=100)
    return hash_obj(payload)


def load_grid(path: Path = GRID_PATH) -> list[Variant]:
    """yaml 그리드를 읽고 정준 생성기와 대조한다. 불일치면 예외."""
    with open(path, encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    expected = grid_payload()
    if hash_obj(payload) != hash_obj(expected):
        raise ValueError(
            f"variant_grid.yaml이 정준 그리드와 다르다 (§4.1 위반).\n"
            f"  파일 해시: {hash_obj(payload)}\n"
            f"  정준 해시: {hash_obj(expected)}\n"
            f"  → 손으로 고쳤다면 되돌리고, 설계를 바꾸려면 코드를 고친 뒤 재생성하고 "
            f"docs/decision_log.md에 개정으로 기록하라."
        )
    return canonical_variants()


def grid_hash() -> str:
    return hash_obj(grid_payload())


def audited_variants() -> list[Variant]:
    return [v for v in canonical_variants() if v.is_audited]


def ranked_variants() -> list[Variant]:
    """순위·arm 선정 풀: INT8 셀만 (2026-10-07 결정, manual_actions #3).
    FP16 `VC-025`는 감사 점수는 내되 '정밀도 축 대조'로 따로 보고하고, 순위와 arm 선정에는 넣지 않는다.
    INT8보다 오차가 8–9배 작아 같은 순위에 두면 혼자 1위가 되어 `ARM-AUDIT` 선정을 왜곡한다."""
    return [v for v in audited_variants() if v.precision == "int8"]


def by_code(code: str) -> Variant:
    for v in canonical_variants():
        if v.code == code:
            return v
    raise KeyError(f"알 수 없는 셀 코드: {code}")


def _iter_summary() -> Iterator[str]:
    for v in canonical_variants():
        if v.precision == "int8":
            yield f"{v.code}  int8  size={v.calib_size:<5} comp={v.calib_composition:<16} gran={v.granularity}"
        else:
            yield f"{v.code}  {v.precision:<5} {v.target:<12} — {v.role}"


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "write":
        h = write_grid()
        print(f"configs/variant_grid.yaml 생성됨\ngrid_hash = {h}")
    else:
        print("\n".join(_iter_summary()))
        print(f"\n총 {len(canonical_variants())} 셀, 감사 대상 {len(audited_variants())} 셀")
        print(f"grid_hash = {grid_hash()}")
