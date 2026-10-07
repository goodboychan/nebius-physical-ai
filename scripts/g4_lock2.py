"""`G4` → `LOCK-2`. Nebius Jobs의 셀별 점수를 모아 순위 5종을 만들고, 실기 arm을 결정한 뒤 동결 기록을 쓴다.
차등 검증: Jobs가 낸 점추정을 같은 상태별 벡터에서 로컬로 다시 계산해 1e-9 안에서 일치하지 않으면 멈춘다.
순위 규약: 오름차순, 1위 = 가장 안전하다고 예측(edgeqgate.scores). cheap_A는 요인만으로, cheap_B·C는 payload 색인에서.
사용(리포 루트): python scripts/g4_lock2.py <g4 폴더> [--dry-run]"""
import glob, json, os, sys
import numpy as np
sys.path.insert(0, "src")
from edgeqgate.grid import load_grid, by_code, ranked_variants
from edgeqgate.scores import upper_tail_stat, score_cheap_A, rank_cells, ranking_hash
from edgeqgate.arms import build_arms, coverage_report, format_coverage
from edgeqgate.splits import load_manifest
from edgeqgate.audit_buffer import build_buffer
from edgeqgate.freeze import create_lock2, write_lock2

SEED = "PREREG-SEED-2026-09-14"
g4 = sys.argv[1]; dry = "--dry-run" in sys.argv
idx = json.load(open(f"{g4}/g4_payload_index.json")); P = idx["cells"]
cells = [v.code for v in load_grid() if v.code != "VC-000"]
assert sorted(P) == sorted(cells), "payload 셀 목록이 그리드와 다르다"
mag, align = {}, {}
for c in cells:
    j = json.load(open(f"{g4}/scores/{c}.json")); z = np.load(f"{g4}/payload/{c}.npz")
    for name, store in (("mag", mag), ("align", align)):
        local = upper_tail_stat(z[name].astype(np.float64))
        if abs(local - j[f"score_{name}"]["point"]) > 1e-9:
            sys.exit(f"차등 검증 실패: {c} score_{name} Jobs {j[f'score_{name}']['point']} vs 로컬 {local}")
        store[c] = j[f"score_{name}"]["point"]
print("차등 검증 통과: 25셀 × 2점수, Jobs 점추정 = 로컬 재계산")
# 순위는 INT8 24셀로만 만든다(2026-10-07 결정 #5). VC-025(FP16)는 점수를 따로 보고한다.
R = [v.code for v in ranked_variants()]
pick = lambda d: {c: d[c] for c in R}
rankings = {
    "score_align": rank_cells(pick(align)), "score_mag": rank_cells(pick(mag)),
    "score_cheap_A": rank_cells({c: score_cheap_A(by_code(c)).value for c in R}),
    "score_cheap_B": rank_cells({c: P[c]["cheap_B"] for c in R}),
    "score_cheap_C": rank_cells({c: P[c]["cheap_C_ms"] for c in R}),
}
fp16 = {"VC-025": {"score_mag": mag["VC-025"], "score_align": align["VC-025"], "cheap_B": P["VC-025"]["cheap_B"],
                   "cheap_C_ms": P["VC-025"]["cheap_C_ms"]}}
print("VC-025(FP16, 순위 밖):", json.dumps(fp16["VC-025"]))
plan = build_arms(rankings, seed=SEED)
cov = coverage_report(plan, rankings)
print("ranking_hash", ranking_hash(rankings)[:16]); print(json.dumps(plan.arms, indent=1)); print(format_coverage(cov))
print("total trials", plan.total_trials())
if dry: sys.exit(0)
m = load_manifest("artifacts/manifests/lock1_split_manifest.yaml")
lengths = {f"ep{i:03d}": n for i, n in enumerate(json.load(open(f"{g4}/episode_lengths.json")))}
buf = build_buffer(m, lengths, SEED); assert buf.buffer_hash == idx["audit_buffer_hash"]
rec = create_lock2(rankings, plan, m, buf, coverage=cov, notes=[
    "점수: 100스텝 chunk 정의(decision_log 2026-10-07), Nebius Jobs 셀별 부트스트랩 200, 차등 검증 통과",
    "순위·arm은 INT8 24셀. VC-025(FP16)는 정밀도 축 대조로 따로: " + json.dumps(fp16["VC-025"]),
    f"g model_hash {idx['g_model_hash']}",
    "동결 timing cache 67fca693…, 엔진 출력 결정성 확인(attempt-029)",
    "CI는 빌드 분산을 포함하지 않는다 — 동결 캐시로 그 분산을 제거했다(manual_actions #14 a)"])
h = write_lock2(rec); print("LOCK-2 record_hash", h)
