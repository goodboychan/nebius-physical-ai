"""Second calibration stage for the twin: pin the lift/elbow/wrist offsets with grasp moments (sim phase 1).
Table touches alone leave a one-parameter family (sim/fit_touch_calib.py), which put the gripper about 5 cm off at
grasp height (T0 trial 1, 2026-10-15). Here every teleop demo adds one constraint at grasp height:
  - the can's real position: its top circle in the first overhead frame, back-projected with the fitted camera to the
    plane table + 0.115 m;
  - the grasp state (the first stable hold after the gripper opens).
Model: the can axis passes through a fixed point between the jaws, at d in the gripper_link frame (3 unknowns), at a
common grasp height h. Fit jointly with the 9 table touches (the touch point at gripper_frame_link + tz).
--fix-d x,y,z fixes the jaw-gap point (gripper_link frame) from the meshes instead of fitting it: fitted freely it absorbs
kinematic error (lateral 6.7 cm, 2026-10-15). From the meshes at the hold angle the gap centre is about (0.03, 0, -0.085).
Usage: python sim/fit_grasp_calib.py <urdf> <touch.json> <twin_calibration.json> <twin_camera.json> <dataset dir> <out.json> [--fix-d x,y,z]"""
import glob, json, sys
import av, cv2, numpy as np, pandas as pd
import xml.etree.ElementTree as ET
from scipy.optimize import least_squares
URDF, TOUCH, CAL, CAM, DS, OUT = sys.argv[1:7]
src = open(__file__.replace("fit_grasp_calib.py", "fk_scene_estimate.py")).read(); exec(src[src.index("def rpy"):src.index("def q_of")])
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
Cal, Cm, T = json.load(open(CAL)), json.load(open(CAM)), json.load(open(TOUCH)); Z0 = Cal["table_z"]
R = np.array(Cm["R_world_to_cam"]); t = np.array(Cm["t_world_to_cam"]); f = Cm["focal_px"]; cam = -R.T @ t
def backproj(u, v, z): d = R.T @ np.array([(u - 320) / f, (v - 240) / f, 1.0]); return cam + (z - cam[2]) / d[2] * d

# table touches (same grid model as fit_touch_calib)
SP = 0.03; pts = {p["point"]: p["state_deg_mean"] for p in T["points"]}
GRID = np.array([[(c - 1) * SP, (1 - r) * SP] for r in range(3) for c in range(3)])
g = Cal["grid_pose"]; cs, sn = np.cos(g["yaw_rad"]), np.sin(g["yaw_rad"])
GW = np.c_[GRID @ np.array([[cs, sn], [-sn, cs]]) + g["xy_m"], np.full(9, Z0)]; QG = [pts[f"G{i}"][:5] for i in range(1, 10)]

# demo grasps
E = pd.concat([pd.read_parquet(x) for x in sorted(glob.glob(f"{DS}/meta/episodes/chunk-*/*.parquet"))])
D = pd.concat([pd.read_parquet(x) for x in sorted(glob.glob(f"{DS}/data/chunk-*/*.parquet"))])
K = "videos/observation.images.top"; QS, CANS = [], []
for vf, grp in E.groupby([K + "/chunk_index", K + "/file_index"]):
    want = {float(r[K + "/from_timestamp"]): int(r.episode_index) for _, r in grp.iterrows()}; got = {}
    c = av.open(f"{DS}/{K}/chunk-{int(vf[0]):03d}/file-{int(vf[1]):03d}.mp4"); st = c.streams.video[0]
    for fr in c.decode(st):
        tt = float(fr.pts * st.time_base)
        for t0, ep in want.items():
            if ep not in got and tt >= t0 - 1e-3: got[ep] = cv2.cvtColor(fr.to_ndarray(format="rgb24"), cv2.COLOR_RGB2GRAY)
        if len(got) == len(want): break
    c.close()
    for ep, gray in got.items():
        gm = cv2.medianBlur(gray, 5); circ = cv2.HoughCircles(gm, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=100, param2=22, minRadius=17, maxRadius=28)
        cand = [(x, y) for x, y, r in (circ[0] if circ is not None else []) if gray[int(y), int(x)] > 90 and np.hypot(x - 241, y - 402) < 60]
        if not cand: continue
        u, v = min(cand, key=lambda p: np.hypot(p[0] - 241, p[1] - 402))
        S = np.stack(D[D.episode_index == ep]["observation.state"]); gr = S[:, 5]
        # the hold: after the first clear opening (> 45), the first 30-step plateau between 10 and 45 (closed on the can;
        # an empty closed gripper reads about 1, which an argmin over the episode picks by mistake)
        op = np.where(gr > 45)[0]
        if not len(op): continue
        hold = [i for i in range(op[0], len(gr) - 30) if 10 < gr[i] < 45 and gr[i:i + 30].std() < 1.5]
        if not hold: continue
        ic = hold[0] + 15
        QS.append(S[ic, :5]); CANS.append(backproj(u, v, Z0 + 0.115)[:2])
