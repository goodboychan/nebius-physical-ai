import numpy as np
import pytest

from edgeqgate.audit_buffer import build_buffer
from edgeqgate.grid import audited_variants
from edgeqgate.scores import rank_cells, score_cheap_A
from edgeqgate.splits import determine_splits

SEED = "PREREG-SEED-TEST"


@pytest.fixture
def episode_ids():
    return [f"ep{i:03d}" for i in range(120)]


@pytest.fixture
def manifest(episode_ids):
    return determine_splits(episode_ids, seed=SEED)


@pytest.fixture
def buffer(manifest, episode_ids):
    lengths = {e: 900 + (i * 7) % 600 for i, e in enumerate(episode_ids)}
    return build_buffer(manifest, lengths, seed=SEED)


@pytest.fixture
def rankings():
    """구조 검증용 가짜 순위. 실제 점수가 아니다."""
    cells = [v.code for v in audited_variants()]
    rng = np.random.default_rng(42)
    rk = {n: [str(c) for c in rng.permutation(cells)]
          for n in ("score_align", "score_mag", "score_cheap_B", "score_cheap_C")}
    rk["score_cheap_A"] = rank_cells({v.code: score_cheap_A(v).value for v in audited_variants()})
    return rk
