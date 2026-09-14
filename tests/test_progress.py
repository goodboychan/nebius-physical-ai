"""§5.1 진행도 회귀기 `g(s, a)` 와 `IG-2`."""
import numpy as np
import pytest

from edgeqgate.progress import fit, fit_from_episodes, phase_targets
from edgeqgate.splits import IntegrityViolation

SEED = "PREREG-SEED-TEST"


@pytest.fixture
def toy():
    """진행도가 행동 축 0에만 민감한 장난감 문제."""
    rng = np.random.default_rng(0)
    s = rng.normal(size=(3000, 6))
    a = rng.normal(size=(3000, 4))
    y = 0.5 + 0.3 * np.tanh(1.5 * a[:, 0] + 0.4 * s[:, 0])
    return s, a, y


def test_analytic_gradient_matches_finite_difference(toy):
    """해석적 기울기를 쓰는 이유가 이것이다 — 스텝 크기 자유도를 없앤다 (§5.1)."""
    s, a, y = toy
    g = fit(s, a, y, seed=SEED)
    ga = g.grad_action(s[:8], a[:8])
    h = 1e-5
    fd = np.zeros_like(ga)
    for j in range(a.shape[1]):
        ap, am = a[:8].copy(), a[:8].copy()
        ap[:, j] += h
        am[:, j] -= h
        fd[:, j] = (g.predict(s[:8], ap) - g.predict(s[:8], am)) / (2 * h)
    assert np.abs(ga - fd).max() < 1e-6


def test_sensitivity_direction_is_unit_norm(toy):
    s, a, y = toy
    g = fit(s, a, y, seed=SEED)
    u, mag = g.sensitivity_directions(s[:200], a[:200])
    norms = np.linalg.norm(u, axis=1)
    assert np.allclose(norms[mag > 1e-12], 1.0, atol=1e-6)


def test_insensitive_states_get_zero_direction():
    """민감도가 0인 상태에 임의 방향을 채워넣으면 없는 신호를 만들어낸다."""
    rng = np.random.default_rng(1)
    s, a = rng.normal(size=(200, 3)), rng.normal(size=(200, 2))
    g = fit(s, a, np.zeros(200), seed=SEED)      # 상수 타깃 -> 기울기 0
    u, mag = g.sensitivity_directions(s, a)
    assert np.allclose(u[mag <= 1e-12], 0.0)


def test_fit_is_deterministic(toy):
    s, a, y = toy
    assert fit(s, a, y, seed=SEED).model_hash == fit(s, a, y, seed=SEED).model_hash


def test_different_seed_changes_model(toy):
    s, a, y = toy
    assert fit(s, a, y, seed=SEED).model_hash != fit(s, a, y, seed=SEED + "x").model_hash


def test_phase_targets_monotone_and_bounded():
    t = phase_targets(10)
    assert t[0] > 0 and t[-1] == 1.0
    assert np.all(np.diff(t) >= 0)
    assert t.min() >= 0 and t.max() <= 1


def test_phase_targets_rejects_degenerate():
    with pytest.raises(ValueError):
        phase_targets(1)


def test_mismatched_lengths_raise(toy):
    s, a, y = toy
    with pytest.raises(ValueError, match="표본 수"):
        fit(s, a[:100], y, seed=SEED)


# ---- IG-2 ----

def test_ig2_blocks_non_train_episodes(manifest):
    """`g`는 train만으로 학습한다."""
    def loader(eid):
        rng = np.random.default_rng(abs(hash(eid)) % 2**32)
        return rng.normal(size=(30, 4)), rng.normal(size=(30, 3))

    with pytest.raises(IntegrityViolation, match="IG-2"):
        fit_from_episodes(manifest, manifest.ids("audit")[:1], loader, seed=SEED)


def test_ig2_allows_train_episodes(manifest):
    def loader(eid):
        rng = np.random.default_rng(abs(hash(eid)) % 2**32)
        return rng.normal(size=(30, 4)), rng.normal(size=(30, 3))

    g = fit_from_episodes(manifest, manifest.ids("train")[:5], loader, seed=SEED, n_features=32)
    assert g.state_dim == 4 and g.action_dim == 3
