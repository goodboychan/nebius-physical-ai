"""Stress v2 offline re-judge (protocol §9, amendment 2026-10-12). Applies the same rule to every v2 trial.

Why: the live judge's "still" test fails a can that is standing still when the circle detector jumps to a wrong circle
in one or two of the last 15 frames. In v2 the can tends to sit about 20 px off the coaster center (rubber-band grasp,
inside the 35 px target), and a bright circle on the coaster rim or logo then competes with the can top. The
operator saw S0 trials 3, 5 and 6 standing on the coaster, but they were judged "moving". The rule was fixed blind to
cells.

Rule: the locked geometry of success_criterion §3 (target 35 px, the same detector, the same offsets, and the S4 can
values when given). The one change is in stillness: at most 3 of the last 15 frames may lie more than 8 px from the
median (80th percentile ≤ 8 px), instead of all 15. Frames come from the saved overhead video, converted
RGB → gray as the runner does. Effect on G6, checked before this rule was adopted (offline, every video): no outcome
changes. The only effect is that the strict rule's spurious offline failure on main052 is not repeated. That trial
was a success live.

Output: {trial_id: {"success_geom": bool, "reason", "base_dist_px", "move_p80", "n_outlier_frames"}}
Usage: python stress_rejudge.py <trials dir> <out.json> [can_profile.json]"""
import glob, json, os, sys
import av, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from judge_success import can_top, COASTER_XY, COASTER_R, CAN_R_RANGE, CAN_TOP_TO_BASE, STILL_PX, LAST_N

MAX_OUT = 3
tdir, outp = sys.argv[1:3]
prof = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
rr = tuple(prof["r_range"]) if prof else CAN_R_RANGE; off = tuple(prof["top_to_base"]) if prof else CAN_TOP_TO_BASE
res = {}
for p in sorted(glob.glob(f"{tdir}/*_top.mp4")):
    tid = os.path.basename(p)[:-len("_top.mp4")]
    c = av.open(p); fr = []
    for f in c.decode(c.streams.video[0]):
        fr.append(f); fr = fr[-LAST_N:]
    c.close()
    tops = [can_top(cv2.cvtColor(f.to_ndarray(format="rgb24"), cv2.COLOR_RGB2GRAY), rr, off) for f in fr]
    if any(t is None for t in tops):
        res[tid] = {"success_geom": False, "reason": "can_top_not_found(fallen_or_occluded)"}; continue
    xy = np.array([(t[0], t[1]) for t in tops]); med = np.median(xy, 0); d = np.linalg.norm(xy - med, axis=1)
    dist = float(np.hypot(med[0] + off[0] - COASTER_XY[0], med[1] + off[1] - COASTER_XY[1]))
    inside, still = dist <= COASTER_R, int((d > STILL_PX).sum()) <= MAX_OUT
    res[tid] = {"success_geom": bool(inside and still),
                "reason": "ok" if inside and still else ",".join(n for n, v in [("outside", inside), ("moving", still)] if not v),
                "base_dist_px": round(dist, 1), "move_p80": round(float(np.percentile(d, 80)), 1), "n_outlier_frames": int((d > STILL_PX).sum())}
json.dump(res, open(outp, "w"), indent=1)
print(len(res), "trials;", sum(v["success_geom"] for v in res.values()), "geometric successes")
