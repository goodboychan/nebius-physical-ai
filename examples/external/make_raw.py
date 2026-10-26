"""Writes raw.jsonl: a SYNTHETIC log in the shape many external evaluations publish, for README.md. Not real data.
40 tasks, each run once by config 1 (baseline) and config 3 (the method), so the same task_id appears twice
(a paired design). Configs are numbers. judge.success is null when the run never reached the judge: the plan was
refused before execution, or the model provider failed. Usage: python make_raw.py"""
import json, random

rng = random.Random(26)
rows = []
for t in range(1, 41):
    for config, p in ((1, 0.40), (3, 0.65)):
        u = rng.random()
        status = "provider_error" if u < 0.04 else "refused_before_execution" if u < 0.12 else "executed"
        rows.append({"attempt_id": f"a{t:03d}-c{config}", "task_id": f"task{t:03d}", "config": config, "status": status,
                     "judge": {"success": (rng.random() < p) if status == "executed" else None}})
open("raw.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
print(len(rows), "rows;", {s: sum(r["status"] == s for r in rows) for s in ("executed", "refused_before_execution", "provider_error")})
