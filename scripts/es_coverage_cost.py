"""§7.3 `ES` 커버리지 문제의 선택지별 비용을 정량화한다.

문제(attempt-002): §7.1의 arm 표는 `score_align` 기준으로만 셀을 고르는데,
`ES-1`은 `score_mag` 상위 3셀, `ES-3`은 `score_cheap_B` 상위 3셀의 성공률을 요구한다.
그 셀들이 어느 arm에도 없으면 실기 데이터가 0개라 계산 불가다.

여기서 답하는 것: **커버리지를 보장하려면 trial이 몇 개 더 드는가.**
"""
import sys
import numpy as np

sys.path.insert(0, "src")
from edgeqgate.arms import ARM_SPEC, build_arms
from edgeqgate.grid import audited_variants
from edgeqgate.scores import rank_cells, score_cheap_A

N_SIM = 3000
SEED = "PREREG-SEED-2026-09-14"
CELLS = [v.code for v in audited_variants()]
CHEAP_A = rank_cells({v.code: score_cheap_A(v).value for v in audited_variants()})


def correlated_ranking(base, rng, rho):
    """base 순위와 목표 상관 rho를 갖는 순위.

    위치 벡터의 표준편차에 맞춰 잡음을 스케일해야 실제로 rho가 나온다.
    범위 전체 크기로 스케일하면 rho와 무관하게 거의 무상관이 된다 (초기 구현의 버그).
    """
    n = len(base)
    pos = np.arange(n, dtype=float)
    sd = pos.std()
    rho = min(max(rho, 1e-6), 0.999999)
    noise_sd = sd * np.sqrt(1.0 / rho ** 2 - 1.0)
    key = pos + rng.normal(size=n) * noise_sd
    order = np.argsort(key)
    return [base[i] for i in order]


def achieved_spearman(rho, rng, n_rep=400):
    """주입한 rho가 실제 순위 상관으로 얼마나 나오는지 확인한다."""
    from scipy.stats import spearmanr
    vals = []
    for _ in range(n_rep):
        base = [f"c{i}" for i in range(len(CELLS))]
        got = correlated_ranking(base, rng, rho)
        pos = {c: i for i, c in enumerate(got)}
        vals.append(spearmanr(range(len(base)), [pos[c] for c in base]).statistic)
    return float(np.mean(vals))


def simulate(rho_mag, rho_cheapb, n_sim=N_SIM):
    """rho_mag = score_mag이 score_align과 얼마나 같은 순위를 주는가."""
    rng = np.random.default_rng(7)
    extra_cells, covered_all = [], 0
    for i in range(n_sim):
        align = [str(c) for c in rng.permutation(CELLS)]
        rk = {"score_align": align,
              "score_mag": correlated_ranking(align, rng, rho_mag),
              "score_cheap_A": CHEAP_A,
              "score_cheap_B": correlated_ranking(align, rng, rho_cheapb),
              "score_cheap_C": [str(c) for c in rng.permutation(CELLS)]}
        plan = build_arms(rk, seed=f"s{i}")
        have = plan.cells_with_trials()
        want = set(rk["score_mag"][:3]) | set(rk["score_cheap_A"][:3]) | set(rk["score_cheap_B"][:3])
        missing = want - have
        extra_cells.append(len(missing))
        covered_all += (len(missing) == 0)
    e = np.array(extra_cells)
    return {"mean_extra_cells": e.mean(), "p50": np.percentile(e, 50),
            "p90": np.percentile(e, 90), "max": e.max(),
            "already_covered_frac": covered_all / n_sim}


