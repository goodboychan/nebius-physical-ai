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

## Status 2026-10-15, late (after the T0R block)

- **Calibrated**:
  - Stage 1, table touches: 2.9 mm, with the held-out START and COASTER at table height within 1–2 mm.
  - Overhead camera: PnP with the focal fixed to the C922's nominal value, the grid, the coaster and two can tops;
    4.2 px.
  - The calibrated FK projected onto the real T0 trial 18 video lands on the real gripper.
  - Isaac Sim kinematics match the URDF FK within 1–2 cm (gravity sag). The camera matches the photo within about 3 px.
- **Stage 2** (`fit_grasp_calib.py`, `twin_calibration_v2.json`):
  - It adds 111 demo grasp moments, with the can position back-projected from the overhead frame. Touch residual
    3.2 mm, grasp residual 9.4 mm median, grasp height 5.9 cm.
  - Bug found and fixed: "tightest grip" picked the empty closed gripper (≈1), so the first stable hold after
    opening is used now.
- **Physics, not yet working**: in a replay of a successful trial (T0 trial 1), the arm reaches the can, but the
  jaws close without being blocked and the can stays.
  - Done: commanded joints replayed instead of measured ones, an STS3215-like gripper torque (2.9 N m), rubber
    friction 1.0, convex decomposition on the gripper colliders. None of these changed the outcome.
  - A close-up render shows the jaws arriving above the can top. The fitted jaw-centre point (lateral 6.7 cm in the
    gripper_link frame) absorbs the remaining kinematic error instead of locating the real gap between the jaws.
  - Next: compute the jaw gap from the gripper meshes at the measured hold angle (≈0.45 rad), fix that point, and
    refit only the joint offsets. Then tune contact.
