"""What one QuantGate review cost, from committed records only, against the brute-force route to the same evidence.
Sources:
  artifacts/cost/jobs.json                 Nebius Jobs (both projects), created/started/finished per job
  artifacts/cost/endpoint_operations.json  Cosmos AI Endpoint start/stop operations
  Token Factory usage: errata runs (measured usage), the model comparison (measured), D3 report runs (estimated from
  characters / 4 where usage was not stored), D4 replay and the Cosmos re-evaluation are endpoint time, not tokens
  real-arm trial logs (artifacts/trials/*): trial-ID timestamps give each session's wall time
Prices (list, on-demand, checked 2026-10-15): L40S (Intel) $1.55/GPU-h; Intel CPU instance from $0.06/h
(cpu-d3 2vcpu-8gb); Nemotron 3 Super on Token Factory $0.30 / $0.90 per 1M input / output tokens; Managed MLflow
medium $0.48/h. Job billing is assumed from creation to finish (it includes provisioning); this is an upper bound.
Usage: python scripts/review_cost.py [--out artifacts/reports]"""
import argparse, datetime as dt, glob, json, os, re

ap = argparse.ArgumentParser(); ap.add_argument("--out", default="artifacts/reports"); a = ap.parse_args()
P = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")[:26] + "+00:00") if s else None
PRICE = {"gpu-l40s-a": 1.55, "cpu-d3": 0.06, "tf_in": 0.30e-6, "tf_out": 0.90e-6, "mlflow": 0.48}

# 1. Nebius Jobs
jobs = json.load(open("artifacts/cost/jobs.json")); J = {}
for j in jobs:
    a0, b = P(j["created_at"]), P(j["finished_at"]); s = P(j["started_at"])
    if not (a0 and b): continue
    kind = "training (L40S)" if j["platform"].startswith("gpu") and j["name"].startswith("act-") and "smoke" not in j["name"] else (
           "smoke tests (L40S)" if j["platform"].startswith("gpu") else "offline audit fan-out (CPU)")
    e = J.setdefault(kind, {"jobs": 0, "run_s": 0.0, "billed_s": 0.0, "usd": 0.0}); e["jobs"] += 1
    e["run_s"] += (b - s).total_seconds() if s else 0; e["billed_s"] += (b - a0).total_seconds()
    e["usd"] += (b - a0).total_seconds() / 3600 * PRICE[j["platform"]]

# 2. Cosmos endpoint uptime (start op creation to the next stop op's finish; failed starts excluded)
ops = sorted(json.load(open("artifacts/cost/endpoint_operations.json")), key=lambda o: o["created_at"]); up, t_on = 0.0, None
for o in ops:
    if o["description"] in ("Create endpoint", "Start endpoint") and not o["error"]: t_on = P(o["created_at"])
    elif o["description"] == "Stop endpoint" and t_on: up += (P(o["finished_at"]) - t_on).total_seconds(); t_on = None
EP = {"sessions": sum(1 for o in ops if o["description"] in ("Create endpoint", "Start endpoint") and not o["error"]), "hours": up / 3600, "usd": up / 3600 * PRICE["gpu-l40s-a"]}

# 3. Token Factory
tf = {"in": 0, "out": 0, "calls": 0, "estimated_calls": 0}
for f in ("artifacts/reports/errata_grounded_v1.json", "artifacts/reports/errata_grounded.json"):
    for r in json.load(open(f))["rows"]:
        u = r.get("usage") or {}; tf["in"] += u.get("prompt_tokens", 0) or 0; tf["out"] += u.get("completion_tokens", 0) or 0; tf["calls"] += 1
for r in json.load(open("artifacts/reports/d3_model_compare.json"))["results"]:
    tf["in"] += r.get("prompt_tokens", 0) or 0; tf["out"] += r.get("completion_tokens", 0) or 0; tf["calls"] += 1
for f in sorted(glob.glob("artifacts/reports/d3_report_v3*run.json")) + ["artifacts/reports/d3_report_v2_run.json"]:
    R = json.load(open(f)); T = json.load(open("artifacts/reports/d3_v3_verdicts.json" if "v3" in f else "artifacts/reports/d3_v2_verdicts.json"))
    for att in R.get("attempts", [{"text": R.get("text", "")}]):
        tf["in"] += len(json.dumps(T, indent=1)) // 4 + 600; tf["out"] += len(att.get("text", "")) // 4 * 3; tf["calls"] += 1; tf["estimated_calls"] += 1   # reasoning tokens ~2x the visible text
