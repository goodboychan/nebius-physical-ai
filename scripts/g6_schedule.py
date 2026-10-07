"""`G6` 실기 순서표 (§7.1, `IG-4`·`IG-5`·`IG-8`). LOCK-2 동결본의 arm 구성에서만 만든다.
- 본 세션: RETEST를 뺀 모든 arm(FP32 포함, IG-8)을 한 줄로 인터리브. 셀별 블록 실행 금지(IG-4).
  각 셀의 k번째 trial 키 = (k + U)/n_c 로 정렬해, 셀마다 trial이 시간축 전체에 고르게 퍼지게 한다(여러 날 저녁에 나눠 해도
  날짜·마모·조명 드리프트가 셀과 섞이지 않는다). U와 동순위는 커밋된 시드에서.
- RETEST: 별도 세션(다른 날) 20 trial
- 블라인딩(IG-5): 조작자에게는 trial 번호와 익명 엔진 토큰만 보인다. 셀↔토큰 대응은 sealed 파일에만 두고,
  그 해시를 지금 커밋한다. 봉인은 LOCK-3(실기 완료) 뒤에만 연다
사용(리포 루트): python scripts/g6_schedule.py <출력 폴더>"""
import hashlib, json, os, secrets, sys
import numpy as np
sys.path.insert(0, "src")
from edgeqgate.hashing import hash_obj, seed_from

out = sys.argv[1]; os.makedirs(f"{out}/sealed", exist_ok=True)
L = json.load(open("artifacts/freeze/lock2.json")); plan = L["arm_plan"]; seed = plan["seed"]
assert L["record_hash"].startswith("5fb513a4")
rng = np.random.default_rng(seed_from(seed, "G6/schedule", L["ranking_hash"]))
main, retest = [], []
for arm, cells in plan["arms"].items():
    for c in cells:
        n = plan["trials_per_cell"][arm]
        tgt = retest if arm == "ARM-RETEST" else main
        tgt += [{"arm": arm, "cell": c, "k": k, "key": (k + rng.uniform()) / n} for k in range(n)]
main.sort(key=lambda t: (t["key"], rng.uniform()))
rng.shuffle(retest)
cells = sorted({t["cell"] for t in main + retest})
token = {c: secrets.token_hex(4) for c in cells}  # 익명 토큰(시드와 무관한 난수 — 순서표에서 셀을 역추론할 수 없게)
def rows(ts, session):
    return [{"trial": i + 1, "session": session, "engine_token": token[t["cell"]]} for i, t in enumerate(ts)]
sealed = {"lock2_record_hash": L["record_hash"], "token_to_cell": {v: k for k, v in token.items()},
          "main": [{"trial": i + 1, "arm": t["arm"], "cell": t["cell"]} for i, t in enumerate(main)],
          "retest": [{"trial": i + 1, "arm": t["arm"], "cell": t["cell"]} for i, t in enumerate(retest)]}
sb = json.dumps(sealed, indent=1, sort_keys=True).encode()
open(f"{out}/sealed/g6_sealed.json", "wb").write(sb)
public = {"lock2_record_hash": L["record_hash"], "sealed_sha256": hashlib.sha256(sb).hexdigest(),
          "n_main": len(main), "n_retest": len(retest), "main": rows(main, "main"), "retest": rows(retest, "retest")}
json.dump(public, open(f"{out}/g6_schedule_public.json", "w"), indent=1)
print("main", len(main), "retest", len(retest), "sealed_sha256", public["sealed_sha256"])
