"""Render small markers at the touch-grid dots and the coaster with the fitted overhead camera, and report where they
land against the real photo's dot pixels (sim phase 1). Tries each camera_axes convention.
Usage: sim/isaac.sh sim/check_camera.py <twin_calibration.json> <twin_camera.json> <spacing m> <out dir>"""
import json, os, sys
from isaacsim import SimulationApp
app = SimulationApp({"headless": True, "width": 640, "height": 480})
import numpy as np
from scipy.spatial.transform import Rotation as Rot
from isaacsim.core.api import World
from isaacsim.core.api.objects import FixedSphere
from isaacsim.sensors.camera import Camera
import isaacsim.core.utils.prims as pu
from PIL import Image
CAL, CAM, SPm, OUT = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), float(sys.argv[3]), sys.argv[4]; os.makedirs(OUT, exist_ok=True)
world = World(stage_units_in_meters=1.0); world.scene.add_default_ground_plane(z_position=CAL["table_z"])
g = CAL["grid_pose"]; c, s = np.cos(g["yaw_rad"]), np.sin(g["yaw_rad"])
GRID = np.array([[(cc - 1) * SPm, (1 - r) * SPm] for r in range(3) for cc in range(3)]) @ np.array([[c, s], [-s, c]]) + g["xy_m"]
for i, (x, y) in enumerate(GRID): world.scene.add(FixedSphere(prim_path=f"/World/dot{i}", name=f"dot{i}", position=np.array([x, y, CAL["table_z"] + 0.004]), radius=0.006, color=np.array([1.0, 0, 0])))
pu.create_prim("/World/Dome", "DomeLight", attributes={"inputs:intensity": 1500.0})
Rcw = np.array(CAM["R_world_to_cam"]); tcw = np.array(CAM["t_world_to_cam"]); pos = -Rcw.T @ tcw; AP = 20.955
cam = Camera(prim_path="/World/overhead", position=pos, resolution=(640, 480), frequency=30)
world.reset(); cam.initialize(); cam.set_clipping_range(0.01, 50.0)
cam.set_horizontal_aperture(AP); cam.set_focal_length(CAM["focal_px"] * AP / 640); cam.set_vertical_aperture(AP * 480 / 640)
x, y, z, w = Rot.from_matrix(Rcw.T).as_quat()
for axes in ("ros", "usd", "world"):
    cam.set_world_pose(position=pos, orientation=np.array([w, x, y, z]), camera_axes=axes)
    for _ in range(15): world.step(render=True)
    im = cam.get_rgba()[..., :3]; Image.fromarray(im).save(f"{OUT}/cam_{axes}.png")
    red = (im[..., 0] > 150) & (im[..., 1] < 80) & (im[..., 2] < 80); ys, xs = np.nonzero(red)
    print(axes, "red px", int(red.sum()), "centroid", (round(float(xs.mean()), 1), round(float(ys.mean()), 1)) if red.any() else None,
          "| real dots centroid", np.array(CAM["dots_px"]).mean(0).round(1).tolist(), "| focal mm", round(cam.get_focal_length(), 3))
app.close()