TF = {**tf, "usd": tf["in"] * PRICE["tf_in"] + tf["out"] * PRICE["tf_out"]}

# 4. Real-arm sessions: trial-ID timestamps, sessions split at gaps > 30 min, +70 s for the last trial of each
ts = []
for f in glob.glob("artifacts/trials/**/*sealed.jsonl", recursive=True):
    for l in open(f):
        r = json.loads(l); m = re.search(r"_(\d{4})_(\d{6})$", r["trial_id"])
        if m: ts.append(dt.datetime.strptime("2026" + m.group(1) + m.group(2), "%Y%m%d%H%M%S"))
ts = sorted(set(ts)); spans, start = [], ts[0]
for x, y in zip(ts, ts[1:] + [None]):
    if y is None or (y - x).total_seconds() > 1800: spans.append((start, x)); start = y
arm_h = sum((b - a0).total_seconds() + 70 for a0, b in spans) / 3600; n_trials = len(ts); per_trial_min = arm_h * 60 / n_trials

MLF = {"hours": 1.5, "usd": 1.5 * PRICE["mlflow"]}
cloud = sum(v["usd"] for v in J.values()) + EP["usd"] + TF["usd"] + MLF["usd"]

# 5. Brute force to the same decision-grade question: every candidate vs FP32 at 10 pp (about 110-120 trials per arm)
n_cand = 25; per_arm = 115; bf_trials = (n_cand + 1) * per_arm; bf_h = bf_trials * per_trial_min / 60
R = {"prices_usd": PRICE, "nebius_jobs": J, "cosmos_endpoint": EP, "token_factory": TF, "mlflow": MLF, "cloud_total_usd": cloud,
     "real_arm": {"trials": n_trials, "sessions": len(spans), "hours": arm_h, "minutes_per_trial": per_trial_min},
     "brute_force_settle_all": {"candidates": n_cand, "trials_per_arm": per_arm, "trials": bf_trials, "arm_hours": bf_h},
     "note": "Job cost assumes billing from creation to finish (an upper bound). Token Factory D3 calls are estimated from text length."}
json.dump(R, open(f"{a.out}/review_cost.json", "w"), indent=1)
L = ["# What one QuantGate review cost", "", "From committed records (`scripts/review_cost.py`). List prices, on demand, checked 2026-10-15.", "",
     "| Item | Use | Cost (USD) |", "|---|---|---|"]
for k, v in J.items(): L.append(f"| Nebius Jobs · {k} | {v['jobs']} jobs · {v['run_s'] / 3600:.2f} h running, {v['billed_s'] / 3600:.2f} h incl. provisioning | {v['usd']:.2f} |")
L += [f"| Nebius AI Endpoint · Cosmos-Reason2 (L40S) | {EP['sessions']} sessions · {EP['hours']:.1f} h up | {EP['usd']:.2f} |",
      f"| Nebius Token Factory · Nemotron 3 Super | {TF['calls']} calls · {TF['in'] / 1e3:.0f}k in / {TF['out'] / 1e3:.0f}k out tokens ({TF['estimated_calls']} estimated; a lower bound, since early report runs did not log usage) | {TF['usd']:.2f} |",
      f"| Nebius Managed MLflow | {MLF['hours']} h | {MLF['usd']:.2f} |", f"| **Cloud total** | | **{cloud:.2f}** |", "",
      f"Real arm: **{n_trials} trials** in {len(spans)} sessions, **{arm_h:.1f} h** of operator time (about {per_trial_min:.1f} min per trial).", "",
      f"For scale, not as a saving: settling approval for every candidate ({n_cand} candidates and FP32 at about {per_arm} trials per arm) "
      f"would be **{bf_trials:,} trials, about {bf_h:.0f} arm-hours**, before any stress or position test. The two numbers answer different "
      "goals, because this review did not settle approval.", "",
      f"What the {n_trials} trials produced: a cost-favoured candidate to validate first (FP16), two miscalibrated builds blocked at the input "
      "check, two weak conditions found (grip, start position), the position weakness fixed and re-tested (+75 pp and +67 pp at ±3 cm), "
      "an AI judge validated live (22/24), and a list of the trials still missing before approval. It did not settle approval; that still "
      "needs the trials it lists."]
open(f"{a.out}/review_cost.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))
