"""Render the twin at given LeRobot joint readings from the side, to check a measured pose by eye (sim phase 1).
Usage: sim/isaac.sh sim/render_pose.py <robot usd> <out.png> <deg,deg,deg,deg,deg> [sign,sign,sign,sign,sign] [offset_deg x5]"""
import sys
from isaacsim import SimulationApp
app = SimulationApp({"headless": True, "width": 640, "height": 480})
import numpy as np, omni.usd
from pxr import UsdPhysics
from isaacsim.core.api import World
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.stage import add_reference_to_stage
from isaacsim.sensors.camera import Camera
import isaacsim.core.utils.prims as pu
from PIL import Image
USD, OUT, Q = sys.argv[1], sys.argv[2], np.array([float(v) for v in sys.argv[3].split(",")])
SG = np.array([float(v) for v in sys.argv[4].split(",")]) if len(sys.argv) > 4 else np.ones(5)
OF = np.array([float(v) for v in sys.argv[5].split(",")]) if len(sys.argv) > 5 else np.zeros(5)
world = World(stage_units_in_meters=1.0); world.scene.add_default_ground_plane(z_position=-0.0024); stage = omni.usd.get_context().get_stage()
add_reference_to_stage(USD, "/World/so101"); fj = UsdPhysics.FixedJoint.Define(stage, "/World/so101/base_fixed"); fj.CreateBody1Rel().SetTargets(["/World/so101/Geometry/base_link"])
pu.create_prim("/World/Dome", "DomeLight", attributes={"inputs:intensity": 1200.0})
arm = world.scene.add(SingleArticulation(prim_path="/World/so101", name="so101"))
views = {"side": (np.array([0.15, -0.75, 0.12]), np.array([0.15, 0.0, 0.10])), "top": (np.array([0.15, 0.0, 0.9]), np.array([0.15, 0.0, 0.0]))}
cams = {k: Camera(prim_path=f"/World/cam_{k}", position=e, resolution=(640, 480), frequency=30) for k, (e, _) in views.items()}
world.reset(); arm.initialize()
from scipy.spatial.transform import Rotation as Rot
def look_at(eye, tgt):
    f = (tgt - eye) / np.linalg.norm(tgt - eye); up = np.array([0, 0, 1.0]) if abs(f[2]) < 0.99 else np.array([1.0, 0, 0])
    y = np.cross(up, f); y /= np.linalg.norm(y); z = np.cross(f, y); x, y_, z_, w = Rot.from_matrix(np.c_[f, y, z]).as_quat(); return np.array([w, x, y_, z_])
for k, (e, t) in views.items(): c = cams[k]; c.initialize(); c.set_clipping_range(0.01, 20); c.set_world_pose(position=e, orientation=look_at(e, t), camera_axes="world")
names = arm.dof_names; q = np.zeros(len(names))
for i, j in enumerate(["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]): q[names.index(j)] = np.deg2rad(SG[i] * Q[i] + OF[i])
for _ in range(5):
    arm.set_joint_positions(q); world.step(render=True)
im = np.hstack([cams["side"].get_rgba()[..., :3], cams["top"].get_rgba()[..., :3]]); Image.fromarray(im).save(OUT); print("saved", OUT)
app.close()