def main():
    base = sum(s["n_cells"] * s["trials_per_cell"] for s in ARM_SPEC.values())
    print(f"현재 계획: {base} trial (§7.1)\n")
    rng0 = np.random.default_rng(1)
    print("상관 주입 검증 (목표 -> 실제 Spearman):",
          ", ".join(f"{r}->{achieved_spearman(r, rng0):.2f}" for r in (0.0, 0.8, 0.95)))
    print()
    print("추가로 trial이 필요한 셀 수 — score_mag / cheap_B가 score_align과 얼마나 닮았는지에 따라")
    print(f"{'상관 가정':<28} {'평균':>6} {'중앙':>5} {'p90':>5} {'최대':>5} {'이미 충족':>9}")
    rows = []
    for label, rm, rb in (("무상관 (최악)", 0.0, 0.0),
                          ("mag 높음 0.8 / cheapB 0.3", 0.8, 0.3),
                          ("mag 매우 높음 0.95 / cheapB 0.5", 0.95, 0.5)):
        r = simulate(rm, rb)
        rows.append((label, r))
        print(f"{label:<28} {r['mean_extra_cells']:>6.2f} {r['p50']:>5.0f} "
              f"{r['p90']:>5.0f} {r['max']:>5.0f} {r['already_covered_frac']:>8.1%}")

    print("\n선택지별 비용 (추가 셀당 trial 수를 바꿔가며)")
    print(f"{'추가 셀당 trial':>14} {'p90 기준 추가 trial':>20} {'총계':>8} {'현재 대비':>10}")
    worst = rows[0][1]["p90"]
    real = rows[1][1]["p90"]
    for per in (10, 15, 20, 25):
        add_w, add_r = int(worst * per), int(real * per)
        print(f"{per:>14} {add_w:>13} (최악) {base+add_w:>8} {100*add_w/base:>+9.0f}%")
        print(f"{'':>14} {add_r:>13} (현실) {base+add_r:>8} {100*add_r/base:>+9.0f}%")

    print("\n예산을 225로 고정하고 재배분하면")
    for per in (10, 15):
        need = int(real * per)
        print(f"  추가 셀당 {per} trial -> {need} trial 필요. "
              f"ARM-AUDIT/RANDOM을 25 -> {25 - need // 6} 로 줄이면 상쇄 "
              f"(EP-1 표본 75 -> {3 * (25 - need // 6)})")
    decompose()
    return 0




def decompose(rho_mag=0.8, rho_b=0.3, n_sim=2000):
    """누락 셀이 어느 점수에서 오는지 분해한다.

    `score_cheap_A`의 상위 3셀은 데이터와 무관하게 오늘 이미 확정되어 있다
    (VC-020/022/024). 그것이 누락의 대부분이라면, 그 3셀만 arm에 넣으면
    문제의 상당 부분이 설계 시점에 해소된다.
    """
    rng = np.random.default_rng(11)
    src = {"score_mag": [], "score_cheap_A": [], "score_cheap_B": []}
    union_after_A = []
    for i in range(n_sim):
        align = [str(c) for c in rng.permutation(CELLS)]
        rk = {"score_align": align,
              "score_mag": correlated_ranking(align, rng, rho_mag),
              "score_cheap_A": CHEAP_A,
              "score_cheap_B": correlated_ranking(align, rng, rho_b),
              "score_cheap_C": [str(c) for c in rng.permutation(CELLS)]}
        plan = build_arms(rk, seed=f"d{i}")
        have = plan.cells_with_trials()
        for k in src:
            src[k].append(len(set(rk[k][:3]) - have))
        # cheap_A의 3셀을 미리 포함시켰다고 가정했을 때 남는 누락
        have2 = have | set(CHEAP_A[:3])
        union_after_A.append(len((set(rk["score_mag"][:3]) | set(rk["score_cheap_B"][:3])) - have2))
    print("\n누락 셀의 출처 분해 (mag 상관 0.8, cheapB 0.3)")
    for k, v in src.items():
        a = np.array(v)
        print(f"  {k:<16} 평균 {a.mean():.2f}  p90 {np.percentile(a,90):.0f}  "
              f"전혀 누락 안 됨 {100*(a==0).mean():.1f}%")
    u = np.array(union_after_A)
    print(f"\n  cheap_A 상위 3셀(VC-020/022/024)을 arm에 **미리 넣으면** 남는 누락:")
    print(f"    평균 {u.mean():.2f}  p90 {np.percentile(u,90):.0f}  누락 0인 경우 {100*(u==0).mean():.1f}%")


if __name__ == "__main__":
    sys.exit(main())
