"""Fit the twin's joint offsets from the touch calibration (scripts/so101_touch_calib.py, sim/README.md).
Unknowns: angle offsets for shoulder_lift, elbow_flex, wrist_flex (rad; the shoulder_pan offset is a gauge freedom,
equivalent to rotating the whole table about the base axis, so it is fixed at 0 and absorbed in the grid yaw); the touch-point offset along the
gripper frame's z (m); the A4 grid's pose on the table in the robot base frame (x, y, yaw).
Known: the table plane (z = -0.0024 m, the base bottom) and the grid geometry (3x3, 5 cm, G1 first, row by row).
Residual: FK touch point minus grid point, in 3D. START and COASTER come out as FK positions after the fit.
Usage: python sim/fit_touch_calib.py <urdf> <touch.json> <out.json>      (--selftest: recover known offsets from synthetic touches)"""
import json, sys
import numpy as np
import xml.etree.ElementTree as ET
from scipy.optimize import least_squares

URDF = sys.argv[1]
src = open(__file__.replace("fit_touch_calib.py", "fk_scene_estimate.py")).read(); exec(src[src.index("def rpy"):src.index("def q_of")])
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]; TABLE_Z = -0.0024
# grid spacing: --spacing overrides touch.json (the 2026-10-15 sheet was drawn at 3 cm, the recorder wrote its 5 cm default)
SP = float(sys.argv[sys.argv.index("--spacing") + 1]) if "--spacing" in sys.argv else (0.05 if "--selftest" in sys.argv else json.load(open(sys.argv[2])).get("grid_spacing_m", 0.05))
GRID = np.array([[(c - 1) * SP, (1 - r) * SP] for r in range(3) for c in range(3)])   # grid frame: G1 at (-SP, +SP)
# raised points: table touches alone cannot separate the lift/elbow/wrist offsets (selftest: errors up to 25 deg).
# So the can is stood on each corner dot and the centre of its top is touched twice, wrist tilted forward (F) and back (K).
# Its height comes from touch.json ("block_height_m", the unopened cola can: 0.115 m)


def tip(qdeg, off, tz):
    T = fk({n: np.deg2rad(qdeg[k]) + (off[k] if k < 4 else 0.0) for k, n in enumerate(J)} | {"gripper": 0.0})
    return T[:3, 3] + T[:3, 2] * tz


def world(g, idx, h):
    c, s = np.cos(g[2]), np.sin(g[2]); return np.c_[GRID[idx] @ np.array([[c, s], [-s, c]]) + g[:2], TABLE_Z + np.asarray(h)]


def fit(Q, idx, h):
    full = lambda p: np.r_[0.0, p[:3], p[3:]]   # pan offset fixed at 0
    def res(p): f = full(p); return (np.array([tip(q, f[:4], f[4]) for q in Q]) - world(f[5:8], idx, h)).ravel()
    d = np.deg2rad(30); best = None
    for yaw in np.linspace(-np.pi, np.pi, 8, endpoint=False):
        x0 = np.r_[np.zeros(3), 0.0, np.mean([tip(q, np.zeros(4), 0)[:2] for q in Q], 0), yaw]
        r = least_squares(res, x0, bounds=(np.r_[[-d] * 3, -0.05, -0.6, -0.6, -2 * np.pi], np.r_[[d] * 3, 0.05, 0.6, 0.6, 2 * np.pi]))
        if best is None or r.cost < best.cost: best = r
    best.x = full(best.x); return best


def plan(box_h):   # the touch list: 9 table dots, then the can top on the 4 corner dots, each wrist-forward (F) and wrist-back (K)
    L = [(f"G{i + 1}", i, 0.0, None) for i in range(9)]
    L += [(f"B{i + 1}{w}", i, box_h, w) for i in (0, 2, 6, 8) for w in ("F", "K")]
    return L


if "--selftest" in sys.argv:
    rng = np.random.default_rng(0); true = np.r_[np.deg2rad([0, -9, 7, -5]), 0.01, 0.20, -0.08, 0.3]; BOX = 0.115
    from scipy.optimize import minimize
    Q, idx, h = [], [], []
    for name, i, hh, w in plan(BOX):   # synthetic touches: IK under the true offsets, wrist pushed forward/back, 0.3 deg noise
        P = world(true[5:8], [i], [hh])[0]; wf = {None: 0.0, "F": 25.0, "K": -25.0}[w]
        f = lambda q: np.sum((tip(np.r_[q, 0], true[:4], true[4]) - P) ** 2) + 1e-4 * (q[3] - (60 + wf)) ** 2 * 1e-2
        q = minimize(f, np.array([0, 20, -20, 60.0 + wf]), method="Nelder-Mead", options={"xatol": 1e-7, "fatol": 1e-14, "maxiter": 40000}).x
        Q.append(np.r_[q, 0] + rng.normal(0, 0.3, 5)); idx.append(i); h.append(hh)
    r = fit(Q, idx, h); err = np.rad2deg(r.x[:4] - true[:4])
    print("selftest offset error (deg):", err.round(2), "| tip error mm:", round((r.x[4] - true[4]) * 1000, 1), "| rms residual mm:", round(float(np.sqrt(np.mean(r.fun ** 2))) * 1000, 2))
    sys.exit(0 if np.all(np.abs(err) < 4) else 1)   # 0.3 deg touch noise gives about 1-3 deg

T = json.load(open(sys.argv[2])); pts = {p["point"]: p["state_deg_mean"] for p in T["points"]}
# 2026-10-15 run: with the wrist tilted for the can-top touches, a different part of the gripper made contact (K touches
# read 28 cm high under any fit), so they do not fit the single-tip model. Default: fit the 9 table touches only, and
# check the fit on held-out touches (START and COASTER must come out at table height). --with-can adds the can-top touches.
L = [x for x in plan(T["block_height_m"]) if x[0] in pts and ("--with-can" in sys.argv or x[0].startswith("G"))]
print("touches used:", len(L), "of", len(plan(0)))
r = fit([pts[n][:5] for n, *_ in L], [i for _, i, _, _ in L], [hh for _, _, hh, _ in L]); p = r.x; per = np.linalg.norm(r.fun.reshape(-1, 3), axis=1)
R = {"joint_offsets_deg": dict(zip(J[:4], np.rad2deg(p[:4]).round(2).tolist())), "tip_offset_m": round(float(p[4]), 4),
     "grid_pose": {"xy_m": p[5:7].round(4).tolist(), "yaw_rad": round(float(p[7]), 4)}, "residual_mm": (per * 1000).round(1).tolist(),
     "rms_mm": round(float(np.sqrt(np.mean(per ** 2))) * 1000, 2), "table_z": TABLE_Z,
     **{k.lower() + "_xyz": tip(pts[k][:5], p[:4], p[4]).round(4).tolist() for k in ("START", "COASTER") if k in pts},
     "held_out_height_error_mm": {k: round(float(tip(pts[k][:5], p[:4], p[4])[2] - TABLE_Z) * 1000, 1) for k in ("START", "COASTER") if k in pts},
     "can_top_touch_height_m": {k: round(float(tip(v[:5], p[:4], p[4])[2] - TABLE_Z), 3) for k, v in pts.items() if k.startswith("B")},
     "fit_points": [n for n, *_ in L], "note": "table touches only; lift/elbow/wrist offsets are not uniquely identified by one plane, so the twin is validated at table height (held-out START/COASTER)"}
json.dump(R, open(sys.argv[3], "w"), indent=1); print(json.dumps(R, indent=1))
