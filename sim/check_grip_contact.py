"""Isolate the grasp physics (sim phase 1): hold the arm still at a grasp pose, put the can where the jaw gap is (from
the meshes), close the gripper and see whether the can blocks the jaw and whether it lifts with the arm.
Usage: sim/isaac.sh sim/check_grip_contact.py <robot usd> <twin_calibration json> [--mu F] [--grip-offset RAD]"""
import json, sys
from isaacsim import SimulationApp
app = SimulationApp({"headless": True})
import numpy as np
import omni.usd
from pxr import UsdPhysics, PhysxSchema, UsdShade, UsdGeom, Usd
from isaacsim.core.api import World
from isaacsim.core.api.objects import DynamicCylinder
from isaacsim.core.api.materials import PhysicsMaterial
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.stage import add_reference_to_stage
from isaacsim.core.utils.types import ArticulationAction
USD, CAL = sys.argv[1], json.load(open(sys.argv[2])); opt = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
MU, GOFF = opt("--mu", 1.0), opt("--grip-offset", 0.0)
world = World(stage_units_in_meters=1.0, physics_dt=1 / 240); world.scene.add_default_ground_plane(z_position=CAL["table_z"])
stage = omni.usd.get_context().get_stage(); add_reference_to_stage(USD, "/World/so101")
fj = UsdPhysics.FixedJoint.Define(stage, "/World/so101/base_fixed"); fj.CreateBody1Rel().SetTargets(["/World/so101/Geometry/base_link"])
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
for j in J:
    d = UsdPhysics.DriveAPI.Apply(stage.GetPrimAtPath(f"/World/so101/Physics/{j}"), "angular")
    d.CreateStiffnessAttr(2000.0 if j != "gripper" else 0.15); d.CreateDampingAttr(60.0 if j != "gripper" else 0.01); d.CreateMaxForceAttr(10.0 if j != "gripper" else 2.9)
rubber = PhysicsMaterial(prim_path="/World/Materials/rubber", static_friction=MU, dynamic_friction=MU, restitution=0.0)
for prim in stage.Traverse():
    if ("gripper_link" in prim.GetPath().pathString) and prim.HasAPI(UsdPhysics.CollisionAPI):
        UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr().Set("convexDecomposition")
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(UsdShade.Material(stage.GetPrimAtPath("/World/Materials/rubber")), UsdShade.Tokens.weakerThanDescendants, "physics")
arm = world.scene.add(SingleArticulation(prim_path="/World/so101", name="so101")); world.reset(); arm.initialize(); names = arm.dof_names
# a horizontal side grasp: shoulder and elbow set so the gripper points down-forward, wrist level; open wide
q = np.zeros(len(names)); q[names.index("gripper")] = 1.2
arm.set_joint_positions(q); arm.apply_action(ArticulationAction(joint_positions=q))
for _ in range(60): world.step(render=False)
gl = [p for p in stage.Traverse() if p.GetName() == "gripper_link"][0]
M = np.array(UsdGeom.Xformable(gl).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
hinge_axis_world = M[:3, 1]; gap = M[:3, :3] @ np.array([0.03, 0.0, -0.085]) + M[:3, 3]
print("gripper_link y axis in world (jaw hinge):", hinge_axis_world.round(3), "| gap point", gap.round(3), flush=True)
# a can whose axis is along the hinge axis, centred on the gap point (gravity off for the can until it is held)
from scipy.spatial.transform import Rotation as Rot
rot = Rot.align_vectors([hinge_axis_world], [[0, 0, 1]])[0].as_quat(); quat = np.array([rot[3], rot[0], rot[1], rot[2]])
can = world.scene.add(DynamicCylinder(prim_path="/World/can", name="can", position=gap, orientation=quat, radius=0.033, height=0.115, mass=0.268, physics_material=rubber))
PhysxSchema.PhysxRigidBodyAPI.Apply(stage.GetPrimAtPath("/World/can")).CreateDisableGravityAttr(True)
world.step(render=False)
for target in (1.2, 0.9, 0.7, 0.5, 0.3, 0.1):
    q[names.index("gripper")] = target + GOFF; arm.apply_action(ArticulationAction(joint_positions=q))
    for _ in range(120): world.step(render=False)
    print(f"cmd {target + GOFF:.2f}  got {arm.get_joint_positions()[names.index('gripper')]:.3f}  can {np.round(can.get_world_pose()[0], 3).tolist()}", flush=True)
PhysxSchema.PhysxRigidBodyAPI(stage.GetPrimAtPath("/World/can")).GetDisableGravityAttr().Set(False)
p0 = can.get_world_pose()[0]
q[names.index("shoulder_lift")] -= 0.3; arm.apply_action(ArticulationAction(joint_positions=q))
for _ in range(240): world.step(render=False)
p1 = can.get_world_pose()[0]; print("lift test: can moved", np.round(p1 - p0, 3).tolist(), "| gripper", round(float(arm.get_joint_positions()[names.index('gripper')]), 3))
app.close()
