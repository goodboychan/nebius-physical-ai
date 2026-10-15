"""Place the task objects in the SO-101 base frame from real data, not by guesswork (sim phase 1).
Forward kinematics of the follower URDF (SO-ARM100 so101_new_calib.urdf, zero = middle of range, as LeRobot's
calibration) on the teleop demos: the gripper frame at the grasp (gripper closing on the can) gives the start mark,
and at the release (gripper opening at the end) gives the coaster. Medians over episodes; spread is printed.
Usage: python sim/fk_scene_estimate.py <urdf> <LeRobot v3 dataset dir> <out.json>"""
import glob, json, sys
import numpy as np, pandas as pd
import xml.etree.ElementTree as ET

URDF, DS, OUT = sys.argv[1:4]
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]

def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr], [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr], [-sp, cp * sr, cp * cr]])

def axis_rot(a, t):
    a = a / np.linalg.norm(a); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K

joints = {}
for j in ET.parse(URDF).getroot().findall("joint"):
    o = j.find("origin"); ax = j.find("axis")
    joints[j.find("child").get("link")] = dict(name=j.get("name"), parent=j.find("parent").get("link"), type=j.get("type"),
        xyz=np.array([float(v) for v in (o.get("xyz", "0 0 0") if o is not None else "0 0 0").split()]),
        rpy=[float(v) for v in (o.get("rpy", "0 0 0") if o is not None else "0 0 0").split()],
        axis=np.array([float(v) for v in (ax.get("xyz") if ax is not None else "0 0 1").split()]))

def fk(q, link="gripper_frame_link"):
    chain = []
    while link in joints: chain.append(joints[link]); link = joints[link]["parent"]
    T = np.eye(4)
    for jt in reversed(chain):
        A = np.eye(4); A[:3, :3] = rpy(*jt["rpy"]); A[:3, 3] = jt["xyz"]; T = T @ A
        if jt["type"] == "revolute":
            R = np.eye(4); R[:3, :3] = axis_rot(jt["axis"], q[jt["name"]]); T = T @ R
    return T

def q_of(deg):   # LeRobot degrees (body joints) -> URDF radians; gripper is not needed for the gripper frame
    return {n: np.deg2rad(d) for n, d in zip(J[:5], deg[:5])} | {"gripper": 0.0}

E_ = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{DS}/meta/episodes/chunk-*/*.parquet"))])
D = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{DS}/data/chunk-*/*.parquet"))])
grasp, release = [], []
for ep, g in D.groupby("episode_index"):
    S = np.stack(g["observation.state"]); gr = S[:, 5]
    i_close = int(np.argmin(gr[: len(gr) * 2 // 3]))           # tightest grip in the first two thirds: holding the can
    t_open = np.where(gr[i_close:] > gr[i_close] + 0.5 * (gr.max() - gr[i_close]))[0]
    if not len(t_open): continue
    i_rel = i_close + int(t_open[0])                            # first clear opening after the grasp: the release
    i_grasp = i_close - int(np.argmax((gr[:i_close][::-1] > gr[i_close] + 0.5 * (gr[:i_close].max() - gr[i_close])))) if i_close else 0
    grasp.append(fk(q_of(S[i_grasp]))[:3, 3]); release.append(fk(q_of(S[i_rel]))[:3, 3])
grasp, release = np.array(grasp), np.array(release)
R = {"urdf": URDF, "dataset": DS, "episodes": len(grasp), "frame": "robot base_link, metres",
     "start_mark_gripper_xyz_median": np.median(grasp, 0).round(4).tolist(), "start_mark_iqr": (np.percentile(grasp, 75, 0) - np.percentile(grasp, 25, 0)).round(4).tolist(),
     "coaster_release_gripper_xyz_median": np.median(release, 0).round(4).tolist(), "coaster_iqr": (np.percentile(release, 75, 0) - np.percentile(release, 25, 0)).round(4).tolist(),
     "start_to_coaster_m": float(np.linalg.norm(np.median(release, 0)[:2] - np.median(grasp, 0)[:2]))}
json.dump(R, open(OUT, "w"), indent=1); print(json.dumps(R, indent=1))
