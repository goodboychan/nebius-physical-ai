"""Fine-tune demo order (docs/finetune_position_preregistration.md §2): 50 demos, 10 at each of 5 start positions along the
S1 axis (-4, -2, 0, +2, +4 cm; + is the S1 side), shuffled from a seed so that positions are interleaved over time.
+3 cm (the S1 mark) is held out for evaluation. Usage: python scripts/ft_demo_order.py > artifacts/finetune/demo_order.txt"""
import sys
import numpy as np
sys.path.insert(0, "src")
from edgeqgate.hashing import seed_from
pos = np.repeat([-4, -2, 0, 2, 4], 10)
order = np.random.default_rng(seed_from("PREREG-SEED-2026-09-14", "FINETUNE/positions/v1")).permutation(pos)
for i, p in enumerate(order): print(f"episode {i:02d}: start {p:+d} cm")
