"""Stage 3 twin calibration from directly measured poses (sim/README.md). No fitting of the joint offsets.
EXTENDED: the arm straight out and level = the zero of SO-ARM100's so101_old_calib.urdf. The new-calibration URDF angles
of that pose are found by matching every link's world pose between the two URDFs; offset = URDF angle - LeRobot reading.
Gripper: GRIP_CLOSED and GRIP_CAN readings map to the closed jaw (-0.1745 rad, the jaw on the fixed finger in the
meshes) and to the jaw resting on the 66 mm can (0.778 rad, measured in sim/check_grip_contact.py).
Then the stage-1/2 data become checks: the 9 table touches (grid pose refit only), START/COASTER heights, and the jaw
gap point vs the camera can position at 111 demo grasps.
Usage: python sim/fit_pose_calib.py <urdf dir> <poses touch.json> <touch.json> <twin_calibration.json> <twin_camera.json> <dataset> <out.json>"""
import glob, json, sys
import av, cv2, numpy as np, pandas as pd
import xml.etree.ElementTree as ET
from scipy.optimize import least_squares
UD, POSES, TOUCH, CAL, CAM, DS, OUT = sys.argv[1:8]
src = open(__file__.replace("fit_pose_calib.py", "fk_scene_estimate.py")).read()
def load(urdf):
    g = {"np": np, "ET": ET, "URDF": urdf}; exec(src[src.index("def rpy"):src.index("def q_of")], g); return g
NEW, OLD = load(f"{UD}/so101_new_calib.urdf"), load(f"{UD}/so101_old_calib.urdf")
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
# 2026-10-16: matching against so101_old_calib.urdf failed (its base and link frames differ beyond joint zeros: 64 mm
# residual). A render of the measured pose with zero offsets showed the arm nearly straight, so the extended pose is
# defined directly in the new URDF: the shoulder_lift->elbow, elbow->wrist and wrist->tip lines are all level.
# wrist_roll is not constrained by "level" and keeps a zero offset; shoulder_pan stays the gauge (0).
P = {p["point"]: np.array(p["state_deg_mean"]) for p in json.load(open(POSES))["points"]}
fkN = NEW["fk"]
def level_err(o3):
    o = np.r_[0.0, o3, 0.0]; q = {n: np.deg2rad(P["EXTENDED"][k]) + o[k] for k, n in enumerate(J)} | {"gripper": 0.0}
    pts_ = [fkN(q, L)[:3, 3] for L in ("upper_arm_link", "lower_arm_link", "wrist_link")]
    T_ = fkN(q, "gripper_frame_link"); pts_.append(T_[:3, 3])
    return np.array([pts_[i + 1][2] - pts_[i][2] for i in range(3)]) * 1000
from scipy.optimize import least_squares as LS
lv = min((LS(level_err, np.array(x0)) for x0 in ([0, 0, 0], [0.4, -0.4, 0], [-0.4, 0.4, 0], [0, 0.5, -0.5])), key=lambda r: r.cost)
print("level residual mm", lv.fun.round(2))
off = np.r_[0.0, lv.x, 0.0]
g0, g1, a0, a1 = P["GRIP_CLOSED"][5], P["GRIP_CAN"][5], -0.1745, 0.778
grip = {"reading_closed": round(float(g0), 2), "reading_can": round(float(g1), 2), "rad_per_unit": round((a1 - a0) / (g1 - g0), 5), "rad_at_zero": round(a0 - g0 * (a1 - a0) / (g1 - g0), 4)}
print("offsets (deg):", dict(zip(J, np.rad2deg(off).round(2))), "| gripper", grip)
# checks with the stage-1/2 data
fk = NEW["fk"]; T = json.load(open(TOUCH)); pts = {p["point"]: p["state_deg_mean"] for p in T["points"]}; Cal = json.load(open(CAL)); Z0 = Cal["table_z"]
def Tm(q, link): return fk({n: np.deg2rad(q[k]) + off[k] for k, n in enumerate(J)} | {"gripper": 0.0}, link)
tipz = lambda q, tz: Tm(q, "gripper_frame_link")[:3, 3] + Tm(q, "gripper_frame_link")[:3, 2] * tz
SP = 0.03; GRID = np.array([[(c - 1) * SP, (1 - r) * SP] for r in range(3) for c in range(3)])
def gres(x):
    c, s = np.cos(x[2]), np.sin(x[2]); W = np.c_[GRID @ np.array([[c, s], [-s, c]]) + x[:2], np.full(9, Z0)]
    return (np.array([tipz(pts[f"G{i}"][:5], x[3]) for i in range(1, 10)]) - W).ravel() * 1000
