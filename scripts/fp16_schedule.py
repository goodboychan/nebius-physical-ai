"""FP16 실기 순서표 (docs/fp16_real_arm_preregistration.md §3). 스트레스 순서표와 같은 방식, 셀마다 trial 수가 다르다(k + U)/n_c.
- 조건(S1, S4)마다 한 블록. 블록 안에서 4셀 × 12 trial을 (k + U)/n 키로 인터리브한다. 블록 순서도 시드에서 정한다
- 익명 토큰은 **새로** 만든다. G6 토큰↔셀 대응은 봉인 해제로 이미 공개되었기 때문이다(artifacts/trials/g6_unsealed/)
- 엔진은 LOCK-2의 같은 파일이다. 토큰 이름으로 링크하고 sha256을 봉인 파일에 남긴다
사용(리포 루트): python scripts/stress_schedule.py <출력 폴더>
출력: <out>/sealed/stress_sealed.json(조작자에게 보이지 않게 Orin ~/.edgeqgate_sealed/stress/로), <out>/stress_schedule_public.json"""
import hashlib, json, os, secrets, sys
import numpy as np
sys.path.insert(0, "src")
from edgeqgate.hashing import seed_from

CELLS = ["VC-025", "VC-000", "VC-002"]; NS = {"VC-025": 20, "VC-000": 10, "VC-002": 10}; CONDS = ["F0"]
out = sys.argv[1]; os.makedirs(f"{out}/sealed", exist_ok=True)
L = json.load(open("artifacts/freeze/lock2.json")); seed = L["arm_plan"]["seed"]
rng = np.random.default_rng(seed_from(seed, "FP16/schedule/v1", L["ranking_hash"]))
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
