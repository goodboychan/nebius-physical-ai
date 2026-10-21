"""Fine-tune v2 demo order (docs/finetune_position_preregistration.md §21, amendment 9): 50 demos, the yellow can 5 at each
of -4, -2, 0, +2, +4 cm and the cola can 13 at +5 cm and 12 at +7 cm, shuffled from a seed so that conditions are
interleaved over time. The yellow can at +3 cm and the cola can at +6 cm are held out for evaluation.
Usage: python scripts/ft_demo_order2.py > artifacts/finetune/demo_order2.txt"""
import sys
import numpy as np
sys.path.insert(0, "src")
from edgeqgate.hashing import seed_from
eps = [("yellow can", p) for p in (-4, -2, 0, 2, 4) for _ in range(5)] + [("cola can", 5)] * 13 + [("cola can", 7)] * 12
order = np.random.default_rng(seed_from("PREREG-SEED-2026-09-14", "FINETUNE/positions/v2")).permutation(len(eps))
for i, j in enumerate(order): print(f"episode {i:02d}: {eps[j][0]:10s} start {eps[j][1]:+d} cm")
