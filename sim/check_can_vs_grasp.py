"""Per rollout: the can position back-projected from its first overhead frame vs the jaw-gap point at the real grasp
(first stable hold of the commanded gripper), under one calibration and camera. If these disagree by centimetres,
the replay places the can where the real jaws never went.
Usage: python sim/check_can_vs_grasp.py <calibration json> <camera json>"""
import csv, glob, json, os, sys
import av, cv2, numpy as np
import xml.etree.ElementTree as ET
CAL, CAM = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
URDF = os.path.expanduser("~/edgeqgate_data/sim_assets/SO-ARM100/Simulation/SO101/so101_new_calib.urdf")
src = open("sim/fk_scene_estimate.py").read(); exec(src[src.index("def rpy"):src.index("def q_of")])
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
off = np.deg2rad([CAL["joint_offsets_deg"].get(j, 0.0) for j in J]); d = np.array(CAL.get("jaw_centre_in_gripper_link_m", [0.063, 0, -0.04]))
R = np.array(CAM["R_world_to_cam"]); t = np.array(CAM["t_world_to_cam"]); f = CAM["focal_px"]; cam = -R.T @ t; Z0 = CAL["table_z"]
def backproj(u, v, z): r = R.T @ np.array([(u - 320) / f, (v - 240) / f, 1.0]); return cam + (z - cam[2]) / r[2] * r
start = np.array(CAL["start_xyz"][:2]); out = []
for ep in sorted(glob.glob(os.path.join(os.environ.get("EPISODE_BUNDLE", os.path.expanduser("~/edgeqgate_data/episode_bundle")), "rollout_*"))):
    rows = list(csv.DictReader(open(f"{ep}/trajectory.csv")))
    c = av.open(f"{ep}/video/top.mp4"); g = cv2.cvtColor(next(c.decode(video=0)).to_ndarray(format="rgb24"), cv2.COLOR_RGB2GRAY); c.close()
    cs = cv2.HoughCircles(cv2.medianBlur(g, 5), cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=100, param2=22, minRadius=17, maxRadius=28)
    cands = [backproj(x, y, Z0 + 0.115)[:2] for x, y, r in (cs[0] if cs is not None else []) if g[int(y), int(x)] > 90]
    can = min(cands, key=lambda p: np.hypot(*(p - start))) if cands else None
    gs = np.array([float(r["state.gripper"]) for r in rows]); op = np.where(gs > 45)[0]
    hold = [i for i in range(op[0], len(gs) - 30) if 10 < gs[i] < 45 and gs[i:i + 30].std() < 1.5] if len(op) else []
    if not hold or can is None: out.append((os.path.basename(ep), None)); continue
    q = [float(rows[hold[0] + 15][f"state.{j}"]) for j in J]
    G = fk({n: np.deg2rad(q[k]) + off[k] for k, n in enumerate(J)} | {"gripper": 0.0}, "gripper_link"); gap = G[:3, :3] @ d + G[:3, 3]
    # closest approach of the jaw gap to the can axis over the first 600 steps, and when, with the gripper reading then
    best = (1e9, None)
    for i in range(0, min(len(rows), 600)):
        qq = [float(rows[i][f"state.{j}"]) for j in J]; Gi = fk({n: np.deg2rad(qq[k]) + off[k] for k, n in enumerate(J)} | {"gripper": 0.0}, "gripper_link"); gp = Gi[:3, :3] @ d + Gi[:3, 3]
        dist = float(np.hypot(*(gp[:2] - can)))
        if gp[2] - Z0 < 0.12 and dist < best[0]: best = (dist, i, round(gs[i], 1), round(float(gp[2] - Z0) * 1000))
    out.append((os.path.basename(ep), round(float(np.hypot(*(gap[:2] - can))) * 1000), "hold@", hold[0] + 15, "| closest mm", round(best[0] * 1000), "@step", best[1], "grip", best[2], "z mm", best[3]))
for o in out: print(o)
v = [o[1] for o in out if o[1] is not None]; print("median gap-to-can mm", np.median(v) if v else None)
