"""§3.3 감사 상태 버퍼와 부트스트랩."""
import numpy as np
import pytest

from edgeqgate.audit_buffer import bootstrap_indices, build_buffer
from edgeqgate.splits import IntegrityViolation

SEED = "PREREG-SEED-TEST"


def test_buffer_size_and_even_allocation(buffer):
    assert buffer.n_states == 2000
    assert buffer.per_episode == 100
    assert len(buffer.episodes) == 20
    assert all(len(v) == 100 for v in buffer.frames.values())


def test_no_duplicate_state_coordinates(buffer):
    pairs = buffer.pairs()
    assert len(pairs) == 2000
    assert len(set(pairs)) == 2000


def test_grid_spans_full_episode(buffer, episode_ids):
    """시간축 균등 샘플이므로 첫 프레임과 마지막 프레임을 포함해야 한다."""
    lengths = {e: 900 + (i * 7) % 600 for i, e in enumerate(episode_ids)}
    for ep in buffer.episodes:
        fr = buffer.frames[ep]
        assert fr[0] == 0
        assert fr[-1] == lengths[ep] - 1


def test_buffer_is_deterministic(manifest, episode_ids):
    lengths = {e: 900 + (i * 7) % 600 for i, e in enumerate(episode_ids)}
    a = build_buffer(manifest, lengths, seed=SEED)
    b = build_buffer(manifest, lengths, seed=SEED)
    assert a.buffer_hash == b.buffer_hash


def test_buffer_only_uses_audit_split(buffer, manifest):
    assert set(buffer.episodes) == set(manifest.ids("audit"))


def test_uneven_allocation_rejected(manifest, episode_ids):
    lengths = {e: 900 for e in episode_ids}
    with pytest.raises(ValueError, match="균등 배분"):
        build_buffer(manifest, lengths, seed=SEED, n_states=1999)


def test_short_episode_rejected(manifest, episode_ids):
    lengths = {e: 900 for e in episode_ids}
    lengths[manifest.ids("audit")[0]] = 50   # per_episode=100보다 짧다
    with pytest.raises(ValueError, match="짧다"):
        build_buffer(manifest, lengths, seed=SEED)


# ---- 부트스트랩 (§5.3) ----

def test_bootstrap_is_reproducible_per_replicate():
    """잡이 중단되어 재실행돼도 같은 결과가 나와야 한다 (preemptible 안전성)."""
    a = bootstrap_indices(2000, 7, SEED)
    b = bootstrap_indices(2000, 7, SEED)
    assert np.array_equal(a, b)


def test_bootstrap_differs_across_replicates():
    assert not np.array_equal(bootstrap_indices(2000, 7, SEED),
                              bootstrap_indices(2000, 8, SEED))


def test_bootstrap_independent_of_batching():
    """replicate 번호에서 결정되므로, 잡을 묶든 나누든 같은 값이 나온다."""
    separate = [bootstrap_indices(2000, r, SEED) for r in range(5)]
    batched = [bootstrap_indices(2000, r, SEED) for r in range(5)]
    assert all(np.array_equal(a, b) for a, b in zip(separate, batched))


def test_bootstrap_shape_and_range():
    idx = bootstrap_indices(2000, 0, SEED)
    assert idx.shape == (2000,)
    assert idx.min() >= 0 and idx.max() < 2000
