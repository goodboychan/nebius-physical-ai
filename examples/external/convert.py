"""Turns raw.jsonl into trials.jsonl with the outcome decided by written rules, one per source status. The rules belong
to the source, not to QuantGate: read the source's own definition, write the rule here, and keep this file with the
results, because the rule changes the count.

  status                      outcome     why
  executed                    judge.success
  refused_before_execution    failure     the method's own checker refused the plan: the task was not done
  provider_error              failure     counted in the denominator, as the source's published totals do
                                          (use "drop" instead if your plan says a provider failure is not a trial)
Usage: python convert.py [raw.jsonl] [trials.jsonl]"""
import json, sys

RULES = {"executed": "judge", "refused_before_execution": "fail", "provider_error": "fail"}
src, dst = (sys.argv[1:] + ["raw.jsonl", "trials.jsonl"][len(sys.argv) - 1:])[:2]
out, count = [], {}
for n, line in enumerate(open(src), 1):
    r = json.loads(line); rule = RULES.get(r["status"])
    if rule is None: sys.exit(f"{src} line {n}: status {r['status']!r} has no rule; add one to RULES before counting")
    if rule == "drop": continue
    ok = r["judge"]["success"] if rule == "judge" else False
    if not isinstance(ok, bool): sys.exit(f"{src} line {n}: executed but judge.success is {ok!r}; fix the source or add a rule")
    out.append({"trial_id": r["attempt_id"], "task_id": r["task_id"], "config": r["config"], "success": ok, "rule": f"{r['status']} -> {rule}"})
    count[r["status"]] = count.get(r["status"], 0) + 1
open(dst, "w").write("".join(json.dumps(r) + "\n" for r in out))
print(f"{len(out)} trials written to {dst}; by status: {count}")
