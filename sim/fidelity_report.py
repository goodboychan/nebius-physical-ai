"""Sim-to-real outcome agreement for the unassisted physics replay (exploratory, sim/README.md).
Sim success: the can ends upright (tilt < 15 deg from the trace, or its centre height on the coaster) with its centre
within 50 mm of the coaster centre. Real outcome: episode.json in the LabLens bundle (consensus re-judge rule).
Conditions differ by block (gripper pads, rubber bands, start position); the sim uses one rubber-band setting, so the
pads-removed trial is expected to disagree.
Usage: python sim/fidelity_report.py <fidelity out dir> <out.json>"""
import glob, json, math, os, sys
OUT, DST = sys.argv[1:3]; L = os.path.expanduser("~/edgeqgate_data/lablens/lablens_so101_episodes"); rows = []
for d in sorted(glob.glob(f"{OUT}/rollout_*/replay_log.json")):
    eid = d.split("/")[-2]; R = json.load(open(d)); c = R["can_xyz"][-1]; co = R["coaster"]
    ep = json.load(open(f"{L}/{eid}/episode.json")); real = bool(ep["outcome"]["success"])
    dist = math.hypot(c[0] - co[0], c[1] - co[1]) * 1000; upright = c[2] > 0.05
    sim = upright and dist < 50; mz = max(p[2] for p in R["can_xyz"])
    rows.append({"episode": eid, "block": ep.get("block"), "gripper": ep.get("gripper"), "real_success": real, "sim_success": sim, "agree": sim == real,
                 "sim_end_mm_from_coaster": round(dist), "sim_upright": upright, "sim_max_lift_m": round(mz, 3), "operator_note": ep.get("operator_note")})
n = len(rows); agree = sum(r["agree"] for r in rows)
S = {"n": n, "agree": agree, "real_success": sum(r["real_success"] for r in rows), "sim_success": sum(r["sim_success"] for r in rows),
     "confusion": {f"real {a} / sim {b}": sum(r["real_success"] == a and r["sim_success"] == b for r in rows) for a in (True, False) for b in (True, False)}, "rows": rows}
json.dump(S, open(DST, "w"), indent=1)
print(f"agreement {agree}/{n}", S["confusion"])
for r in rows: print(("OK  " if r["agree"] else "DIFF"), r["episode"], "real", r["real_success"], "sim", r["sim_success"], f'{r["sim_end_mm_from_coaster"]} mm', "upright" if r["sim_upright"] else "down", "lift", r["sim_max_lift_m"], "|", (r["gripper"] or "")[:20])
