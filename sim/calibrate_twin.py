"""Digital-twin calibration from real data (sim phase 1). No hand-placed numbers.
Observations, per teleop demo (LOCK-1 120 + position demos 50):
  - overhead pixel of the can top at the first frame (can at its start mark) and at the last frame (can on the coaster),
    by the same Hough circle detector as the success judge;
  - the follower joint state at the grasp (tightest grip in the first two thirds) and at the release (first clear opening).
Model: FK of the SO-ARM100 URDF with per-joint angle offsets (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex) on
LeRobot degrees; the can top is the gripper frame's xy at the grasp/release, at table height + 0.115 m (table = base
bottom, z = -0.0024 m); a pinhole camera (yaw/pitch/roll, position, focal length; principal point at the centre).
Fit: robust least squares of the pixel residuals, plus a soft term that the gripper z is the same at grasp and release.
Usage: python sim/calibrate_twin.py <urdf> <out.json> <dataset dir> [<dataset dir> ...]"""
import glob, json, sys
import av, cv2, numpy as np, pandas as pd
import xml.etree.ElementTree as ET
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation as Rot

URDF, OUT, DSS = sys.argv[1], sys.argv[2], sys.argv[3:]
src = open(__file__.replace("calibrate_twin.py", "fk_scene_estimate.py")).read()
exec(src[src.index("def rpy"):src.index("def q_of")])   # rpy, axis_rot, joint table, fk
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
CAN_H, TABLE_Z, W, H = 0.115, -0.0024, 640, 480


def can_top(gray, anchor, max_d=120):
    g = cv2.medianBlur(gray, 5)
    cs = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=100, param2=22, minRadius=17, maxRadius=28)
    best = None
    for x, y, r in (cs[0] if cs is not None else []):
        m = np.zeros_like(gray); cv2.circle(m, (int(x), int(y)), int(r * 0.7), 255, -1)
        d = float(np.hypot(x - anchor[0], y - anchor[1]))
        if gray[m > 0].mean() > 90 and d <= max_d and (best is None or d < best[2]): best = (float(x), float(y), d)
    return best


def frames_at(path, times):
    c = av.open(path); s = c.streams.video[0]; out = {}
    for f in c.decode(s):
        t = float(f.pts * s.time_base)
        for k, tt in times.items():
            if k not in out and t >= tt - 1e-3: out[k] = cv2.cvtColor(f.to_ndarray(format="rgb24"), cv2.COLOR_RGB2GRAY)
        if len(out) == len(times): break
    c.close(); return out


