"""SO-101 coaster task scene in Isaac Sim 6.2 (sim phase 1), plus a replay of one recorded demo's joint trajectory.
Geometry is provisional until the twin is calibrated: object positions from the URDF forward kinematics of the demos
(sim/scene_estimate.json, joint offsets not yet known), the coaster radius assumed 5 cm, the overhead camera placed by eye.
With --camera <fit_overhead_camera output>, the overhead camera takes the fitted pose and focal length. With --calib <fit_touch_calib output>, the joint offsets are applied and the can and coaster go to the touched START
and COASTER positions; with --every 1, every control step is rendered (frames for a side-by-side clip).
Usage: sim/isaac.sh sim/build_scene.py <robot usd> <scene_estimate.json> <episode trajectory.csv> <out dir> [--calib <json>] [--every N]"""
import json, os, sys
from isaacsim import SimulationApp
app = SimulationApp({"headless": True, "width": 640, "height": 480})
import numpy as np
from pxr import UsdPhysics, PhysxSchema, Sdf
import omni.usd
from isaacsim.core.api import World
from isaacsim.core.api.objects import DynamicCylinder, FixedCylinder
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.stage import add_reference_to_stage
from isaacsim.sensors.camera import Camera
import isaacsim.core.utils.prims as pu
from PIL import Image

USD, EST, TRAJ, OUT = sys.argv[1:5]; os.makedirs(OUT, exist_ok=True)
opt = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
est = json.load(open(EST)); start = np.array(est["start_mark_gripper_xyz_median"][:2]); coaster = np.array(est["coaster_release_gripper_xyz_median"][:2])
CAL = json.load(open(opt("--calib"))) if opt("--calib") else None; EVERY = int(opt("--every", 60))
OFF = np.zeros(5)
if CAL:
    OFF[:4] = np.deg2rad([CAL["joint_offsets_deg"][j] for j in ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex")])
    start, coaster = np.array(CAL["start_xyz"][:2]), np.array(CAL["coaster_xyz"][:2])
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
BASE_Z = 0.0024   # base bottom sits on the table (z = 0)

world = World(stage_units_in_meters=1.0, physics_dt=1 / 240, rendering_dt=1 / 30); world.scene.add_default_ground_plane()
stage = omni.usd.get_context().get_stage()
add_reference_to_stage(USD, "/World/so101")
root = stage.GetPrimAtPath("/World/so101")
pu.set_prim_attribute_value("/World/so101", "xformOp:translate", (0.0, 0.0, BASE_Z)) if root.GetAttribute("xformOp:translate") else None
# fix the base to the world
fj = UsdPhysics.FixedJoint.Define(stage, "/World/so101/base_fixed"); fj.CreateBody1Rel().SetTargets(["/World/so101/Geometry/base_link"])
for j in J:   # position drives, stiff like a hobby servo under LeRobot position control
    p = stage.GetPrimAtPath(f"/World/so101/Physics/{j}"); d = UsdPhysics.DriveAPI.Apply(p, "angular")
    d.CreateStiffnessAttr(2000.0 if j != "gripper" else 400.0); d.CreateDampingAttr(60.0); d.CreateMaxForceAttr(10.0)
world.scene.add(FixedCylinder(prim_path="/World/coaster", name="coaster", position=np.r_[coaster, 0.002], radius=0.05, height=0.004, color=np.array([0.85, 0.85, 0.8])))
can = world.scene.add(DynamicCylinder(prim_path="/World/can", name="can", position=np.r_[start, 0.0575], radius=0.033, height=0.115, mass=0.268, color=np.array([0.55, 0.05, 0.08])))
pu.create_prim("/World/Dome", "DomeLight", attributes={"inputs:intensity": 900.0})
pu.create_prim("/World/Key", "DistantLight", attributes={"inputs:intensity": 2500.0})
mid = (start + coaster) / 2
def look_at(eye, tgt):   # Isaac "world" camera axes: +X forward, +Z up -> quaternion (w, x, y, z)
    from scipy.spatial.transform import Rotation as Rot
    f = (tgt - eye) / np.linalg.norm(tgt - eye); up = np.array([0, 0, 1.0]) if abs(f[2]) < 0.99 else np.array([1.0, 0, 0])
    y = np.cross(up, f); y /= np.linalg.norm(y); z = np.cross(f, y)
    x, y_, z_, w = Rot.from_matrix(np.c_[f, y, z]).as_quat(); return np.array([w, x, y_, z_])
EYE, TGT = np.r_[mid + [0.10, 0.0], 0.75], np.r_[mid - [0.04, 0.0], 0.0]
cam = Camera(prim_path="/World/overhead", position=EYE, resolution=(640, 480), frequency=30)
arm = world.scene.add(SingleArticulation(prim_path="/World/so101", name="so101"))
world.reset(); cam.initialize(); arm.initialize()
cam.set_world_pose(position=EYE, orientation=look_at(EYE, TGT), camera_axes="world"); cam.set_clipping_range(0.01, 50.0)
if opt("--camera"):   # the fitted overhead camera (sim/fit_overhead_camera.py): OpenCV/ROS optical axes, pinhole focal in px
    from scipy.spatial.transform import Rotation as Rot
    CC = json.load(open(opt("--camera"))); Rcw = np.array(CC["R_world_to_cam"]); tcw = np.array(CC["t_world_to_cam"])
    x, y, z_, w = Rot.from_matrix(Rcw.T).as_quat(); AP = 20.955
    cam.set_world_pose(position=-Rcw.T @ tcw, orientation=np.array([w, x, y, z_]), camera_axes="ros")
    cam.set_horizontal_aperture(AP); cam.set_focal_length(CC["focal_px"] * AP / CC["image"][0]); cam.set_vertical_aperture(AP * 480 / 640)
for _ in range(10): world.step(render=True)
print("cam pose", [np.round(v, 3).tolist() for v in cam.get_world_pose(camera_axes="world")], "img mean", float(cam.get_rgba()[..., :3].mean()))
names = arm.dof_names; print("dofs", names)
idx = [names.index(j) for j in J]
import csv
traj = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(TRAJ))]
def q_of(row):   # LeRobot degrees -> URDF radians (no offsets yet); gripper 0..100 -> its joint range
    q = np.zeros(len(names))
    for k, j in enumerate(J[:5]): q[idx[k]] = np.deg2rad(row[f"state.{j}"]) + OFF[k]
    g = row["state.gripper"]; q[idx[5]] = -0.1745 + (1.745 + 0.1745) * g / 100.0; return q
arm.set_joint_positions(q_of(traj[0]))
for _ in range(60): world.step(render=True)
log, frames = [], []
for i, row in enumerate(traj):
    from isaacsim.core.utils.types import ArticulationAction
    arm.apply_action(ArticulationAction(joint_positions=q_of(row)))
    for _ in range(8): world.step(render=False)
    world.step(render=True)
    p, _ = can.get_world_pose(); log.append(p.tolist())
    if i % 200 == 0: print("step", i, "cmd", np.round(q_of(row)[idx], 2).tolist(), "got", np.round(arm.get_joint_positions()[idx], 2).tolist(), flush=True)
    if i % EVERY == 0 or i == len(traj) - 1:
        Image.fromarray(cam.get_rgba()[..., :3]).save(f"{OUT}/replay_{i:04d}.png")
json.dump({"can_xyz": log, "start": start.tolist(), "coaster": coaster.tolist()}, open(f"{OUT}/replay_log.json", "w"))
print("REPLAY DONE", len(traj), "can start", log[0], "can end", log[-1])
app.close()
