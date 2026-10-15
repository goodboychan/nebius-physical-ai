"""Isaac Sim smoke test on the GX10: headless app, a lit cube on a ground plane, one camera frame saved to PNG."""
import sys
from isaacsim import SimulationApp
app = SimulationApp({"headless": True, "width": 640, "height": 480})
import numpy as np
from isaacsim.core.api import World
from isaacsim.core.api.objects import DynamicCuboid
from isaacsim.sensors.camera import Camera
import isaacsim.core.utils.prims as pu
world = World(stage_units_in_meters=1.0); world.scene.add_default_ground_plane()
world.scene.add(DynamicCuboid(prim_path="/World/Cube", name="cube", position=np.array([0, 0, 0.3]), size=0.1, color=np.array([0.9, 0.2, 0.1])))
pu.create_prim("/World/Dome", "DomeLight", attributes={"inputs:intensity": 1000.0})
cam = Camera(prim_path="/World/Cam", position=np.array([0.6, 0.6, 0.5]), resolution=(640, 480), frequency=30)
world.reset(); cam.initialize()
from isaacsim.core.utils.viewports import set_camera_view
cam.set_world_pose(position=np.array([0.6, 0.6, 0.5]), orientation=None)
for i in range(120): world.step(render=True)
img = cam.get_rgba()
print("raw", None if img is None else (img.shape, img.dtype, float(img[..., :3].mean()) if img.size else None))
from PIL import Image; Image.fromarray(np.asarray(img)[..., :3].astype(np.uint8)).save(sys.argv[1]); print("SMOKE OK")
app.close()
