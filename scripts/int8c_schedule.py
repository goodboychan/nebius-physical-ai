"""INT8 chatter block, amendment 3 (docs/fp16_real_arm_preregistration.md §9): block Q8, INT8 VC-002 against FP16 VC-025 at the training mark.
VC-002 24 / VC-025 24, interleaved by the (k + U)/n key. Seed key INT8/chatter/schedule/v1, new random tokens.
Usage (repo root): python scripts/int8c_schedule.py <out dir>
Output: <out>/sealed/stress_sealed.json (to Orin ~/.edgeqgate_sealed/stress_int8c/, never read by the operator or the assistant),
        <out>/stress_schedule_public.json"""
import hashlib, json, os, secrets, sys
import numpy as np
sys.path.insert(0, "src")
from edgeqgate.hashing import seed_from

CELLS = ["VC-002", "VC-025"]; NS = {"VC-002": 24, "VC-025": 24}; CONDS = ["Q8"]
out = sys.argv[1]; os.makedirs(f"{out}/sealed", exist_ok=True)
L = json.load(open("artifacts/freeze/lock2.json")); seed = L["arm_plan"]["seed"]
rng = np.random.default_rng(seed_from(seed, "INT8/chatter/schedule/v1", L["ranking_hash"]))
order = list(CONDS)
token = {c: secrets.token_hex(4) for c in CELLS}   # 시드와 무관한 난수 — 순서표에서 셀을 역추론할 수 없게
blocks = {}
for cond in order:
    ts = [{"cell": c, "k": k, "key": (k + rng.uniform()) / NS[c]} for c in CELLS for k in range(NS[c])]
    ts.sort(key=lambda t: (t["key"], rng.uniform())); blocks[cond] = ts
sealed = {"lock2_record_hash": L["record_hash"], "block_order": order, "token_to_cell": {v: k for k, v in token.items()},
          **{c: [{"trial": i + 1, "cell": t["cell"]} for i, t in enumerate(ts)] for c, ts in blocks.items()}}
sb = json.dumps(sealed, indent=1, sort_keys=True).encode()
open(f"{out}/sealed/stress_sealed.json", "wb").write(sb)
public = {"lock2_record_hash": L["record_hash"], "sealed_sha256": hashlib.sha256(sb).hexdigest(), "block_order": order,
          **{c: [{"trial": i + 1, "engine_token": token[t["cell"]]} for i, t in enumerate(ts)] for c, ts in blocks.items()}}
json.dump(public, open(f"{out}/stress_schedule_public.json", "w"), indent=1)
print("block order", order, "trials", {c: len(v) for c, v in blocks.items()}, "sealed_sha256", public["sealed_sha256"])
