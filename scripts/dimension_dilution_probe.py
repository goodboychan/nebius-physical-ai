"""내가 양팔을 권하며 든 메커니즘이 실제로 성립하는가 — 팔을 사기 전에 확인한다.

**주장**: 행동 차원이 늘면 `score_mag`는 태스크 무관 차원에 희석되어 판별력이 떨어지고,
`score_align`은 민감 방향에 투영하므로 영향을 덜 받는다. 따라서 양팔(12-DoF)에서
두 점수의 격차가 벌어져 `H2`의 판별력이 올라간다.

**검증 방법**: 합성. 태스크 민감 부분공간의 차원 k를 고정하고 전체 행동 차원 D를 늘린다.
"안전한 셀"과 "위험한 셀"을 민감 방향 성분의 크기로만 구분하고, 두 점수가 그 둘을
얼마나 잘 갈라내는지(효과 크기)를 D에 대해 본다.

**이것이 보여주지 않는 것**: 실제 태스크에서 민감 부분공간의 차원이 몇인지,
양팔에서 그것이 어떻게 변하는지. 그건 실기로만 안다. 여기서 보는 것은
"차원이 늘면 두 점수가 어떻게 반응하는가"라는 **기하학적 성질**뿐이다.
"""
import sys
import numpy as np

sys.path.insert(0, "src")
from edgeqgate.scores import score_align, score_mag

RNG = np.random.default_rng(20260915)
N_STATES = 2000
K_SENSITIVE = 2          # 태스크 민감 부분공간의 차원 (양팔이어도 협응 제약 수는 비슷하다고 본다)
N_CELLS = 12             # 셀당 효과 크기 추정을 위한 반복


def sensitive_basis(D, k, rng):
    A = rng.normal(size=(D, k))
    Q, _ = np.linalg.qr(A)
    return Q[:, :k]                      # (D, k) 정규직교


def make_errors(D, U, sens_gain, iso_gain, rng):
    """민감 성분 + 등방 잡음. 셀 간 차이는 sens_gain에만 있다."""
    a = rng.normal(size=(N_STATES, U.shape[1])) * sens_gain
    sens = a @ U.T                        # (N, D) 민감 부분공간 성분
    iso = rng.normal(size=(N_STATES, D)) * iso_gain
    return sens + iso


def cohens_d(x, y):
    nx, ny = len(x), len(y)
    s = np.sqrt(((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)) / (nx + ny - 2))
    return (np.mean(x) - np.mean(y)) / s if s > 0 else 0.0


def main():
    ISO = 0.05
    SAFE, RISKY = 0.02, 0.06             # 민감 방향 성분: 위험 셀이 3배
    print(f"민감 부분공간 차원 k={K_SENSITIVE} 고정, 등방 잡음 {ISO}, "
          f"민감 성분 안전 {SAFE} vs 위험 {RISKY}")
    print(f"{'D':>4} {'mag(안전)':>11} {'mag(위험)':>11} {'d_mag':>8} "
          f"{'align(안전)':>12} {'align(위험)':>12} {'d_align':>9} {'비율':>7}")
    rows = []
    for D in (6, 12, 24, 48):
        U = sensitive_basis(D, K_SENSITIVE, RNG)
        u_dir = U[:, 0] / np.linalg.norm(U[:, 0])
        dirs = np.tile(u_dir, (N_STATES, 1))
        mg, ag = {}, {}
        for tag, gain in (("safe", SAFE), ("risky", RISKY)):
            mg[tag], ag[tag] = [], []
            for _ in range(N_CELLS):
                e = make_errors(D, U, gain, ISO, RNG)
                mg[tag].append(score_mag(e, cell="x").value)
                ag[tag].append(score_align(e, dirs, cell="x").value)
        dm = cohens_d(np.array(mg["risky"]), np.array(mg["safe"]))
        da = cohens_d(np.array(ag["risky"]), np.array(ag["safe"]))
        ratio = da / dm if dm else float("inf")
        rows.append((D, dm, da, ratio))
        print(f"{D:>4} {np.mean(mg['safe']):>11.5f} {np.mean(mg['risky']):>11.5f} {dm:>8.2f} "
              f"{np.mean(ag['safe']):>12.5f} {np.mean(ag['risky']):>12.5f} {da:>9.2f} {ratio:>7.2f}")

    print()
    d6 = next(r for r in rows if r[0] == 6)
    d12 = next(r for r in rows if r[0] == 12)
    print(f"6 -> 12차원에서  d_mag {d6[1]:.2f} -> {d12[1]:.2f} "
          f"({100*(d12[1]-d6[1])/d6[1]:+.0f}%),  d_align {d6[2]:.2f} -> {d12[2]:.2f} "
          f"({100*(d12[2]-d6[2])/d6[2]:+.0f}%)")
    claim = d12[3] > d6[3]
    print(f"주장('차원이 늘면 align 우위가 커진다') 성립: {claim}")
    sensitivity_to_k_scaling()
    return 0




def sensitivity_to_k_scaling():
    """급소 확인: 민감 부분공간 차원 k가 행동 차원과 함께 커지면 어떻게 되는가.

    위 결과는 k가 고정이라는 가정 위에 있다. 양팔이 되면서 협응 제약이 늘어
    k도 함께 커진다면 희석 우위는 사라질 수 있다. 세 시나리오를 본다.
    """
    ISO, SAFE, RISKY = 0.05, 0.02, 0.06
    print("\n=== 급소 확인: k가 차원에 따라 어떻게 변하는가 ===")
    for label, kf in (("k 고정 (2)", lambda D: 2),
                      ("k 비례 (D/6 배)", lambda D: max(2, round(2 * D / 6))),
                      ("k 완전 비례 (D/3)", lambda D: max(2, D // 3))):
        out = []
        for D in (6, 12):
            k = kf(D)
            U = sensitive_basis(D, k, RNG)
            u = U[:, 0] / np.linalg.norm(U[:, 0])
            dirs = np.tile(u, (N_STATES, 1))
            mg, ag = {}, {}
            for tag, gain in (("safe", SAFE), ("risky", RISKY)):
                mg[tag] = [score_mag(make_errors(D, U, gain, ISO, RNG), cell="x").value
                           for _ in range(N_CELLS)]
                ag[tag] = [score_align(make_errors(D, U, gain, ISO, RNG), dirs, cell="x").value
                           for _ in range(N_CELLS)]
            dm = cohens_d(np.array(mg["risky"]), np.array(mg["safe"]))
            da = cohens_d(np.array(ag["risky"]), np.array(ag["safe"]))
            out.append((D, k, dm, da, da / dm if dm else float("inf")))
        r6, r12 = out
        verdict = "우위 증가" if r12[4] > r6[4] else "우위 감소/소멸"
        print(f"  {label:<18} D=6(k={r6[1]}) 비율 {r6[4]:.2f}  ->  "
              f"D=12(k={r12[1]}) 비율 {r12[4]:.2f}   {verdict}")


if __name__ == "__main__":
    sys.exit(main())
