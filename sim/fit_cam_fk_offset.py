"""Planar frame correction between the overhead camera and the arm FK: fit a yaw + xy shift that maps camera-derived
can positions onto the FK jaw-gap point at the real grasp, over both demo sets (LOCK-1 at the mark, positions at
-4..+4 cm). Tried for each wrist-roll candidate with the measured jaw-gap point, so the roll is chosen by residual
rather than by which trials lift. The correction is applied to the camera pose, so --can-from-video uses it as is.
Usage: python sim/fit_cam_fk_offset.py <calibration json> <camera json> <out camera json> [roll deg ...]"""
import json, sys
import numpy as np
CAL_P, CAM_P, OUT_CAM = sys.argv[1:4]; ROLLS = [float(r) for r in sys.argv[4:]] or [-90.0, 88.0]
sys.argv = [sys.argv[0], CAL_P, CAM_P, "/dev/null"]
src = open("sim/fit_roll_gap.py").read(); exec(src[src.index("import glob"):src.index("def gaps(")])
d = np.array(CAL.get("jaw_centre_in_gripper_link_m", [0.063, 0, -0.04])); best = None
def gap_points(roll):
    o = base.copy(); o[4] = np.deg2rad(roll)
    return np.array([(lambda G: G[:3, :3] @ d + G[:3, 3])(fk({n: np.deg2rad(q[k]) + o[k] for k, n in enumerate(J)} | {"gripper": 0.0}, "gripper_link"))[:2] for q in Q])
def rigid(A, B):   # B ~ Rz A + s, robust: two passes dropping the worst 10%
    m = np.ones(len(A), bool)
    for _ in range(2):
        a, b = A[m] - A[m].mean(0), B[m] - B[m].mean(0); U, _, Vt = np.linalg.svd(a.T @ b); Rz = (U @ Vt).T
        if np.linalg.det(Rz) < 0: Vt[1] *= -1; Rz = (U @ Vt).T
        s = B[m].mean(0) - Rz @ A[m].mean(0); e = np.linalg.norm(A @ Rz.T + s - B, axis=1); m = e <= np.percentile(e, 90)
    return Rz, s, e
for roll in ROLLS:
    G = gap_points(roll); e0 = np.linalg.norm(C - G, axis=1) * 1000; Rz, s, e = rigid(C, G); e *= 1000
    yaw = np.degrees(np.arctan2(Rz[1, 0], Rz[0, 0])); per = {k: round(float(np.median(e[np.array(SRC) == k])), 1) for k in set(SRC)}
    print(f"roll {roll:+.0f}: before median {np.median(e0):.1f} mm | after yaw {yaw:+.2f} deg shift {np.round(s * 1000, 1)} mm median {np.median(e):.1f} p90 {np.percentile(e, 90):.1f} | per set {per}")
    if best is None or np.median(e) < best[0]: best = (float(np.median(e)), roll, Rz, s, yaw, per)
_, roll, Rz, s, yaw, per = best
R3 = np.eye(3); R3[:2, :2] = Rz; T = np.r_[s, 0.0]   # world' = R3 world + T; camera sees world' through R' = R R3^T
Rn = R @ R3.T; tn = t - Rn @ T
out = dict(CAM); out["R_world_to_cam"] = Rn.round(6).tolist(); out["t_world_to_cam"] = tn.round(5).tolist()
out["fk_correction"] = {"from": CAM_P, "calibration": CAL_P, "wrist_roll_deg": roll, "yaw_deg": round(yaw, 3), "shift_mm": np.round(s * 1000, 1).tolist(),
                        "median_mm": round(best[0], 1), "per_set_median_mm": per, "n_grasps": len(Q)}
json.dump(out, open(OUT_CAM, "w"), indent=1); print("chosen roll", roll, "->", OUT_CAM)
# Per-set fits: if each set alone fits well but they need different shifts, the camera (or the arm base) moved between sessions.
G = gap_points(roll)
for k in sorted(set(SRC)):
    m = np.array(SRC) == k; Rk, sk, ek = rigid(C[m], G[m])
    print(f"  {k}: own fit yaw {np.degrees(np.arctan2(Rk[1, 0], Rk[0, 0])):+.2f} deg shift {np.round(sk * 1000, 1)} mm median {np.median(ek) * 1000:.1f} p90 {np.percentile(ek, 90) * 1000:.1f}")
