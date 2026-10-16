"""Refit the wrist-roll offset and the jaw-gap point (gripper_link frame) on grasp moments from both demo sets
(LOCK-1, 120 at the mark; positions, 50 at -4..+4 cm), with the can position back-projected by the given camera.
The nominal demos alone barely vary the start or the roll, which left roll and gap point confounded: the fine-tune
policy and +3 cm trials came out 5-7 cm off (2026-10-16). Lift/elbow/wrist-flex stay at the measured values.
Usage: python sim/fit_roll_gap.py <calibration json> <camera json> <out calibration json>"""
import glob, json, os, sys
import av, cv2, numpy as np, pandas as pd
import xml.etree.ElementTree as ET
from scipy.optimize import least_squares
CAL, CAM, OUT = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
URDF = os.path.expanduser("~/edgeqgate_data/sim_assets/SO-ARM100/Simulation/SO101/so101_new_calib.urdf")
src = open("sim/fk_scene_estimate.py").read(); exec(src[src.index("def rpy"):src.index("def q_of")])
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]; base = np.deg2rad([CAL["joint_offsets_deg"].get(j, 0.0) for j in J])
R = np.array(CAM["R_world_to_cam"]); t = np.array(CAM["t_world_to_cam"]); f = CAM["focal_px"]; cam = -R.T @ t; Z0 = CAL["table_z"]
def backproj(u, v, z): r = R.T @ np.array([(u - 320) / f, (v - 240) / f, 1.0]); return cam + (z - cam[2]) / r[2] * r
start = np.array(CAL["start_xyz"][:2]); Q, C, SRC = [], [], []
for DS in (os.path.expanduser("~/edgeqgate_data/so101_demo"), os.path.expanduser("~/edgeqgate_data/ftpos")):
    E = pd.concat([pd.read_parquet(x) for x in sorted(glob.glob(f"{DS}/meta/episodes/chunk-*/*.parquet"))]); D = pd.concat([pd.read_parquet(x) for x in sorted(glob.glob(f"{DS}/data/chunk-*/*.parquet"))])
    K = "videos/observation.images.top"
    for vf, grp in E.groupby([K + "/chunk_index", K + "/file_index"]):
        want = {float(r[K + "/from_timestamp"]): int(r.episode_index) for _, r in grp.iterrows()}; got = {}
        c = av.open(f"{DS}/{K}/chunk-{int(vf[0]):03d}/file-{int(vf[1]):03d}.mp4"); st = c.streams.video[0]
        for fr in c.decode(st):
            tt = float(fr.pts * st.time_base)
            for t0, ep in want.items():
                if ep not in got and tt >= t0 - 1e-3: got[ep] = cv2.cvtColor(fr.to_ndarray(format="rgb24"), cv2.COLOR_RGB2GRAY)
            if len(got) == len(want): break
        c.close()
        for ep, g in got.items():
            cs = cv2.HoughCircles(cv2.medianBlur(g, 5), cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=100, param2=22, minRadius=17, maxRadius=28)
            cands = [backproj(x, y, Z0 + 0.115)[:2] for x, y, r in (cs[0] if cs is not None else []) if g[int(y), int(x)] > 90]
            cands = [p for p in cands if np.hypot(*(p - start)) < 0.09]
            if not cands: continue
            can = min(cands, key=lambda p: np.hypot(*(p - start)))
            S = np.stack(D[D.episode_index == ep]["observation.state"]); gs = S[:, 5]; op = np.where(gs > 45)[0]
            hold = [i for i in range(op[0], len(gs) - 30) if 10 < gs[i] < 45 and gs[i:i + 30].std() < 1.5] if len(op) else []
            if hold: Q.append(S[hold[0] + 15, :5]); C.append(can); SRC.append(os.path.basename(DS))
Q, C = np.array(Q), np.array(C); print("grasps:", len(Q), {s: SRC.count(s) for s in set(SRC)}, "roll range deg", np.round([Q[:, 4].min(), Q[:, 4].max()], 1))
def gaps(x):
    o = base.copy(); o[4] = x[0]; d = x[1:4]
    return np.array([(lambda G: G[:3, :3] @ d + G[:3, 3])(fk({n: np.deg2rad(q[k]) + o[k] for k, n in enumerate(J)} | {"gripper": 0.0}, "gripper_link")) for q in Q])
def res(x): G = gaps(x); return np.r_[(G[:, :2] - C).ravel() * 1000, (G[:, 2] - Z0 - x[4]) * 1000 / 3]
best = min((least_squares(res, np.r_[r0, 0.03, 0.0, -0.06, 0.06], bounds=([-np.pi * 2, -0.1, -0.1, -0.15, 0.0], [np.pi * 2, 0.12, 0.1, 0.0, 0.115]), loss="soft_l1", f_scale=10)
            for r0 in np.deg2rad(np.arange(-180, 180, 30))), key=lambda r: r.cost)
G = gaps(best.x); e = np.linalg.norm(G[:, :2] - C, axis=1) * 1000
for s in set(SRC): m = np.array(SRC) == s; print(s, "median xy error mm", round(float(np.median(e[m])), 1), "p90", round(float(np.percentile(e[m], 90)), 1))
out = dict(CAL); out["joint_offsets_deg"] = dict(CAL["joint_offsets_deg"]); out["joint_offsets_deg"]["wrist_roll"] = round(float(np.rad2deg(best.x[0])) % 360 if best.x[0] > np.pi else float(np.rad2deg(best.x[0])), 2)
out["jaw_centre_in_gripper_link_m"] = best.x[1:4].round(4).tolist(); out["grasp_height_m"] = round(float(best.x[4]), 4)
out["wrist_roll_source"] = f"refit on {len(Q)} grasps from both demo sets with {os.path.basename(sys.argv[2])}; median xy error {np.median(e):.1f} mm"
json.dump(out, open(OUT, "w"), indent=1); print("roll", out["joint_offsets_deg"]["wrist_roll"], "gap", out["jaw_centre_in_gripper_link_m"], "h", out["grasp_height_m"], "| all median", round(float(np.median(e)), 1))
