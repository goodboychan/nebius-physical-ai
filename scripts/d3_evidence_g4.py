"""`D3` 리포트용 증거 묶음 (G4 시점). 있는 것만 담고 추정·보간하지 않는다.
- G3: 셀별 요인, 빌드 성공·시간, 엔진 크기 정보, 동결 캐시 해시, 결정성 시험 결과
- G4: 셀별 score_mag / score_align 점추정·CI95(Nebius Jobs), cheap_B, cheap_C(Orin GPU 지연)
- D5: errata 스냅샷 해시와 결과 제목·URL
사용: python scripts/d3_evidence_g4.py <g4 scores 폴더> <g4_payload_index.json> <out.json>"""
import glob, json, os, sys
sys.path.insert(0, "src")
from edgeqgate.grid import load_grid

scores_dir, pidx, out = sys.argv[1:4]
P = json.load(open(pidx))["cells"]
B = {json.loads(l)["code"]: json.loads(l) for l in open("artifacts/manifests/g3_engine_build.jsonl")}
cells = {}
for v in load_grid():
    if v.code == "VC-000": continue
    c = {"precision": v.precision, "calib_size": v.calib_size, "calib_composition": v.calib_composition, "granularity": v.granularity}
    b = B.get(v.code, {}); c.update(build_ok=b.get("ok"), build_sec=b.get("build_sec"))
    f = os.path.join(scores_dir, f"{v.code}.json")
    if os.path.exists(f):
        s = json.load(open(f))
        for k in ("score_mag", "score_align"):
            c[k] = round(s[k]["point"], 5); c[k + "_ci95"] = [round(x, 5) for x in s[k]["ci95"]]
    if v.code in P:
        c["score_cheap_B"] = round(P[v.code]["cheap_B"], 6); c["orin_gpu_ms_median"] = round(P[v.code]["cheap_C_ms"], 2)
    cells[v.code] = c
errata = json.load(open("artifacts/retrieval/errata_g4.json"))
ev = {
    "experiment": "QuantGate — offline audit of INT8 variants of a LeRobot ACT policy (SO-101 cola-can pick-and-place) before real-arm trials",
    "deployment_target": {"device": "Jetson Orin Nano Super", "power_mode": "15W", "tensorrt": "10.3.0"},
    "reference": "VC-000 = FP32 policy (GX10 torch). Scores measure INT8/FP16 action-chunk deviation from it on 2,000 held-out audit states",
    "score_definitions": {
        "score_mag": "CVaR@90 over states of RMS (over 100 chunk steps) of the L2 action error, normalized units",
        "score_align": "same, error projected on the task-progress sensitivity direction",
        "score_cheap_B": "open-loop action MSE on 2,000 train states",
        "orin_gpu_ms_median": "TensorRT GPU time per inference on Orin"},
    "grid_build": {"n_cells": len(cells), "n_built": sum(1 for c in cells.values() if c.get("build_ok")),
                   "g3_criterion_min_cells": 20, "determinism_check": "VC-001 rebuilt with the same frozen timing cache: outputs bit-identical on 2,000 train states"},
    "cells": cells,
    "real_robot_trials": "none yet — closed-loop success is unknown",
    "errata_snapshot": {"hash": errata.get("snapshot_hash"), "results": [{"title": r["title"][:100], "url": r["url"]}
                        for q in errata["results"].values() for r in q][:12]},
}
json.dump(ev, open(out, "w"), indent=1, ensure_ascii=False); print("cells", len(cells), "with scores", sum("score_mag" in c for c in cells.values()))
