"""Writes seeds.csv: a SYNTHETIC before/after log on fixed seeds, for README.md. Not real data. 60 seeds, each run
by version `before` and `after`. `near_miss` is recorded only when an episode ends in success or timeout, and is empty
otherwise: empty means "not recorded", not "no near miss". Usage: python make_seeds.py"""
import csv, random

rng = random.Random(7615)
rows = []
for seed in range(60):
    for version, p in (("before", 0.40), ("after", 0.75)):
        u = rng.random()
        outcome = "success" if u < p else rng.choice(["collision", "dropped", "timeout"])
        nm = (rng.random() < (0.15 if version == "after" else 0.05)) if outcome in ("success", "timeout") else None
        rows.append({"run_id": f"{version}-{seed:03d}", "seed": seed, "version": version, "outcome": outcome,
                     "near_miss": "" if nm is None else str(nm).lower()})
with open("seeds.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "runs")
