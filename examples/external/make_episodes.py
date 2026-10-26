"""Writes episodes.csv: a SYNTHETIC per-episode CSV in the shape some real-robot evaluations publish, for README.md.
Not real data. Four models, each recorded on its own days; text outcomes in a column named `eval.outcome`; episodes on
several objects and instructions, so a fair comparison has to filter to one condition first.
Usage: python make_episodes.py"""
import csv, random

rng = random.Random(1026)
p = {"openpi": 0.30, "gr00t": 0.22, "act": 0.21, "smolvla": 0.02}
rows = []
for m, (model, ps) in enumerate(p.items()):
    for k in range(40):
        obj = "spoons" if k % 4 else "towels"; instr = "put the spoons in the box" if obj == "spoons" else "fold the towel"
        u = rng.random()
        outcome = "Success" if u < ps else rng.choice(["Stalled", "Safety", "Timeout", "Partial"])
        rows.append({"episode_id": f"{model}-{k:03d}", "model": model, "object": obj, "instruction": instr, "start_objects": 3,
                     "recorded": f"2026-09-{10 + 3 * m + k // 20:02d}", "eval.outcome": outcome})
with open("episodes.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "episodes")
