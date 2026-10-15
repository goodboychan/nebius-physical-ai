"""Live Cosmos C1 end-of-trial judge, scored prospectively on the fine-tune blocks (prereg §9, §14, §16).
Outcome: the unsealed trial success (consensus re-judge ∧ released ∧ no contact ∧ not aborted). The judge answered
YES/NO from the final overhead frame during the run; it was never used for outcomes.
Usage: python scripts/ft_live_judge.py <out.json>"""
import json, statistics, sys
sys.path.insert(0, "scripts")
from g6_analysis import wilson
B = {"T1": "artifacts/trials/ft_unsealed/stress_ft_T1_sealed.jsonl", "T0": "artifacts/trials/ft_unsealed/stress_ft_T0_sealed.jsonl",
     "T2": "artifacts/trials/ft2_unsealed/stress_ft2_T2_sealed.jsonl", "T0R": "artifacts/trials/ft3_unsealed/stress_ft3_T0R_sealed.jsonl"}
ans = lambda r: (r.get("d4_judge") or {}).get("answer")
by, allr = {}, []
for b, p in B.items():
    R = [json.loads(l) for l in open(p)]; allr += R
    f = [r for r in R if not r["success"]]; s = [r for r in R if r["success"]]
    by[b] = {"fail_caught": [sum(ans(r) == "NO" for r in f), len(f)], "false_alarm": [sum(ans(r) == "NO" for r in s), len(s)]}
f = [r for r in allr if not r["success"]]; s = [r for r in allr if r["success"]]
kc, kf = sum(ans(r) == "NO" for r in f), sum(ans(r) == "NO" for r in s)
lat = [r["d4_judge"].get("latency_ms") for r in allr if r.get("d4_judge") and r["d4_judge"].get("latency_ms") is not None]
out = {"prompt": "C1p1", "n": len(allr), "n_fail": len(f), "failure_recall": [kc, len(f), [round(x, 3) for x in wilson(kc, len(f))]],
       "false_alarm": [kf, len(s), [round(x, 3) for x in wilson(kf, len(s))]], "abstain": sum(ans(r) not in ("YES", "NO") for r in allr),
       "latency_ms_median": round(statistics.median(lat), 1) if lat else None, "by_block": by}
json.dump(out, open(sys.argv[1], "w"), indent=1); print(json.dumps(out))