gb = min((least_squares(gres, np.r_[0.28, -0.02, y, 0.0]) for y in np.linspace(-np.pi, np.pi, 8, endpoint=False)), key=lambda r: r.cost)
touch_rms = float(np.sqrt(np.mean(np.linalg.norm(gb.fun.reshape(-1, 3), axis=1) ** 2)))
held = {k: round(float(tipz(pts[k][:5], gb.x[3])[2] - Z0) * 1000, 1) for k in ("START", "COASTER")}
print("check: 9 table touches with these offsets (grid pose refit only): rms", round(touch_rms, 1), "mm | START/COASTER height", held, "mm")
Cm = json.load(open(CAM)); R = np.array(Cm["R_world_to_cam"]); t = np.array(Cm["t_world_to_cam"]); f = Cm["focal_px"]; cam = -R.T @ t
def backproj(u, v, z): d = R.T @ np.array([(u - 320) / f, (v - 240) / f, 1.0]); return cam + (z - cam[2]) / d[2] * d
E_ = pd.concat([pd.read_parquet(x) for x in sorted(glob.glob(f"{DS}/meta/episodes/chunk-*/*.parquet"))]); D = pd.concat([pd.read_parquet(x) for x in sorted(glob.glob(f"{DS}/data/chunk-*/*.parquet"))])
K = "videos/observation.images.top"; GQ, GC = [], []
for vf, grp in E_.groupby([K + "/chunk_index", K + "/file_index"]):
    want = {float(r[K + "/from_timestamp"]): int(r.episode_index) for _, r in grp.iterrows()}; got = {}
    c = av.open(f"{DS}/{K}/chunk-{int(vf[0]):03d}/file-{int(vf[1]):03d}.mp4"); st = c.streams.video[0]
    for fr in c.decode(st):
        tt = float(fr.pts * st.time_base)
        for t0, ep in want.items():
            if ep not in got and tt >= t0 - 1e-3: got[ep] = cv2.cvtColor(fr.to_ndarray(format="rgb24"), cv2.COLOR_RGB2GRAY)
        if len(got) == len(want): break
    c.close()
    for ep, gray in got.items():
        circ = cv2.HoughCircles(cv2.medianBlur(gray, 5), cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=100, param2=22, minRadius=17, maxRadius=28)
        cand = [(x, y) for x, y, r in (circ[0] if circ is not None else []) if gray[int(y), int(x)] > 90 and np.hypot(x - 241, y - 402) < 60]
        S = np.stack(D[D.episode_index == ep]["observation.state"]); gr = S[:, 5]; op = np.where(gr > 45)[0]
        hold = [i for i in range(op[0], len(gr) - 30) if 10 < gr[i] < 45 and gr[i:i + 30].std() < 1.5] if len(op) else []
        if not cand or not hold: continue
        u, v = min(cand, key=lambda p: np.hypot(p[0] - 241, p[1] - 402)); can = backproj(u, v, Z0 + 0.115)[:2]
        GQ.append(S[hold[0] + 15, :5]); GC.append(can)
