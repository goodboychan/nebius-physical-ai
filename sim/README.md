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

## Debugging 2026-10-15/16, after the T0R block

- **Grip physics works when the geometry is right** (`check_grip_contact.py`).
  - Arm still, can placed in the jaw gap computed from the meshes: the jaw stops at 0.778 rad on the can, close to
    the 0.75 rad the meshes predict for a 66 mm gap.
  - The can lifts 8.4 cm with the arm (rubber μ = 1.0, an STS3215-like gripper torque of 2.9 N m, convex
    decomposition on the gripper colliders).
- **The gripper mapping is off by about 0.3 rad.** The real hold reading (32.8 on the 0–100 scale) maps linearly to
  0.455 rad. There the jaw gap is about 5.4 cm, too small for the can, while the meshes need about 0.75–0.78 rad.
  So 0–100 does not map to the URDF limits as assumed.
- **The replay still misses the can, because the joint offsets are not identified.**
  - Fitting them with the camera and demo grasps gives non-physical solutions:
    - a free jaw point 6.7 cm along the hinge, wider than the gripper;
    - with the mesh jaw point fixed, a 57 mm residual;
    - with wrist roll added, a 78° roll and a 34 mm residual.
  - Indirect fitting has reached its limit.
- **Next (stage 3): measure the offsets directly on the arm** (about 5 minutes).
  - `POSES=EXTENDED,GRIP_CLOSED,GRIP_CAN python so101_touch_calib.py`.
  - Arm straight out and level (the SO-ARM100 `so101_old_calib.urdf` zero, known relative to the new-calibration
    URDF), gripper fully closed, gripper holding the can.
  - These give each joint's offset and the gripper's 0–100 → angle mapping directly. Then the stage 1–2 data become
    checks rather than the fit.

## Stage 3 (2026-10-16): offsets measured directly

- **Poses**: `POSES=EXTENDED,GRIP_CLOSED,GRIP_CAN`.
  - Matching against `so101_old_calib.urdf` failed: its base and link frames differ beyond joint zeros, with a
    64 mm residual.
  - A render of the measured pose with zero offsets showed the arm nearly straight. So "extended" is defined in the
    new URDF itself: the shoulder→elbow, elbow→wrist and wrist→tip lines are all level.
- **Result** (`fit_pose_calib.py`, `twin_calibration_v4.json`):
  - Measured offsets: lift −7.35°, elbow −19.1°, wrist_flex +3.8°.
  - With no fitting, the 9 table touches fit within 3.4 mm, and the held-out START and COASTER heights within 1 and
    4 mm.
  - wrist_roll is not fixed by "level". From the demo grasps it is about +88° (LeRobot's roll zero is about a
    quarter turn from the URDF's). With the gap point free, the grasp xy error is 5.8 mm.
  - Gripper map: 1.09 (closed) → −0.1745 rad, 31.93 (on the can) → 0.778 rad.
- **Replay** of T0 trial 1, commanded joints, gripper stiffness 0.3, μ 1.5:
  - The jaw closes on the can (stops at about 0.78–0.88 rad), and **the can is lifted to 17 cm** and carried toward
    the coaster.
  - It then slips out during the fast swing, at about step 225–240, and falls.
  - Stiffer grip (0.5) ejects it. More solver iterations (16–32) and real step timing (`t_wall_s`) did not stabilise
    the carry; the outcome is sensitive to these settings.
- **Next**: contact tuning (collider rest and contact offsets, a cylinder collider for the can, finer jaw
  decomposition), or, for a visual replay only, a grasp attachment labelled as such.
