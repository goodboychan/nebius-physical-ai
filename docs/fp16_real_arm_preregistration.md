# FP16 real-arm run — pre-registration v1 (LOCKED before the first F0 trial)

Status: locked 2026-10-12 by the commit that adds this file. The user decided to run it (2026-10-12). No FP16 real-arm
trial has been run.

## 1. Question

On the Orin Nano Super at 15 W, the FP16 engine (`VC-025`) is the fastest and the most energy-efficient
(`artifacts/reports/power_bench/SUMMARY.md`: 11.6 ms and 82 mJ per inference, against 16.8–17.1 ms and 101 mJ for
INT8). It is the engine a practitioner should ship **if it is not worse on the real arm**. FP16 was never run on the
arm: it was excluded from the G6 arms (decision_log, #5). This run asks:

> Is FP16 closed-loop performance tolerance-compatible with FP32 on the current hardware?

## 2. Hardware and scene

This is the current hardware: **rubber bands on the gripper, pads removed** (stress protocol §8). The scene is
nominal: the cola can at the training start mark. The hardware differs from G6, so FP16 is compared only with cells
run in the **same interleaved session**, never with G6.

## 3. Design

| Cell | Engine | Trials |
|---|---|---|
| `VC-025` | FP16 (engine sha256 `3b19f7eb…`, as in the G3 manifest) | 20 |
| `VC-000` | FP32 reference | 10 |
| `VC-002` | INT8 best fidelity | 10 |

- 40 trials, interleaved with key (k + U)/n_c, seed key `FP16/schedule/v1` (`scripts/fp16_schedule.py`).
- New anonymous tokens. Sealed schedule `~/.edgeqgate_sealed/stress_fp16/stress_sealed.json`, sha256
  `ded2ea119a22d4a950db3209f648475d85ca93fc0031136958b5f0160d8150f2`. Public copy
  `artifacts/fp16/stress_schedule_public.json`.
- Runner: `so101_trial.py --blind F0 fp16`. Execution, session checks and the Cosmos shadow and end question are as
  in stress v2. Latency is hidden from the operator.
- Order: after stress v2 S4 is complete, in its own session.

## 4. Outcome

Stress protocol §9 applies: the offline re-judge (`scripts/stress_rejudge.py`, locked geometry, ≤ 3/15 outlier frames)
∧ released ∧ no human contact ∧ not aborted. E2 is the re-judged base distance.

## 5. Analysis (`scripts/fp16_analysis.py`, sha256 `dfd92ea4…`)

- **Primary**: VC-025 vs VC-000.
  - Degradation = FP32 − FP16 for E1 (pp) and FP16 − FP32 for E2 (px).
  - Unpaired bootstrap with 10,000 draws. The family is 2 endpoints, so the CI is 97.5%.
  - AEP decision semantics, tolerances E1 10 pp and E2 5 px, with the ceiling rule.
- **Secondary**: VC-025 vs VC-002, with the same CI.
- **Descriptive**: end-to-end inference latency per cell, late chunks, and step-time maxima.
- `falsified_if` (the claim "FP16 is safe to ship here"): `materially_degraded` on either primary endpoint.

**Power, stated now**: with 20 vs 10 trials, E1 `tolerance_compatible` needs the upper CI bound below 10 pp. That is
unlikely unless both cells are close to 100%. The likely E1 outcome is `indeterminate`. E2 (continuous) is the
informative endpoint. Results are reported as effect sizes and CIs.

## 6. Order lock

1. This file, the analysis script, the schedule and the runner are committed before the first F0 trial.
2. After the last trial, the sealed log `stress_fp16_F0_sealed.jsonl` is hashed into `artifacts/freeze/fp16_post.json`.
   Only then is it opened.
3. If the session fails, the trials so far are reported as they are. Nothing is changed after outcomes have been seen.

## 7. Amendment 1 (2026-10-12, before the first F0 trial)

The E1 decision uses the Newcombe hybrid-score interval at 97.5%, the bootstrap is secondary, E2 needs at least 5
placements per arm, and each comparison gets a verdict: GO, NO-GO or INSUFFICIENT_EVIDENCE. The analysis function is
the same as in stress protocol §10 (`stress_analysis.py` `7d99864d…`). The reason is the bootstrap's collapse at 0
failures.

## 8. Amendment 2 (2026-10-13, before the first F0 trial)

The outcome uses the consensus re-judge of stress protocol §11 (`stress_rejudge_consensus.py` `382acdf3…`) instead of §9.
The reason is the §9 rule's false failures on an off-center can, documented in §11 and validated on 345 videos.

## 9. Amendment 3 (2026-10-18, before any Q8 trial): an INT8 chatter block

- **Why**: in G6 and the FP16 block, the INT8 build `VC-002` commanded a gripper that chatters about twice as much as
  FP16 (`artifacts/reports/ft_chatter.json`; median 0.29–0.31 against 0.13). That is a post hoc observation. This block
  tests it prospectively. It also matters for deployment: the review recommends FP16 first, and INT8 only if memory or
  power forces it.
  - Written after G6, the FP16 block and the fine-tune blocks were unsealed. No Q8 trial exists.
- **Design**: block **Q8**, the cola can at the training start mark, rubber-band gripper.
  - `VC-002` (INT8, engine sha256 `86eba809…`) 24 and `VC-025` (FP16, `3b19f7eb…`) 24, both the original policy,
    interleaved by the (k + U)/n key.
  - Seed key `INT8/chatter/schedule/v1`, with new random tokens.
  - Sealed schedule `~/.edgeqgate_sealed/stress_int8c/stress_sealed.json`, sha256
    `5646236006255b44f16326ac272d5fad6136ccf757d3dcd9e222627fbc4eddd5`. The public copy is
    `artifacts/fp16/stress_schedule_Q8_public.json`.
  - The engines are hard links to the FP16-block files, built by `scripts/int8c_setup_orin.py` (no token-to-cell
    output). There is one normalization file (`273746c2…`) with a per-token manifest (`2e3ec4632d118c83…`). The local
    copy of the sealed schedule was deleted unread.
- **Runner**: `so101_trial.py --blind Q8 int8c`, sha256 `bfc723a6ee8ba4eb…`, deployed with no block running. The
  previous `f499c1b0` is kept as a backup. The manifest is required. The C1 end-of-trial judge records if the endpoint
  is up. The stop rule is 2 operator aborts.
- **Primary** (`scripts/int8c_analysis.py`, written now and dry-run on relabelled FP16-block data):
  - Gripper chatter (the fine-tune prereg §13 metric, computed on the Orin by `ft_chatter.py measure`), `VC-002`
    against `VC-025`, Mann-Whitney U two-sided at α = 0.05.
  - The direction stated now is `VC-002` > `VC-025`. **Confirmed** iff p < 0.05 and the `VC-002` median is higher.
    Otherwise the reading is "not confirmed".
- **Secondary**: `chatter_hold` (closed-gripper steps), the same test.
- **Descriptive**: success with the usual semantics (97.5%, 10 pp, ceiling rule). No approval follows from this block.
- **Power, stated now**: if the earlier gap is real (medians about 0.30 against 0.13, with little overlap), 24 against
  24 detects it almost surely. A null result would contradict the post hoc pattern.
- **Order**: run Q8 → hash the sealed log into `artifacts/freeze/int8c_post.json` → blind consensus re-judge →
  chatter measured on the Orin (no cells) → unseal → `int8c_analysis.py`.
- **Date stop**: if not started by 2026-10-25, it is reported as not run.

## 10. Amendment 4 (2026-10-20, before any Q8B trial): Q8 restarted as Q8B after a scene deviation

- **What happened**: Q8 was paused after 6 trials (all failed by the live judge, one operator abort). No Q8 cell was
  opened.
  - The hardware check found one scene difference from the pre-registered nominal scene, the one used in T0R: small
    red round markers on the start axis next to the can, present since 2026-10-17.
  - Everything else matched T0R: engine and normalization files, calibration, control-loop timing, joint tracking, can
    position and image brightness.
- **Decision**: the 6 Q8 trials are **discarded as a scene deviation** and never analysed. The decision rests only on
  the scene difference, not on cell outcomes.
  - The sealed log is kept unopened: `stress_int8c_Q8_sealed.jsonl`, sha256
    `635a78d229a9bdf0671e04025a5469fc1f06d4b36c87c42704846ee60afd5cae`, 7 records.
  - The markers were removed (checked on the overhead frame).
- **Diagnostic, non-blind, not counted** (old FP16 engine, FP16-block token `39b99e35`, session `diag_q8_fp16`):
  - with markers, 2/3 (the operator called the successes marginal);
  - after removal, 2/3.
  - In T0R the same engine went 11/12 at the mark. The lower diagnostic rate is reported as a limitation. Q8B's primary
    endpoint (gripper chatter) is measured on every trial, success or not.
- **Design**: unchanged from §9 except the names. Block **Q8B**: `VC-002` 24 and `VC-025` 24, interleaved.
  - Seed key `INT8/chatter/schedule/v2`, with new random tokens.
  - Sealed schedule `~/.edgeqgate_sealed/stress_int8c2/stress_sealed.json`, sha256
    `33b6a82e98697fcb5f7ab736eb6c39c3bb3f910a3c044621513658f71f866125`. The public copy is
    `artifacts/fp16/stress_schedule_Q8B_public.json`.
  - Engines `86eba809…` and `3b19f7eb…`; normalization `273746c2…`; manifest `cd661bc72ded866b…`.
  - Runner: `so101_trial.py --blind Q8B int8c2`, sha256 `89e26180bd2e36f9…`, deployed after the diagnostic session ended.
- **Analysis**: `int8c_analysis.py --block Q8B`, the same rules as §9 (dry-run on relabelled FP16-block data).
- **Order**: as §9, with `artifacts/freeze/int8c2_post.json`.

## 11. Q8B results (2026-10-20, unsealed after int8c2_post.json)

Order kept:
1. The sealed log was hashed into `artifacts/freeze/int8c2_post.json` (pushed).
2. The consensus re-judge was run blind to cells: 43/48, equal to the live judge and the operator's reports.
3. The failure-mode labels were written blind (`artifacts/fp16/Q8B_modes.json`), and chatter was measured on the Orin
   for all 48 trials with no cell information.
4. Only then was the log unsealed. It matches the post record (`4a442990…`).

Analysis: `scripts/int8c_analysis.py --block Q8B`, written to `artifacts/reports/int8c2_analysis.json`.

| | VC-002 (INT8) | VC-025 (FP16) | Test | Reading |
|---|---|---|---|---|
| **Gripper chatter (primary)** | median 0.497 | 0.391 | MWU two-sided p = 0.12 | **Not confirmed**: the direction is INT8 > FP16, but the difference is not significant |
| Chatter, closed gripper (secondary) | 0.488 | 0.384 | p = 0.13 | not confirmed |
| Success (descriptive) | 23/24 | 20/24 | degradation −12.5 pp [−35.1, +9.7] at 97.5%; placement +1.2 px [+0.1, +2.3] | tolerance-compatible on both endpoints under `compare` semantics. By §9 this block is descriptive for success: **no approval follows** |

- **Failures** (blind labels): VC-002 1 (41, fell while being set down). VC-025 4: 33 placement disturbance, 36 fell
  after a wrong grasp, 39 pulled back while grasping, 44 fell while being set down.
- **Reading**:
  - The post hoc pattern from G6 and the FP16 block (INT8 chatter about twice FP16) is **not confirmed** prospectively.
    In this session the gap was about 1.3×.
  - **Chatter rose for both engines.** It was about 0.39–0.50, against 0.13 (FP16) and 0.29–0.31 (INT8) in the
    earlier nominal blocks at the same mark. The session-level rise is unexplained. It came after the red-marker period,
    the system update with the NVIDIA stack held, and a reboot. It is reported, not attributed.
  - FP16's 20/24 is lower than its earlier 19/20 and 11/12 at this mark, consistent with the diagnostic (2/3). The INT8
    success interval meets the 10 pp tolerance only because the reference itself was lower. Read it as "no sign INT8
    is worse here", not as evidence for INT8.
- **Limitations**: one session. The six earlier Q8 trials were discarded unopened for a scene deviation (§10). The
  chatter rise means this block may not represent the earlier nominal condition.

## 12. Health check H1 (2026-10-20, before any H1 trial): is the training-mark scene back to nominal?

- **Why**: gripper chatter tracks how far the policy is from familiar conditions. At the training mark the old FP16
  policy chattered at a median of 0.13 in T0R and 0.13 in the FP16 block. Since 2026-10-19 it has stayed high at the
  same mark: the discarded Q8 block 0.70, the diagnostic 0.60 (before the system update and reboot), Q8B 0.39.
  Hard-failure conditions sit at 0.56–0.74 (T6P, TYP). So the scene may still differ from T0R in a way not yet found.
- **Design**: non-blind, one engine, so no cells. The old FP16 engine (FP16-block token `39b99e35`), 12 runs at the
  training mark in the pre-registered scene (no extra markers), session `health_h1`. Never counted in any comparison.
- **Measures**: per-run chatter (`ft_chatter.py measure`), live judge success, and operator notes.
- **Readings, fixed now**:

  | H1 chatter median | H1 success | Reading | Then |
  |---|---|---|---|
  | ≤ 0.20 | ≥ 10/12 | back to nominal | run the re-test blocks (finetune prereg §19) |
  | 0.20–0.30, or ≥ 0.30 with ≥ 10/12 | — | unclear | run the re-tests and flag them |
  | ≥ 0.30 | < 10/12 | not nominal | do not run the re-tests; look for the cause first (wrist camera mount, lighting, gripper bands) |

## 13. H1 result (2026-10-20)

- 12 runs, old FP16 engine, training mark, restored scene (no red markers, wrist camera re-aimed; operator notes).
  Live judge **11/12** (run 11 failed, (b)).
- Chatter median **0.242** (per run 0.14–0.71; `artifacts/fp16/chatter_raw_H1.json`).
  - That is lower than the diagnostic (0.60) and Q8B FP16 (0.39), and above T0R and the FP16 block (0.13).
  - Runs 8–11 were higher (0.45–0.71) than the rest.
- **Reading (§12 table): "unclear"** (chatter 0.20–0.30). By the gate, the re-tests (finetune prereg §19) run and are
  flagged as run in a scene whose nominal status is unclear.

## 14. Health check H2 (2026-10-21, before any H2 trial): does a fixed wrist mount bring chatter back to nominal?

- **Why**: H1 read "unclear" (chatter 0.242, 11/12). After the amendment 8 re-tests the rest-pose wrist frame showed the
  camera shifted again (finetune prereg §20 hardware note). The hypothesis, stated before any H2 trial: the raised
  chatter since 2026-10-19 comes mainly from the wrist camera view. If so, a fixed mount should bring the old FP16
  policy back near its earlier 0.13 at the training mark.
- **Before the first run** (no policy, the arm does not move):
  - the operator fixes the wrist-camera mount (cable ties or adhesive) and aims it as in T0R;
  - a rest-pose wrist frame is taken (`wrist_snap.py`) and committed as the reference
    (`artifacts/fp16/wrist_ref_H2.png`) with its sha256, beside the T0R first frame;
  - the overhead frame is checked for stray markers.
- **Design**: as H1 (§12). Non-blind, one engine, no cells: the old FP16 engine (FP16-block token `39b99e35`), 12 runs
  at the training mark, session `health_h2`. Never counted in any comparison.
  - `so101_trial.py health_h2 VC-025 ~/.edgeqgate_sealed/stress_fp16/engines/39b99e35.engine 12`
- **Measures**: per-run chatter (`ft_chatter.py measure`), live judge success, operator notes, and a rest-pose wrist
  frame after run 12 compared with the reference.
- **Readings, fixed now** (the §12 table, unchanged):

  | H2 chatter median | H2 success | Reading | Then |
  |---|---|---|---|
  | ≤ 0.20 | ≥ 10/12 | back to nominal; the wrist hypothesis is supported | pre-register and run amendment 9 (fine-tune v2) |
  | 0.20–0.30, or ≥ 0.30 with ≥ 10/12 | — | unclear | amendment 9 may run, flagged |
  | ≥ 0.30 | < 10/12 | not nominal | no amendment 9 block; look for the cause first |

  - If the after-run wrist frame shows the camera moved again, H2 is reported with that note and the mount is fixed
    again before any later block.
- **Reference frame, before the first H2 run (2026-10-21)**: the operator re-aimed and fixed the wrist mount; the
  fingertips and the orange band are back in the lower right, as in the frame before T6PR. Committed as
  `artifacts/fp16/wrist_ref_H2.png`, sha256 `490f71ab0fcc16e48f0c9b14d62954dd8e298916a31b3e6c2e690c81c374d3ff` (overhead frame `top_ref_H2.png`).
  - Deviation, stated before any H2 run: the arm was not at the rest pose (joints [48.8, 25.3, 30.9, 36.4, -5.8, 2.0]),
    so the background differs from earlier rest-pose frames. The fingertips and band sit on the same link as the
    camera, so their place in the frame shows the camera angle regardless of the arm pose. The first wrist frame of
    H2 run 1, taken at the rest pose by the runner, is added as a second reference before H2 is read.

## 15. H2 result (2026-10-21)

- 12 runs, old FP16 engine, training mark, wrist mount re-aimed and fixed, no stray markers. Live judge **11/12**
  (run 12 failed: the can fell while being set down, operator report; placement disturbance).
- Chatter median **0.106** (per run 0.089–0.737; `artifacts/fp16/chatter_raw_H2.json`). Runs 6, 8 and 12 were higher
  (0.39, 0.41, 0.74); the other nine were 0.09–0.15.
  - That is back at the earlier nominal level (T0R and the FP16 block 0.13) and below H1 (0.242), Q8B (0.39) and the
    diagnostic (0.60).
- Wrist view: the first frame of run 1 (rest pose, second reference, sha256 `269ad2b6ae8a35b9…`) and a rest-pose frame after
  run 12 both show the fingertips and the band as in the reference (`artifacts/fp16/wrist_H2_check.jpg`). The mount held.
- **Reading (§14 table): "back to nominal"; the wrist hypothesis is supported.** It was stated before H2 and tested
  once, in one session, non-blind; it is not a controlled comparison of camera angles. Amendment 9 (finetune prereg
  §21) may be locked and run.
