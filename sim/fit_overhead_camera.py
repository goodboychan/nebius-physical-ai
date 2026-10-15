"""Overhead camera pose for the twin from one photo of the touch-calibration grid (sim phase 1).
The 9 red dots are detected in the photo; their table positions come from the touch-calibration fit (grid pose in the
robot frame). One planar view gives the focal length (principal point fixed at the centre, no distortion) and the pose.
The dot order is matched over the 8 symmetries of a 3x3 grid by reprojection error.
Usage: python sim/fit_overhead_camera.py <grid photo> <twin_calibration.json> <spacing m> <out.json>"""
import itertools, json, sys
import cv2, numpy as np

IMG, CAL, SPm, OUT = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
im = cv2.imread(IMG); hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
red = cv2.inRange(hsv, (0, 90, 60), (10, 255, 255)) | cv2.inRange(hsv, (170, 90, 60), (180, 255, 255))
# only red inside the white sheet (books and cables elsewhere in the frame are red too)
white = cv2.inRange(hsv, (0, 0, 150), (180, 60, 255)); nw, lw, sw, cw = cv2.connectedComponentsWithStats(white)
# the sheet: the largest white region whose centre is in the lower half (the wall at the top-left is white too)
cand = [i for i in range(1, nw) if cw[i][1] > im.shape[0] / 2]; sheet = (lw == max(cand, key=lambda i: sw[i, cv2.CC_STAT_AREA])).astype(np.uint8)
sheet = cv2.morphologyEx(sheet, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8)); red = red & (sheet * 255)
n, lab, st, cen = cv2.connectedComponentsWithStats(red)
blobs = sorted([(st[i, cv2.CC_STAT_AREA], tuple(cen[i])) for i in range(1, n) if 4 <= st[i, cv2.CC_STAT_AREA] <= 400], reverse=True)
# keep the 9 blobs closest to their common median (the grid), ignoring other red things in the scene
pts = np.array([c for _, c in blobs]); med = np.median(pts, 0); pts = pts[np.argsort(np.linalg.norm(pts - med, axis=1))][:9]
assert len(pts) == 9, f"found {len(pts)} dots"
C = json.load(open(CAL)); g = C["grid_pose"]; x0, y0 = g["xy_m"]; yaw = g["yaw_rad"]; z = C["table_z"]
GRID = np.array([[(c - 1) * SPm, (1 - r) * SPm] for r in range(3) for c in range(3)])
cs, sn = np.cos(yaw), np.sin(yaw); W = np.c_[GRID @ np.array([[cs, sn], [-sn, cs]]) + [x0, y0], np.full(9, z)].astype(np.float32)
# sort detected dots into a 3x3 lattice in image order (rows by y, then x), then try the grid's 8 symmetries
P = pts[np.argsort(pts[:, 1])]; P = np.vstack([r[np.argsort(r[:, 0])] for r in P.reshape(3, 3, 2)]).astype(np.float32)
lat = np.arange(9).reshape(3, 3); syms = []
for k in range(4):
    for f in (False, True):
        m = np.rot90(lat, k); syms.append((np.fliplr(m) if f else m).ravel())
best = None; h, w = im.shape[:2]
# a 6 cm grid seen almost face-on does not determine the focal length (2026-10-15: calibrateCamera ran away to 2e9 px),
# so the focal is fixed to the C922's nominal 70.4 deg horizontal field at 640 px, and the coaster centre (judge
# constant, 395, 377 px; touched COASTER position) is added as a tenth point off the grid
F = (w / 2) / np.tan(np.deg2rad(70.42 / 2)); K = np.array([[F, 0, w / 2], [0, F, h / 2], [0, 0, 1]])
# plus two raised points that break the near-face-on mirror ambiguity: the can top at the start mark and on the coaster,
# median detections in the demo frames (241, 402) and (371, 352) px, at table + 0.115 m and + 0.119 m (coaster 4 mm)
s_, c_ = C["start_xyz"], C["coaster_xyz"]
Wc = np.array([c_, [s_[0], s_[1], z + 0.115], [c_[0], c_[1], z + 0.119]], np.float32)
Pc = np.array([[395.0, 377.0], [241.0, 402.0], [371.0, 352.0]], np.float32)
for s in syms:
    obj = np.vstack([W[s], Wc]).astype(np.float32); img = np.vstack([P, Pc]).astype(np.float32)
    ok, rv, tv = cv2.solvePnP(obj, img, K, None, flags=cv2.SOLVEPNP_SQPNP)
    ok, rv, tv = cv2.solvePnP(obj, img, K, None, rv, tv, useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
    proj = cv2.projectPoints(obj, rv, tv, K, None)[0].reshape(-1, 2); err = float(np.sqrt(np.mean(np.sum((proj - img) ** 2, 1))))
    if best is None or err < best[0]: best = (err, K, rv, tv, s, proj)
err, K, rv, tv, s, proj = best
R_cw = cv2.Rodrigues(rv)[0]; t_cw = tv.ravel()     # robot frame -> camera (points were given in the robot frame)
cam_pos = -R_cw.T @ t_cw
R = {"rms_px": round(float(err), 2), "focal_px": round(float(K[0, 0]), 1), "image": [w, h], "camera_position_m": cam_pos.round(4).tolist(),
     "R_world_to_cam": R_cw.round(6).tolist(), "t_world_to_cam": t_cw.round(5).tolist(), "dot_order": s.tolist(), "dots_px": P.round(1).tolist(), "residual_px": np.linalg.norm(proj - np.vstack([P, Pc]), axis=1).round(1).tolist(), "focal": "fixed, C922 nominal",
     "convention": "OpenCV camera: x right, y down, z forward"}
json.dump(R, open(OUT, "w"), indent=1); print(json.dumps({k: R[k] for k in ("rms_px", "focal_px", "camera_position_m")}))