obs = []
for ds in DSS:
    E = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{ds}/meta/episodes/chunk-*/*.parquet"))])
    D = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{ds}/data/chunk-*/*.parquet"))])
    K = "videos/observation.images.top"
    for vf, grp in E.groupby([K + "/chunk_index", K + "/file_index"]):
        times = {}
        for _, r in grp.iterrows():
            times[(r.episode_index, 0)] = float(r[K + "/from_timestamp"]); times[(r.episode_index, 1)] = float(r[K + "/to_timestamp"]) - 2 / 30
        fr = frames_at(f"{ds}/{K}/chunk-{int(vf[0]):03d}/file-{int(vf[1]):03d}.mp4", times)
        for _, r in grp.iterrows():
            g = D[D.episode_index == r.episode_index]; S = np.stack(g["observation.state"]); gr = S[:, 5]
            ic = int(np.argmin(gr[: len(gr) * 2 // 3])); t = np.where(gr[ic:] > gr[ic] + 0.5 * (gr.max() - gr[ic]))[0]
            if not len(t) or (r.episode_index, 0) not in fr or (r.episode_index, 1) not in fr: continue
            a = can_top(fr[(r.episode_index, 0)], (241, 402), 140); b = can_top(fr[(r.episode_index, 1)], (371, 352), 60)
            if a and b: obs.append({"ds": ds, "ep": int(r.episode_index), "px0": a[:2], "px1": b[:2], "q0": S[ic, :5].tolist(), "q1": S[ic + t[0], :5].tolist()})
    print(ds, "episodes with both detections:", sum(o["ds"] == ds for o in obs), flush=True)

Q0 = np.array([o["q0"] for o in obs]); Q1 = np.array([o["q1"] for o in obs]); P0 = np.array([o["px0"] for o in obs]); P1 = np.array([o["px1"] for o in obs])


def grip(q, off):
    return fk({n: np.deg2rad(q[k]) + (off[k] if k < 4 else 0.0) for k, n in enumerate(J)} | {"gripper": 0.0})[:3, 3]


def project(X, cam):
    R = Rot.from_euler("zyx", cam[:3]).as_matrix(); t = cam[3:6]; f = cam[6]
    Xc = (X - t) @ R            # world -> camera (camera looks along +z, x right, y down)
    return np.stack([f * Xc[:, 0] / Xc[:, 2] + W / 2, f * Xc[:, 1] / Xc[:, 2] + H / 2], 1)


def resid(p):
    off, cam, h = p[:4], p[4:11], p[11]
    G0 = np.array([grip(q, off) for q in Q0]); G1 = np.array([grip(q, off) for q in Q1])
    X0 = np.c_[G0[:, :2], np.full(len(G0), TABLE_Z + CAN_H)]; X1 = np.c_[G1[:, :2], np.full(len(G1), TABLE_Z + CAN_H + 0.004)]
    rp = np.r_[(project(X0, cam) - P0).ravel(), (project(X1, cam) - P1).ravel()]
    rz = np.r_[G0[:, 2] - h, G1[:, 2] - h - 0.004] * 500    # 1 cm of height mismatch weighs like 5 px
    return np.r_[rp, rz]

# camera start: above the workspace, looking down (rotation x by pi), focal from the C922's ~70 degree horizontal field
# physical bounds: joint offsets within +-25 deg (a hand-set calibration pose), camera 0.4-1.5 m above the table and
# within 0.6 m of the base horizontally, focal 350-650 px, grasp height 2-10 cm
d = np.deg2rad(25)
lo = np.r_[[-d] * 4, [-np.pi, -np.pi / 2, -2 * np.pi], [-0.6, -0.6, 0.4], 350, 0.02]
hi = np.r_[[d] * 4, [np.pi, np.pi / 2, 2 * np.pi], [0.6, 0.6, 1.5], 650, 0.10]
x0 = np.r_[np.zeros(4), [0, 0, np.pi], [0.2, -0.1, 0.8], 457.0, 0.06]
best = None
for yaw in np.linspace(-np.pi, np.pi, 8, endpoint=False):
    for cx, cy in ((0.2, -0.1), (0.0, 0.0), (0.3, 0.1), (0.1, -0.3)):
        x = x0.copy(); x[4] = yaw; x[7], x[8] = cx, cy
        r = least_squares(resid, x, bounds=(lo, hi), loss="soft_l1", f_scale=8.0, max_nfev=300)
        if best is None or r.cost < best.cost: best = r
r = least_squares(resid, best.x, bounds=(lo, hi), loss="soft_l1", f_scale=8.0, max_nfev=3000); p = r.x
res = resid(p); n = len(obs); pix = np.hypot(*res[: 4 * n].reshape(-1, 2).T)
at_bound = [i for i in range(len(p)) if abs(p[i] - lo[i]) < 1e-4 or abs(p[i] - hi[i]) < 1e-4]
G0 = np.array([grip(q, p[:4]) for q in Q0]); G1 = np.array([grip(q, p[:4]) for q in Q1])
R_ = {"episodes": n, "joint_offsets_deg": dict(zip(J[:4], np.rad2deg(p[:4]).round(2).tolist())),
      "camera": {"euler_zyx_rad": p[4:7].round(4).tolist(), "position_m": p[7:10].round(4).tolist(), "focal_px": round(float(p[10]), 1), "image": [W, H]},
      "grasp_height_m": round(float(p[11]), 4), "pixel_residual_median": round(float(np.median(pix)), 2), "pixel_residual_p90": round(float(np.percentile(pix, 90)), 2),
      "start_mark_xy_median": np.median(G0[:, :2], 0).round(4).tolist(), "coaster_xy_median": np.median(G1[:, :2], 0).round(4).tolist(),
      "table_z": TABLE_Z, "can_height": CAN_H, "parameters_at_bound": at_bound}
json.dump(R_, open(OUT, "w"), indent=1); print(json.dumps(R_, indent=1))
