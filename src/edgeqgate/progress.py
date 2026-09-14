"""태스크 진행도 회귀기 `g` (§5.1, `IG-2`).

`g(s, a)` = 상태 s에서 행동 a를 실행한 뒤 도달하는 정규화 진행도 [0, 1].

왜 `g(s)`가 아니라 `g(s, a)`인가:
  §5.1은 민감 방향을 "행동에 대한 `g`의 국소 민감도"로 정의한다. `g`가 상태만 받으면
  ∂g/∂a는 동역학 모델 없이는 정의되지 않는다. 행동을 입력에 포함시키면 미분이 직접
  정의되고, 그 값은 "이 행동을 흔들면 태스크 진행이 얼마나 바뀌는가"라는 의도 그대로다.

왜 랜덤 푸리에 특징 + 릿지인가:
  해석적 기울기를 얻기 위해서다. 유한차분은 스텝 크기라는 자유도를 지표에 밀어넣고,
  그 값에 따라 셀 순위가 바뀔 수 있다. 사전등록 연구에서 순위를 바꿀 수 있는 자유도는
  없애는 편이 낫다. 성능이 목적이 아니다 — `g`는 방향을 주는 도구이지 예측기가 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from .hashing import hash_obj, seed_from
from .splits import SplitManifest, assert_allowed

D_FEATURES_DEFAULT = 512
RIDGE_DEFAULT = 1e-3
LENGTHSCALE_DEFAULT = 1.0


@dataclass
class ProgressRegressor:
    """학습된 `g`. 가중치와 정규화 통계를 모두 담아 해시 가능하게 둔다."""

    W: np.ndarray          # (D, S+A) 랜덤 주파수
    b: np.ndarray          # (D,) 위상
    w: np.ndarray          # (D,) 릿지 가중치
    intercept: float
    mu: np.ndarray         # (S+A,) 입력 평균
    sigma: np.ndarray      # (S+A,) 입력 표준편차
    state_dim: int
    action_dim: int
    seed: str
    n_train_samples: int

    # ---- 내부 ----

    def _standardize(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mu) / self.sigma

    def _features(self, xs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """RFF와 그 내부 인자를 함께 반환 (기울기 계산에 재사용)."""
        proj = xs @ self.W.T + self.b            # (N, D)
        scale = np.sqrt(2.0 / self.W.shape[0])
        return scale * np.cos(proj), proj

    # ---- 공개 API ----

    def predict(self, states: np.ndarray, actions: np.ndarray) -> np.ndarray:
        x = np.concatenate([np.atleast_2d(states), np.atleast_2d(actions)], axis=1)
        z, _ = self._features(self._standardize(x))
        return z @ self.w + self.intercept

    def grad_action(self, states: np.ndarray, actions: np.ndarray) -> np.ndarray:
        """∂g/∂a — 해석적. 반환 (N, action_dim).

        g = sqrt(2/D) * sum_d w_d cos(W_d·x~ + b_d),  x~ = (x - mu)/sigma
        ∂g/∂a = -sqrt(2/D) * sum_d w_d sin(W_d·x~ + b_d) * W_d[a] / sigma[a]
        """
        x = np.concatenate([np.atleast_2d(states), np.atleast_2d(actions)], axis=1)
        xs = self._standardize(x)
        _, proj = self._features(xs)
        scale = np.sqrt(2.0 / self.W.shape[0])
        coef = -scale * np.sin(proj) * self.w                 # (N, D)
        Wa = self.W[:, self.state_dim :]                      # (D, A)
        grad = coef @ Wa                                      # (N, A)
        return grad / self.sigma[self.state_dim :]

    def sensitivity_directions(
        self, states: np.ndarray, actions: np.ndarray, eps: float = 1e-12
    ) -> tuple[np.ndarray, np.ndarray]:
        """단위 민감 방향 u와 그 크기 |∂g/∂a|.

        크기가 수치적으로 0인 상태(진행도가 행동에 무감각한 구간 — 예: 정지 대기)는
        방향이 정의되지 않는다. 그런 상태는 0 벡터를 돌려주고, 점수 계산에서 정렬 성분이
        0이 되도록 둔다. 임의 방향을 채워넣으면 없는 신호를 만들어내게 된다.
        """
        g = self.grad_action(states, actions)
        norm = np.linalg.norm(g, axis=1, keepdims=True)
        u = np.where(norm > eps, g / np.maximum(norm, eps), 0.0)
        return u, norm.squeeze(-1)

    @property
    def model_hash(self) -> str:
        return hash_obj(
            {
                "W": np.round(self.W, 12),
                "b": np.round(self.b, 12),
                "w": np.round(self.w, 12),
                "intercept": round(float(self.intercept), 12),
                "mu": np.round(self.mu, 12),
                "sigma": np.round(self.sigma, 12),
                "seed": self.seed,
                "n_train_samples": self.n_train_samples,
            }
        )


def phase_targets(episode_length: int) -> np.ndarray:
    """에피소드 길이 T에 대한 진행도 타깃.

    (s_t, a_t) -> a_t 실행 후 도달하는 정규화 위상. 마지막 스텝은 1.0.
    """
    if episode_length < 2:
        raise ValueError("길이 2 미만 에피소드는 진행도 타깃을 만들 수 없다")
    t = np.arange(episode_length, dtype=float)
    return np.clip((t + 1.0) / (episode_length - 1.0), 0.0, 1.0)


def fit(
    states: np.ndarray,
    actions: np.ndarray,
    targets: np.ndarray,
    seed: str,
    n_features: int = D_FEATURES_DEFAULT,
    ridge: float = RIDGE_DEFAULT,
    lengthscale: float = LENGTHSCALE_DEFAULT,
) -> ProgressRegressor:
    """릿지 닫힌 해. 무작위성은 커밋된 시드에서만 온다."""
    states = np.atleast_2d(np.asarray(states, dtype=float))
    actions = np.atleast_2d(np.asarray(actions, dtype=float))
    targets = np.asarray(targets, dtype=float).reshape(-1)
    if not (states.shape[0] == actions.shape[0] == targets.shape[0]):
        raise ValueError("states/actions/targets의 표본 수가 다르다")

    x = np.concatenate([states, actions], axis=1)
    mu = x.mean(axis=0)
    sigma = x.std(axis=0)
    sigma = np.where(sigma < 1e-8, 1.0, sigma)  # 상수 차원은 스케일 1로 둔다
    xs = (x - mu) / sigma

    rng = np.random.default_rng(seed_from(seed, "progress-regressor-rff"))
    d_in = xs.shape[1]
    W = rng.normal(0.0, 1.0 / lengthscale, size=(n_features, d_in))
    b = rng.uniform(0.0, 2.0 * np.pi, size=n_features)

    scale = np.sqrt(2.0 / n_features)
    Z = scale * np.cos(xs @ W.T + b)
    y_mean = targets.mean()
    y = targets - y_mean

    A = Z.T @ Z + ridge * np.eye(n_features)
    w = np.linalg.solve(A, Z.T @ y)

    return ProgressRegressor(
        W=W, b=b, w=w, intercept=float(y_mean), mu=mu, sigma=sigma,
        state_dim=states.shape[1], action_dim=actions.shape[1],
        seed=seed, n_train_samples=int(xs.shape[0]),
    )


def fit_from_episodes(
    manifest: SplitManifest,
    episode_ids: Sequence[str],
    load_episode,
    seed: str,
    **kwargs,
) -> ProgressRegressor:
    """`IG-2` 가드를 통과시킨 뒤 학습한다.

    load_episode(episode_id) -> (states (T,S), actions (T,A))
    """
    verified = assert_allowed(manifest, episode_ids, "progress_regressor")
    S, A, Y = [], [], []
    for eid in verified:
        s, a = load_episode(eid)
        s = np.asarray(s, dtype=float)
        a = np.asarray(a, dtype=float)
        if s.shape[0] != a.shape[0]:
            raise ValueError(f"에피소드 {eid}: 상태/행동 길이 불일치")
        S.append(s)
        A.append(a)
        Y.append(phase_targets(s.shape[0]))
    return fit(np.concatenate(S), np.concatenate(A), np.concatenate(Y), seed=seed, **kwargs)
