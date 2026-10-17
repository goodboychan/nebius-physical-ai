# Position fine-tune evaluation (T1, T0) — operator notes

Operator observations by trial number. The operator is blind to engines, and these notes contain no cell information.
Outcomes are decided by the locked criterion (automatic judge and §11 consensus re-judge), not by these notes.
- Hardware: rubber bands on the gripper. Cola can.
- T1 scene: the +3 cm (S1, red dot) mark. T0 scene: the training start mark.
- Live Cosmos: on, using the C1 p1 end-of-trial prompt (endpoint running from 21:33 KST).
- A side-view phone video was recorded from a fixed mount outside the overhead view (checked on an overhead frame
  before the session).

## 2026-10-14, T1

- Trial 2: the can ended **half on the coaster**. The operator would read it as a failure; the locked criterion decides.
- Trial 3: the same as trial 2 (the can ended half on the coaster).
- Trial 6: the can was set half on the coaster, then the gripper moved and knocked it over.
- Trial 8: the same pattern (set half on the coaster).
- After trial 8: the operator reports that **the two policies' motions look visibly different**. So the operator may
  be able to tell the arms apart by motion, though not which one is FT. This is a partial-unblinding risk for the
  operator's inputs, recorded as it arose.
  - Outcomes do not depend on the operator: success comes from the automatic judge and the video consensus
    re-judge.
  - The operator's inputs are the release and contact answers and the can placement.
  - The operator was asked to keep the placement and answers identical regardless of the motion seen.
  - Side-view recording may stop mid-block. A non-blind demonstration of both policies is planned after T0.
- T1 complete (22:08 KST): 24/24 trials logged; 0 invalid, 0 aborted, 0 runtime errors, 0 human contact; 24 overhead
  videos. The operator did not see some failures directly; outcomes come from the automatic judge and the §11 video
  consensus re-judge, so this does not change any result.
- During T0: the operator reports **much less gripper chatter** than in earlier experiments. No cell information.
- T0 trial 18: the can did not fall but was pushed far off the coaster.
- T0 trial 22: the can was knocked over while being set down.
- T0 complete: 24/24, 0 invalid, 0 aborted, 0 runtime errors, 0 contact. Sealed logs hashed into artifacts/freeze/ft_post.json; unsealing deferred until T2 is done.

## 2026-10-14, T2 (−3 cm, amendment 4)

- Before T2: a red sticker was placed at the new −3 cm mark. An overhead frame shows the two red dots symmetric about
  the start-mark tape. The sticker is a scene change shared by both arms within T2.
- T2 trial 12: the can was set down properly, then the gripper kept moving nearby and knocked it over.
- T2 trial 14: the can was never grasped.
- During T2: the operator reports that the difference between the fine-tuned and non-fine-tuned policies again looks clear. The operator says they can tell the two motion patterns apart, so the operator may also infer which pattern is the fine-tune. No trial-to-cell mapping was stated. Recorded as a blinding limitation; outcomes come from the automatic judge and the video re-judge.
- T2 complete: 24/24. Sealed log hashed into artifacts/freeze/ft2_post.json before unsealing. The operator did not see some failures directly.

## 2026-10-14, demonstration runs after unsealing (not counted)

- Non-blind runs for the video at the +3 cm mark, saved in their own sessions (`~/so101_trials/demo_shift_old`,
  `demo_shift_ft`): OLD-FP16 (VC-025) and then FT-FP16. A side-view phone video was recorded. These runs are
  never added to T1/T0/T2. Any clip from them is captioned "demonstration, not counted", with the counted T1 result
  shown alongside.

## T0R (2026-10-15, prereg §15; training start mark, rubber-band gripper)

- Before the block: touch calibration for the Isaac Sim twin (`scripts/so101_touch_calib.py`). The first wrist check
  failed because the A4 grid sheet was still in the wrist camera's view; the sheet was removed and the check re-run.
  The coaster was re-seated on its mark. The Cosmos endpoint was up (C1 judge recorded, not used for outcomes).
- Failures reported by the operator, by trial number only (blind to cells):
  - 22:29 trial 2: the gripper pushed the can while approaching; it slid out of reach and was never grasped.
- 23:00 T0R complete: 24/24, 0 aborted. Sealed log hashed into artifacts/freeze/ft3_post.json before unsealing. The Cosmos endpoint was stopped.

## TYP (2026-10-17, prereg §17; yellow can at the +3 cm mark, rubber-band gripper)

- Before the block: yellow can judge values re-measured (PASS, `stress_can_TYP.json`); reach check at ±6 cm with
  the leader arm (not recorded). The Cosmos endpoint was stopped (C1 not recorded; an offline batch re-judge of the
  final frames is planned before unsealing).
- Failures reported by the operator, by trial number only (blind to cells):
  - trial 1: the gripper pushed the can while approaching; it was never grasped.
  - trial 2: the gripper closed partly on the can, then the can was pushed away.
  - trial 3: as trial 1, the gripper pushed the can while approaching; it was never grasped.
  - trial 5: as trial 1, the gripper pushed the can while approaching; it was never grasped.
  - trial 6: grasped, carried and set down, but on the coaster edge; the judge called it a failure.
  - trial 7: as trial 1, the gripper pushed the can while approaching; it was never grasped.
  - trial 9: reported as the same as before (the gripper pushed the can while approaching; never grasped).
  - trials 11 and 12: failures (mode not yet given).
- Operator observation after trial 12 (blind to cells): the failures so far fall into three kinds:
  (a) the gripper does not find the can's start position and grasps in the wrong place;
  (b) it reaches the right start position, but the can is pushed away while the gripper closes;
  (c) the can is carried and set down on the coaster edge.
  These are used as descriptive sub-labels in the blind mode labelling before unsealing ((a), (b) under `grasp`,
  (c) under `other: edge placement`); they do not change the outcome rule.
  - trial 13: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 14: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 15: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 16: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 17: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 18: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 19: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 20: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 21: (b), the right start position was reached, but the can was pushed away while the gripper closed.
