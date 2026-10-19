# FP16 real-arm run — operator notes

Operator observations by trial number. The operator is blind to engines; these notes contain no cell information.
Hardware: rubber bands on the gripper, pads removed. Scene: cola can at the training start mark, yellow can out of view.

## 2026-10-13

- Trial 13: **failure**. The gripper tried to grasp with its fingertips and dropped the can
- All other trials succeeded (operator). Block complete: 40 trials, 0 invalid, 0 aborted. Live judge 37/40

## Q8 (2026-10-19, fp16 prereg §9 amendment 3; INT8 chatter block, cola can at the training mark, rubber-band gripper)

- Before the block: no grid sheet, leader-arm teleop off, Cosmos endpoint stopped (C1 not recorded).
- Failures reported by the operator, by trial number only (blind to cells; kinds (a) start not found, (b) pushed while
  closing, (c) edge placement, (e) knocked over after placing):
  - trial 1: grasped in the wrong place, and the can fell while being set down.
  - trial 2: (b), the can was pushed away while the gripper closed.
- Paused after trial 6 (2026-10-19/20). Live judge: trials 1-6 all failed; one operator abort (trial 4, rerun under the
  same number). The pause is a hardware check triggered by the block-level failure pattern (both cells, cells not
  opened): normalization file, engine file, can position, image brightness, start pose, joint tracking error,
  calibration files and the wrist view all match T0R, where the old FP16 policy went 11/12 at the same mark. The
  operator reports gripper bands, can, mounts and lighting unchanged.
- Next: a non-blind diagnostic of 3 runs with the old FP16 engine (FP16-block token `39b99e35`, not a Q8 token) at the
  training mark, in its own session `diag_q8_fp16`. These runs are never counted in Q8.
  - diagnostic run 1 (FP16, non-blind, not counted): success.
  - diagnostic run 2: failure. It went for the wrong start spot, pushed the can, grasped it only partly and dropped it ((a) then (b)).
  - diagnostic run 3: success; the operator notes that all the diagnostic successes were marginal.
  - Diagnostic total: 2/3, with marginal successes.
- Scene finding (first overhead frames, all blocks): small **red round markers** lie on the start axis next to the can
  from the generalization blocks (TYP, 2026-10-17) onward, in TYP, T6P, T6M, Q8 and the diagnostic. They are absent
  in T1, T0 and T0R, where the old FP16 policy succeeded at the mark; T2 shows at most one faint marker. The can is
  red, so the markers are a plausible visual distractor. This finding uses no cell information.
- Red markers removed (2026-10-20, checked on the overhead frame). Diagnostic restarted (FP16, non-blind, not counted):
  - run 1 after removal: failure (b), the can was pushed away while the gripper closed.
- Start-pose gripper position in the first overhead frame is the same across blocks within a few pixels (T0R 171,341;
  latest diagnostic 169,338), so a shifted arm base is not supported.
  - runs 2 and 3 after removal: success. Diagnostic after removal: 2/3.
- 2026-10-20 before Q8B: system update with all 108 NVIDIA/TensorRT/CUDA packages held, then reboot. Checks after
  reboot: L4T 36.5.2 and TensorRT 10.3.0.30 unchanged, 15 W, device links intact, Q8B engine hashes 3b19f7eb/86eba809,
  runner 89e26180, no leftover processes. trtexec on the FP16-block engines: FP16 median 11.71 ms, INT8 16.95 ms (the
  benchmarked 11.6 ms and 16.8-17.1 ms).

## Q8B (2026-10-20, fp16 prereg §10 amendment 4; INT8 chatter block, restarted, cola can at the training mark, no red markers)

- Failures reported by the operator, by trial number only (blind to cells):
  - trial 33: (e), set the can down, then knocked it over while the arm moved away (`placement disturbance`).
  - trial 36: grasped in the wrong place, and the can fell over while being set down.
