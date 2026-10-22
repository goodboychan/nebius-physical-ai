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
  - trial 22: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 23: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 24: (b), the right start position was reached, but the can was pushed away while the gripper closed.
- TYP complete: 24 trials, 0 aborted. Operator-reported failures: 21 (trials 1-3, 5-7, 9, 11-24); not reported as failures: 4, 8, 10. The counted outcome is the judge and the blind consensus re-judge.
- TYP sealed log hashed before T6P (interim, not opened): `stress_ft4_TYP_sealed.jsonl` sha256 `d90d75b2b95a6d41e17e45769eb45b744eef7dc7ef468310ab1b9d5f865420e4`, 24 trials, 0 aborted, 0 invalid. Live automatic judge failures by trial (no cells): 1-3, 5-7, 9, 11-24 (21), the same trials the operator reported.

## T6P (2026-10-17, prereg §17; cola can at the +6 cm mark, rubber-band gripper)

- Failures reported by the operator, by trial number only (blind to cells; kinds (a)/(b)/(c) as in TYP):
  - trials 1 and 2: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 3: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 4: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 5: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 6: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 7: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 8: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 9: (a), the start position was not found and the can was grasped in the wrong place.
- T6P complete: 24 trials, 0 aborted, 0 invalid. The operator reported trials 1-9 individually; trials 10-24 were not described. Sealed log hashed (interim, not opened): `stress_ft4_T6P_sealed.jsonl` sha256 `3a766befbae52140b3ecae21018bd2e7896733da97fbd819e616564fce9055bd`. Live automatic judge: all 24 trials failed (this is a block-level tally; with every trial failing it shows no cell-level difference before unsealing).

## T6M (2026-10-18, prereg §17; cola can at the −6 cm mark, rubber-band gripper)

- Failures reported by the operator, by trial number only (blind to cells; kinds as in TYP):
  - trials 1 and 4: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 5: (c), the can was carried and set down on the coaster edge.
  - trial 6: (b), the right start position was reached, but the can was pushed away while the gripper closed.
- After trial 6 the operator said the arm had "stopped" several times; the log shows no operator abort (Ctrl+C) in trials 1-6, so the stop rule (2 aborts) has not been reached.
  - trial 8: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 9: the can was set down properly, then knocked over while the arm moved back (pre-registered label `placement disturbance`; a fourth kind, not (a)-(c)).
  - trial 10: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 12: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 13: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 14: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 16: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 17: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 19: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 21: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 23: (c), the can was carried and set down on the coaster edge.
  - trial 24: (a), the start position was not found and the can was grasped in the wrong place.
- T6M complete: 24 trials, 0 aborted, 0 invalid; live judge failures 1, 4-6, 8-10, 12-14, 16, 17, 19, 21, 23, 24 (16), the same trials the operator reported.
- All three sealed logs hashed into `artifacts/freeze/ft4_post.json` before any is opened.

## T6PR (2026-10-21, prereg §19 amendment 8; cola can at the +6 cm mark, no red markers, wrist camera as re-aimed before H1)

- Pre-block check (no policy, arm not moved): rest-pose wrist frame shows the fingertips and orange band as after the 10-20 re-aim; overhead frame shows no red markers.
- Failures reported by the operator, by trial number only (blind to cells; kinds as in TYP):
  - trial 1: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 2: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 3: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 4: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 5: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 6: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 7: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 8: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 9: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 10: (a), the start position was not found and the can was grasped in the wrong place.
  - After trial 10 the operator said every trial seemed to fail; no operator abort so far, so the block continues (stop rule: 2 aborts).
  - trial 11: (a), the start position was not found and the can was grasped in the wrong place (typed "ㅁ", the a key on the Korean layout).
  - trial 12: (a), the start position was not found and the can was grasped in the wrong place (typed "ㅁ").
  - trial 13: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 14: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 15: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 16: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 17: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 19: (a), the start position was not found and the can was grasped in the wrong place. (Trial 18 was not reported as a failure.)
  - trial 20: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 21: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 22: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 23: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 24: (a), the start position was not found and the can was grasped in the wrong place.
- T6PR complete: 24 trials, 0 aborted, 0 invalid. Live automatic judge: all 24 failed, trial 18 included (block-level tally; with every trial failing it shows no cell-level difference before unsealing). Sealed log hashed (interim, not opened): `stress_ft5_T6PR_sealed.jsonl` sha256 `47e8a4849fedbdcb883c2fa6840ffb03e2b8c591be85ac515a3a78a59fa65904`.

## TYPR (2026-10-21, prereg §19 amendment 8; yellow can at the +3 cm mark, no red markers, judge values stress_can_TYP.json)

- Failures reported by the operator, by trial number only (blind to cells; kinds as in TYP):
  - trial 1: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 2: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 3: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 4: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 5: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 6: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 7: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 8: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 9: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 10: (a), the start position was not found and the can was grasped in the wrong place.
  - After trial 10 the operator said the arm seemed to miss the can's position more completely than in TYP (10-17), and asked whether every trial might fail. No operator abort so far; the block continues (stop rule: 2 aborts).
  - trials 11-17: (a), the start position was not found and the can was grasped in the wrong place (reported together after trial 18; from trial 11 the operator reported only failures other than (a) as they happened).
  - trial 18: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 19: (b), the right start position was reached, but the can was pushed away while the gripper closed (typed "ㅠ", the b key on the Korean layout).
  - trial 20: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 21: (b), the right start position was reached, but the can was pushed away while the gripper closed.
  - trial 22: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 23: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 24: (b), the right start position was reached, but the can was pushed away while the gripper closed.
- TYPR complete: 24 trials, 0 aborted, 0 invalid. Live automatic judge: all 24 failed (block-level tally). Operator kinds: (b) in trials 18, 19, 21, 24; (a) in the rest. Both sealed logs hashed into `artifacts/freeze/ft5_post.json` before either is opened.

## TYP2 (2026-10-22, prereg §21 amendment 9; yellow can at the +3 cm mark, FT2 vs FT, wrist mount fixed, Ray worker service stopped)

- Pre-block check (no policy, arm not moved): wrist frame shows the fingertips and band as in the H2 reference; overhead frame shows no stray markers.
- Failures reported by the operator, by trial number only (blind to cells; kinds as in TYP):
  - trial 1: (a), the start position was not found and the can was grasped in the wrong place.
  - From trial 2 on, the operator reports failures only; a trial not mentioned is one the operator saw succeed (operator's convention, 2026-10-22). The counted outcome is still the judge and the blind re-judge.
  - trial 3: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 17: (a), the start position was not found and the can was grasped in the wrong place. (Trials 4-16 not mentioned: seen as successes by the operator.)
  - trial 19: (a), the start position was not found and the can was grasped in the wrong place.
  - trial 22: (a), the start position was not found and the can was grasped in the wrong place.
