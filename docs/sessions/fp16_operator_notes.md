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