QS, CANS = np.array(QS), np.array(CANS); print("demo grasps:", len(QS), flush=True)

def T_of(q, off, link): return fk({n: np.deg2rad(q[k]) + (off[k] if k < len(off) else 0.0) for k, n in enumerate(J)} | {"gripper": 0.0}, link)
ROLL = "--fit-roll" in sys.argv   # wrist_roll offset: it moves the off-axis jaw gap sideways, which table touches cannot see
FIX_D = np.array([float(v) for v in sys.argv[sys.argv.index("--fix-d") + 1].split(",")]) if "--fix-d" in sys.argv else None
def res(p):
    off = np.r_[0.0, p[:3], p[8] if ROLL else 0.0]; tz, d, h = p[3], (FIX_D if FIX_D is not None else p[4:7]), p[7]
    rt = []
    for q, w in zip(QG, GW):
        T_ = T_of(q, off, "gripper_frame_link"); rt.append((T_[:3, 3] + T_[:3, 2] * tz - w) * 1000)
    rg = []
    for q, c in zip(QS, CANS):
        T_ = T_of(q, off, "gripper_link"); jc = T_[:3, :3] @ d + T_[:3, 3]; rg.append(np.r_[jc[:2] - c, jc[2] - (Z0 + h)] * 1000 / 3)   # grasp terms: 3 mm ~ 1 mm of touch
    return np.r_[np.ravel(rt), np.ravel(rg)]
dg = np.deg2rad(40); best = None
for d0 in ([0, 0, -0.06], [0, -0.02, -0.08], [0.02, 0, -0.05]):
  for roll0 in ((-0.6, -0.3, 0.0, 0.3, 0.6) if ROLL else (0.0,)):
    x0 = np.r_[np.deg2rad(Cal["joint_offsets_deg"]["shoulder_lift"]), np.deg2rad(Cal["joint_offsets_deg"]["elbow_flex"]), np.deg2rad(Cal["joint_offsets_deg"]["wrist_flex"]), Cal["tip_offset_m"], d0, 0.05, roll0]
    r = least_squares(res, x0, bounds=(np.r_[[-dg] * 3, -0.05, -0.15, -0.15, -0.15, 0.0, -1.6], np.r_[[dg] * 3, 0.05, 0.15, 0.15, 0.15, 0.115, 1.6]), loss="soft_l1", f_scale=10)
    if best is None or r.cost < best.cost: best = r
p = best.x; rr = res(p); print("wrist_roll offset deg:", round(float(np.rad2deg(p[8])), 2) if ROLL else 0.0); tt = np.linalg.norm(rr[:27].reshape(-1, 3), axis=1); gg = np.linalg.norm(rr[27:].reshape(-1, 3) * 3, axis=1)
off = np.r_[0.0, p[:3], p[8] if ROLL else 0.0]
held = {k: round(float((T_of(pts[k][:5], off, "gripper_frame_link")[:3, 3] + T_of(pts[k][:5], off, "gripper_frame_link")[:3, 2] * p[3])[2] - Z0) * 1000, 1) for k in ("START", "COASTER")}
out = dict(Cal); out.update({"joint_offsets_deg": dict(zip(J[:len(off)], np.rad2deg(off).round(2).tolist())), "tip_offset_m": round(float(p[3]), 4),
    "jaw_centre_in_gripper_link_m": (FIX_D if FIX_D is not None else p[4:7]).round(4).tolist(), "jaw_centre_fixed": FIX_D is not None, "grasp_height_m": round(float(p[7]), 4), "touch_residual_mm_rms": round(float(np.sqrt(np.mean(tt ** 2))), 1),
    "grasp_residual_mm_median": round(float(np.median(gg)), 1), "grasp_residual_mm_p90": round(float(np.percentile(gg, 90)), 1), "demo_grasps": len(QS),
    "held_out_height_error_mm": held,
    "start_xyz": (T_of(pts["START"][:5], off, "gripper_frame_link")[:3, 3]).round(4).tolist(), "coaster_xyz": (T_of(pts["COASTER"][:5], off, "gripper_frame_link")[:3, 3]).round(4).tolist(),
    "note": "stage 2: table touches + 120 demo grasps (can position from the overhead camera)"})
json.dump(out, open(OUT, "w"), indent=1); print(json.dumps({k: out[k] for k in ("joint_offsets_deg", "tip_offset_m", "jaw_centre_in_gripper_link_m", "grasp_height_m", "touch_residual_mm_rms", "grasp_residual_mm_median", "grasp_residual_mm_p90", "held_out_height_error_mm")}, indent=1))