# wrist_roll: "level" does not fix it, and a roll error moves the off-axis jaw gap up or sideways. It is the one offset
# taken from the demo grasps (1 parameter: the jaw gap must sit on the can axis; its height is free)
def gap(q, o): G = fk({n: np.deg2rad(q[k]) + o[k] for k, n in enumerate(J)} | {"gripper": 0.0}, "gripper_link"); return G[:3, :3] @ np.array([0.03, 0.0, -0.085]) + G[:3, 3]
def rres(x):
    o = off.copy(); o[4] = x[0]; Gp = np.array([gap(q, o) for q in GQ]); return np.r_[(Gp[:, :2] - np.array(GC)).ravel(), (Gp[:, 2] - Z0 - x[1]) ] * 1000
rb = min((least_squares(rres, np.r_[r0, 0.06], loss="soft_l1", f_scale=10) for r0 in np.deg2rad(np.arange(-180, 180, 30))), key=lambda r: r.cost)
off[4] = rb.x[0]; Gp = np.array([gap(q, off) for q in GQ]); xy = np.linalg.norm(Gp[:, :2] - np.array(GC), axis=1) * 1000
errs = np.c_[xy, (Gp[:, 2] - Z0) * 1000]
print("wrist_roll offset from grasps:", round(float(np.rad2deg(rb.x[0])), 1), "deg; can-axis height of the gap", round(float(rb.x[1]) * 1000, 1), "mm")
print("check: jaw gap vs camera can position at", len(errs), "demo grasps: xy error median", round(float(np.median(errs[:, 0])), 1), "mm, p90", round(float(np.percentile(errs[:, 0], 90)), 1), "| gap height median", round(float(np.median(errs[:, 1])), 1), "mm")
out = dict(Cal); out.update({"joint_offsets_deg": dict(zip(J, np.rad2deg(off).round(2).tolist())), "wrist_roll_source": "demo grasps (1 parameter)", "tip_offset_m": round(float(gb.x[3]), 4), "gripper_map": grip,
    "grid_pose": {"xy_m": gb.x[:2].round(4).tolist(), "yaw_rad": round(float(gb.x[2]), 4)}, "check_touch_rms_mm": round(touch_rms, 1), "held_out_height_error_mm": held,
    "check_grasp_xy_mm_median": round(float(np.median(errs[:, 0])), 1), "check_grasp_height_mm_median": round(float(np.median(errs[:, 1])), 1),
    "jaw_centre_in_gripper_link_m": [0.03, 0.0, -0.085], "start_xyz": tipz(pts["START"][:5], gb.x[3]).round(4).tolist(), "coaster_xyz": tipz(pts["COASTER"][:5], gb.x[3]).round(4).tolist(),
    "note": "stage 3: offsets measured directly (extended pose = old-calibration zero); stage-1/2 data are checks"})
json.dump(out, open(OUT, "w"), indent=1)

if "--free-gap" in sys.argv:   # diagnostic: with the measured lift/elbow/wrist offsets fixed, fit roll + the gap (x, z) + height
    def fres(x):
        o = off.copy(); o[4] = x[0]; d = np.array([x[1], 0.0, x[2]])
        Gp = []
        for q in GQ:
            G = fk({n: np.deg2rad(q[k]) + o[k] for k, n in enumerate(J)} | {"gripper": 0.0}, "gripper_link"); Gp.append(G[:3, :3] @ d + G[:3, 3])
        Gp = np.array(Gp); return np.r_[(Gp[:, :2] - np.array(GC)).ravel(), Gp[:, 2] - Z0 - x[3]] * 1000
    fb = min((least_squares(fres, np.r_[r0, 0.0, -0.08, 0.06], bounds=([-4, -0.06, -0.14, 0], [4, 0.08, 0.0, 0.115]), loss="soft_l1", f_scale=10) for r0 in np.deg2rad(np.arange(-180, 180, 30))), key=lambda r: r.cost)
    e = np.linalg.norm(fb.fun[: 2 * len(GQ)].reshape(-1, 2), axis=1)
    print("free gap: roll", round(float(np.rad2deg(fb.x[0])), 1), "deg, gap x", round(fb.x[1], 4), "z", round(fb.x[2], 4), "height", round(fb.x[3], 4), "| xy error median", round(float(np.median(e)), 1), "mm")
