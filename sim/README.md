# Isaac Sim twin of the SO-101 coaster task (phase 1, 2026-10-15)

Exploratory and not part of the hackathon evidence. Nothing here changes a QuantGate number.

- **Environment**: GX10 (GB10, aarch64). Isaac Sim 6.2.0 from pypi.nvidia.com is installed in `~/isaacsim-env` (19 GB).
  Run scripts through `sim/isaac.sh`, which preloads libgomp (needed on aarch64) and sets the EULA flag; the user
  accepted the EULA on 2026-10-15. The first launch compiles shaders for about 3 min, later launches take about 12 s.
- **Robot**: SO-ARM100 `Simulation/SO101/so101_new_calib.urdf` (Apache 2.0, commit `a758567c`), converted with
  `urdf_usd_converter --no-layer-structure --no-physics-scene`. Assets live in `~/edgeqgate_data/sim_assets/`, outside
  the repo.
- **Scene** (`build_scene.py`): the robot fixed on a table, a 5 cm coaster, a 268 g can (r 33 mm, h 115 mm), lights and
  an overhead camera.
  - USD cameras default to a 1 m near clip, so the script sets 0.01 m; otherwise every frame is blank.
  - Joint position drives track the commands within about 0.1 rad.
- **Status**: replaying a recorded demo moves the arm, but the gripper does not reach the can.
  - The URDF zero (middle of range) does not match this robot's LeRobot calibration. With zero offsets, the forward
    kinematics put the gripper about 5 cm under the table at the grasp (`scene_estimate.json`).
  - Fitting per-joint offsets and the camera pose from the overhead images alone (`calibrate_twin.py`) is
    under-determined: the images show essentially two point clusters (start mark and coaster). The bounded fit hit its
    bounds, with a 21 px median residual, and was discarded.
- **Touch calibration, ready** (`scripts/so101_touch_calib.py` on the Orin, `sim/fit_touch_calib.py` here):
  - It uses 9 table dots plus the can top on 4 corner dots, each touched with the wrist tilted forward and back.
  - Table touches alone could not separate the lift, elbow and wrist offsets: the selftest errors reached 25°.
  - The shoulder-pan offset is a gauge freedom (it is the same as rotating the table), so it is fixed at 0.
  - Selftest on synthetic touches with 0.3° noise: the offsets are recovered within about 3.5°, the residual is
    about 4 mm.
- **Previous plan**: a touch calibration on the real arm (about 5 minutes). Drive the follower with the leader so the gripper
  tip touches 6–8 table points whose positions are measured with a ruler from the base, and record the joint states.
  Then fit the joint offsets (table height known, xy known), and solve the overhead camera pose by PnP from the same
  points in the overhead frame.
