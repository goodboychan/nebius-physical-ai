"""Compare the twin's gripper pose in Isaac Sim with the URDF forward kinematics used for calibration (sim phase 1).
Sets a few joint vectors directly (no drives), reads the gripper_frame_link world pose from the stage, and prints both.
Usage: sim/isaac.sh sim/check_fk_vs_sim.py <robot usd> <urdf>"""
import sys
from isaacsim import SimulationApp
app = SimulationApp({"headless": True})
import numpy as np, xml.etree.ElementTree as ET
import omni.usd
from pxr import UsdGeom, Usd
from isaacsim.core.api import World
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.stage import add_reference_to_stage
USD, URDF = sys.argv[1:3]
src = open("sim/fk_scene_estimate.py").read(); exec(src[src.index("def rpy"):src.index("def q_of")])
world = World(stage_units_in_meters=1.0); stage = omni.usd.get_context().get_stage()
add_reference_to_stage(USD, "/World/so101")
from pxr import UsdPhysics
fj = UsdPhysics.FixedJoint.Define(stage, "/World/so101/base_fixed"); fj.CreateBody1Rel().SetTargets(["/World/so101/Geometry/base_link"])
arm = world.scene.add(SingleArticulation(prim_path="/World/so101", name="so101")); world.reset(); arm.initialize()
names = arm.dof_names
paths = {p.GetName(): p.GetPath() for p in stage.Traverse() if p.GetName() in ("gripper_frame_link", "gripper_link", "wrist_link", "base_link")}
print("dofs", names, "paths", {k: str(v) for k, v in paths.items()})
for qd in ([0, 0, 0, 0, 0], [30, 0, 0, 0, 0], [0, 30, 0, 0, 0], [0, 0, 30, 0, 0], [0, 0, 0, 30, 0], [10, 20, -30, 40, 0]):
    q = np.zeros(len(names))
    for k, j in enumerate(["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]): q[names.index(j)] = np.deg2rad(qd[k])
    arm.set_joint_positions(q); world.step(render=False)
    sim = {k: np.array(UsdGeom.Xformable(stage.GetPrimAtPath(paths[k])).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).ExtractTranslation()) for k in ("gripper_link", "gripper_frame_link") if k in paths}
    ref = fk({n: np.deg2rad(v) for n, v in zip(["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"], qd)} | {"gripper": 0.0}, "gripper_link")[:3, 3]
    print(qd, "sim gripper_link", sim.get("gripper_link", np.zeros(3)).round(4), "| urdf fk", ref.round(4), "| sim frame_link", sim.get("gripper_frame_link", np.full(3, np.nan)).round(4))
app.close()
