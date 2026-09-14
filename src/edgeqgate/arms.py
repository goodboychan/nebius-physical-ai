"""실기 arm 구성 (§7.1) 과 `IG-7`.

arm 확정은 `LOCK-2`(점수 동결) **직후** 1회만 일어나고 그 결과를 봉인한다.
이 모듈의 모든 무작위성은 커밋된 시드에서만 나오며, 재실행하면 같은 arm이 나온다.

이 모듈은 arm을 만들기만 하지 않는다. §7.3의 `ES-1`/`ES-3`가 실제로 계산 가능한지를
**지금(= 결과를 보기 전에)** 점검해 보고한다. 근거는 coverage_report() docstring 참조.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field

import numpy as np

from .grid import audited_variants, by_code
from .hashing import hash_obj, seed_from
from .scores import SCORE_NAMES, ranking_hash

# §7.1 arm 표. 셀 수와 trial/셀을 코드로 고정한다.
ARM_SPEC = {
    "ARM-AUDIT":  {"n_cells": 3, "trials_per_cell": 25, "source": "score_align 상위 3셀"},
    "ARM-RANDOM": {"n_cells": 3, "trials_per_cell": 25, "source": "나머지 풀에서 커밋 시드 무작위"},
    "ARM-LOW":    {"n_cells": 2, "trials_per_cell": 15, "source": "score_align 하위 2셀"},
    "ARM-FP32":   {"n_cells": 1, "trials_per_cell": 25, "source": "VC-000"},
    "ARM-RETEST": {"n_cells": 1, "trials_per_cell": 20, "source": "ARM-AUDIT 중 1셀, 별도 세션"},
}
TOTAL_TRIALS = 225

# §12 리스크 레지스터가 **사전 고정**한 축소 순서. 결과를 본 뒤 고르지 않기 위해 코드에 박는다.
REDUCTION_ORDER = [
    ("ARM-LOW", 15, 10),
    ("ARM-AUDIT", 25, 20),
    ("ARM-RANDOM", 25, 20),
]


@dataclass(frozen=True)
class ArmPlan:
    schema: str
    seed: str
    ranking_hash: str
    arms: dict[str, list[str]]              # arm -> 셀 코드
    trials_per_cell: dict[str, int]         # arm -> trial 수
    retest_cell: str
    spec_section: str = "§7.1"
    notes: list[str] = field(default_factory=list)

    @property
    def plan_hash(self) -> str:
        return hash_obj(asdict(self))

    def trial_counts(self) -> dict[tuple[str, str], int]:
        """(arm, cell) -> trial 수."""
        return {
            (arm, cell): self.trials_per_cell[arm]
            for arm, cells in self.arms.items()
            for cell in cells
        }

    def total_trials(self) -> int:
        return sum(self.trial_counts().values())

    def cells_with_trials(self) -> set[str]:
        """실기 데이터가 생기는 셀 전체. `ARM-FP32`의 VC-000 포함."""
        return {c for cells in self.arms.values() for c in cells}


def build_arms(rankings: dict[str, list[str]], seed: str) -> ArmPlan:
    """동결된 순위에서 arm을 결정한다 (§7.1, `IG-7`).

    rankings: 점수명 -> 오름차순 셀 순위 (1위 = 가장 안전). 5개 점수 전부 필요(`IG-9`).
    """
    rhash = ranking_hash(rankings)   # 5개 점수가 다 있는지 IG-9가 먼저 검사한다
    align = list(rankings["score_align"])

    known = {v.code for v in audited_variants()}
    align = [str(c) for c in align]
    if set(align) != known:
        raise ValueError(
            f"score_align 순위가 감사 대상 25셀과 다르다. "
            f"누락 {sorted(known - set(align))}, 초과 {sorted(set(align) - known)}"
        )

    # numpy 문자열 스칼라가 섞이면 yaml 직렬화가 깨지므로 여기서 순수 str로 고정한다.
    audit_cells = [str(c) for c in align[:3]]
    low_cells = [str(c) for c in align[-2:][::-1]]   # 최하위부터

    # `IG-7`: 나머지 풀에서 커밋된 시드로 3셀. 추출 후 교체·재추출 금지.
    pool = sorted(set(align) - set(audit_cells) - set(low_cells))
    rng = np.random.default_rng(seed_from(seed, "IG-7/arm-random", rhash))
    random_cells = sorted(str(c) for c in rng.choice(pool, size=3, replace=False).tolist())

    # `ARM-RETEST` 대상 셀: §7.1은 "ARM-AUDIT 중 1셀"이라고만 하고 선택 규칙이 없다.
    # 사람이 고르면 결과를 본 뒤 고를 수 있는 경로가 열리므로 시드로 결정한다.
    rng_rt = np.random.default_rng(seed_from(seed, "arm-retest-pick", rhash))
    retest_cell = str(rng_rt.choice(sorted(audit_cells)))

    return ArmPlan(
        schema="edgeqgate/arm_plan/v1",
        seed=seed,
        ranking_hash=rhash,
        arms={
            "ARM-AUDIT": audit_cells,
            "ARM-RANDOM": random_cells,
            "ARM-LOW": low_cells,
            "ARM-FP32": ["VC-000"],
            "ARM-RETEST": [retest_cell],
        },
        trials_per_cell={a: s["trials_per_cell"] for a, s in ARM_SPEC.items()},
        retest_cell=retest_cell,
        notes=[
            "ARM-RETEST는 ARM-AUDIT의 셀을 별도 세션에서 재측정한다(§7.4 ES-5).",
            "ARM-RETEST의 20 trial은 EP-1의 ARM-AUDIT 75 trial에 합산하지 않는다.",
            "ARM-FP32는 테스트 arm과 동일 인터리브 블록에서 실행한다(IG-8).",
            "ARM-RANDOM 추출은 IG-7에 따라 1회만. 재추출 금지.",
        ],
    )


def coverage_report(plan: ArmPlan, rankings: dict[str, list[str]]) -> dict:
    """§7.3의 `ES-1`–`ES-3`가 계산 가능한지 사전 점검한다.

    왜 필요한가: §7.1의 arm 표는 `score_align`의 상·하위 셀과 무작위 셀에만 trial을 배정한다.
    그런데 `ES-1`은 `score_mag` 상위 3셀의 성공률을, `ES-3`은 `score_cheap_B` 상위 3셀의
    성공률을 요구한다. 이 셀들이 어느 arm에도 없으면 **실기 데이터가 아예 없어서**
    해당 부 가설을 계산할 수 없다. §7.3은 "겹치는 셀은 trial을 공유한다"고만 말하고
    겹치지 않는 경우를 다루지 않는다.

    이 함수는 그 공백을 `LOCK-2` 시점에 드러낸다 — 실기가 끝난 뒤 "계산 불가"를 발견하면
    그때는 손쓸 방법이 없고, 사후에 trial을 추가하면 blinding과 인터리브가 깨진다.
    """
    have = plan.cells_with_trials()
    report: dict[str, dict] = {}
    checks = {
        "ES-1": ("score_mag", 3),
        "ES-2": ("score_cheap_A", 3),
        "ES-3": ("score_cheap_B", 3),
    }
    for endpoint, (score, k) in checks.items():
        wanted = list(rankings[score])[:k]
        covered = [c for c in wanted if c in have]
        missing = [c for c in wanted if c not in have]
        report[endpoint] = {
            "score": score,
            "top_k": wanted,
            "covered": covered,
            "missing": missing,
            "computable": len(missing) == 0,
            "partial": 0 < len(covered) < k,
        }
    report["_summary"] = {
        "cells_with_trials": sorted(have),
        "n_cells_with_trials": len(have),
        "all_computable": all(v["computable"] for k, v in report.items() if k != "_summary"),
    }
    return report


def format_coverage(report: dict) -> str:
    lines = []
    for ep in ("ES-1", "ES-2", "ES-3"):
        r = report[ep]
        mark = "OK  " if r["computable"] else ("부분" if r["partial"] else "불가")
        lines.append(
            f"  [{mark}] {ep} ({r['score']} top3={r['top_k']}) "
            f"covered={r['covered']} missing={r['missing']}"
        )
    return "\n".join(lines)


def apply_reduction(plan: ArmPlan, step: int) -> ArmPlan:
    """§12의 사전 고정된 축소 순서를 step 단계만큼 적용한다.

    시간 초과 시에만 쓴다. 축소 대상은 결과와 무관하게 이 순서로만 정해진다.
    """
    tpc = dict(plan.trials_per_cell)
    applied = []
    for i, (arm, before, after) in enumerate(REDUCTION_ORDER):
        if i < step:
            if tpc[arm] != before:
                raise ValueError(f"{arm}의 현재 trial 수 {tpc[arm]}가 축소 전제 {before}와 다르다")
            tpc[arm] = after
            applied.append(f"{arm} {before}->{after}")
    return ArmPlan(
        schema=plan.schema, seed=plan.seed, ranking_hash=plan.ranking_hash,
        arms=plan.arms, trials_per_cell=tpc, retest_cell=plan.retest_cell,
        notes=plan.notes + [f"§12 사전 고정 축소 적용: {', '.join(applied)}"],
    )
