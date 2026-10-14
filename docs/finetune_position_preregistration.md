# Position fine-tune — pre-registration v1 (LOCKED before any demo is recorded)

Status: locked on 2026-10-13 by the commit that adds this file. The user decided on the task. No fine-tune demo,
checkpoint, engine or trial exists yet.

## 1. Why

QuantGate's stress test surfaced a weak spot: with the start moved 3 cm (S1), the policy failed 0/3. In that small,
early-stopped test the cause was not isolated. The developer's natural next step is to add demonstrations from varied
start positions, fine-tune, and run the same check again. This study runs that loop:

> Does a policy fine-tuned with varied start positions succeed more often at a **held-out** start position (+3 cm,
> the S1 mark) than the original policy, without degrading the nominal task?

The result is reported as measured. The study does not assume the fix works.

## 2. Data

- **50 new teleoperated demos**: 10 at each of five start positions along the S1 axis, at −4, −2, 0, +2 and +4 cm
  (+ is the S1 side; 0 is the training start mark). The order is shuffled from seed key `FINETUNE/positions/v1`
  (`scripts/ft_demo_order.py`, list in `artifacts/finetune/demo_order.txt`), so positions are interleaved over time.
- **+3 cm is never used in training.** It is the evaluation position.
- The can is the cola can. Hardware is the current gripper (rubber bands, pads removed); the scene is otherwise nominal.
- Recording: `~/so101_record.sh ftpos 50 25 10`, a new dataset `~/so101_data/ftpos`. The LOCK-1 dataset is not
  touched. A failed demo is re-recorded with `r`, as in G1.

## 3. Training (fixed now)

- Start from the G2 checkpoint (100k steps, sha256 `bb5e1850…`), using LeRobot `--policy.path`.
- Data: the 50 new demos plus the 80 LOCK-1 **train** episodes, mixed. The audit and validation splits stay out.
- **20,000 steps**, with batch size, optimizer and learning rate as in G2. Seed 1001. Nebius Jobs on L40S.
- The final checkpoint (step 20,000) is used. There is no checkpoint selection, which avoids tuning on outcomes.
- Engine: FP16 TensorRT on the Orin, with the same flags and frozen-cache procedure as `VC-025`. The policy is called
  `FT-FP16`.

## 4. Evaluation (real arm)

- Two blocks, each interleaved and operator-blinded, with new tokens. The runner is `so101_trial.py` with its pre-run
  seal and LOCK-2 checks.

  | Block | Scene | Trials |
  |---|---|---|
  | `T1` | cola can at the **+3 cm S1 mark** (held out) | FT-FP16 12, OLD-FP16 (`VC-025`) 12 |
  | `T0` | cola can at the training start mark (nominal) | FT-FP16 12, OLD-FP16 12 |

  Block order: T1, then T0.
- Outcome: the consensus re-judge (stress protocol §11) ∧ released ∧ no contact ∧ not aborted.
- Stop rule: the block stops after 2 operator aborts.

## 5. Analysis (fixed now)

- **Primary (T1)**: success difference FT − OLD with a Newcombe 95% interval. **Improvement detected** if the lower
  bound is above 0. Otherwise: not detected.
- **Secondary (T0)**: FT against OLD with the `stress_analysis.compare` semantics (E1 Newcombe 97.5%, E2 bootstrap
  with ≥ 5 placements, tolerances 10 pp and 5 px, ceiling rule). Verdict: GO, NO-GO or INSUFFICIENT_EVIDENCE.
- Descriptive: from the overhead videos, the operator's notes on the first grasp location (at the trained start spot
  or at the can) and the number of re-grasp attempts.
- Power, stated now: 12 against 12 detects an improvement only for a large gap. FT needs at least 4/12 if OLD is
  0/12, 6/12 if OLD is 1/12, or 7/12 if OLD is 2/12. Smaller gains read as "not detected".

## 6. Readings

| T1 | T0 | Reading |
|---|---|---|
| improvement detected | not NO-GO | The gate's finding led to a fix that the gate then confirmed, within this setting |
| improvement detected | NO-GO | The fix moved the weakness: position improved, nominal degraded |
| not detected | any | No evidence that this fine-tune fixed the position weakness; report as is |

## 7. Order lock

1. This file and the demo order are committed **before** recording.
2. The training config and the checkpoint hash are committed before the engine build. The engine hash and the schedule
   are committed before any trial.
3. Each block's sealed log is hashed into `artifacts/freeze/ft_post.json` before it is opened.

## 8. Build and schedule (fixed before the first trial, 2026-10-14)

- Checkpoint: `g2/act_ft_pos_20k/020000`, model sha256 `1385d3dd…`. ONNX sha256 `a218303e…`; torch and ONNX differ by at
  most 1.3e-6.
- FP16 engine `FT-FP16`, sha256 `4affc06d…`, built with the same frozen cache (`67fca693…`). The rebuild hash is
  identical. Engine and torch differ by at most 0.0035 in normalized units.
- Normalization: the fine-tune re-estimated the state and action statistics. The runner therefore loads per-engine
  statistics (`<token>.norm_stats.npz` for FT, the folder default for OLD = G2), via `so101_trial.py` `bdf2c3a6…`.
- Sealed schedule `~/.edgeqgate_sealed/stress_ft/stress_sealed.json`, sha256
  `996d4a9a584c20d80ce221add95bec8cb4893b1b0c44a0990634fd113653d053`. Blocks run T1, then T0, with 24 trials each.
  Public copy: `artifacts/finetune/stress_schedule_public.json`. Analysis: `scripts/ft_analysis.py`.
- Runner commands: `so101_trial.py --blind T1 ft`, then `--blind T0 ft`.

## 9. Amendment 1 (2026-10-14, before the first trial): the end judge uses the validated prompt

The end-of-trial Cosmos question in T1 and T0 uses the C1 p1 prompt chosen in
`docs/cosmos_judge_eval_preregistration.md`: on eval it caught 20/21 failures with 5/252 false alarms. It runs with
max_tokens 768 and the `Answer:` parse. This makes the 48 trials a **prospective, live check** of that prompt on new
data. It stays descriptive and is never used for an outcome. Runner `so101_trial.py` `891a6e95…`. The live Cosmos
configuration was restored on the Orin.

## 10. Amendment 2 (2026-10-14, before the first trial; interpretation and safety only)

- **Readings, refined.** The §6 row "improvement detected / not NO-GO" lumped two cases together. They are separated:

  | T1 | T0 verdict | Reading |
  |---|---|---|
  | improvement detected | GO | Position improved, and nominal performance is maintained within tolerance |
  | improvement detected | INSUFFICIENT_EVIDENCE | **Position improved; whether nominal performance is maintained is undetermined** |
  | improvement detected | NO-GO | The fix moved the weakness: position improved, nominal degraded |
  | not detected | any | No evidence that this fine-tune fixed the position weakness |

- **Normalization guard.** Each engine must load the normalization file recorded for it. A sealed manifest
  (`norm_manifest.json`: token → sha256 of the normalization file) is checked before each engine starts. A missing or
  mismatched file **refuses the run** instead of falling back to the folder default.
- **Policy-server timeout.** A policy reply that does not arrive within 5 s aborts the trial as `runtime_error`, and the
  server is restarted before the next trial. The runner no longer waits forever.
- Procedure, sample sizes and the primary rule are unchanged.
- Runner `so101_trial.py` `ee80efe4…`; sealed normalization manifest `stress_ft/engines/norm_manifest.json` sha256 `6ecf919d95ac79a5…` (one token → FT normalization, one → G2). Verified with `tests/runner_abort_harness.py`, which now includes a policy-server timeout case.

## 11. Amendment 3 (2026-10-14, before any T1/T0 trial): a missing manifest also refuses the run

- External review 4 found a gap in the §10 guard. The manifest was checked only if `norm_manifest.json` existed. If
  the file itself was missing, the runner fell back to the folder default without a check.
- **Change**:
  - The normalization choice moved into `resolve_norm()`. In the fine-tune blocks (`--blind T1|T0 ft`), a missing
    manifest now **refuses the run**. So do a mismatched hash and an engine absent from the manifest.
  - Other modes are unchanged.
- **Tests**: `tests/runner_abort_harness.py` gained six `resolve_norm` cases:
  - a missing manifest is refused;
  - the per-engine file is used when no manifest is required;
  - both mapped engines resolve;
  - a tampered file is refused;
  - an unmapped engine is refused.
  The harness now runs in CI.
- **On the Orin**, both sealed engines resolve under the new guard. Only pass/fail was printed, not the
  token-to-file mapping.
- Runner `so101_trial.py` `a3e6fd7f61752406…`, deployed to the Orin; the previous `ee80efe4` is kept as a backup.
  The sealed schedule `996d4a9a…`, the engines and the manifest `6ecf919d…` are unchanged.
- The procedure, sample sizes and primary rule are unchanged.

## 12. Amendment 4 (2026-10-14, during T1 and before any unsealing): a −3 cm symmetry block T2

- **Why**: during T1, after trial 8, the user asked whether a −3 cm test is needed to judge the fine-tune's effect.
  +3 cm tests only the side where the weakness was observed (stress S1, 0/3).
  - The demonstrations cover −4, −2, 0, +2 and +4 cm, so −3 cm is the mirror held-out position.
  - This amendment is written while T1 is still running. Nobody has unsealed or analysed any T1 or T0 trial.
  - The operator has reported failures by trial number only. The operator also reported that the two policies'
    motions look visibly different; see the operator notes.
  - The decision to add T2 does not depend on any cell-level outcome.
- **Design**:
  - Block **T2**: the cola can at a new **−3 cm** tape mark, on the same axis as the other marks, midway between
    −2 and −4.
  - FT-FP16 12 and OLD-FP16 (`VC-025`) 12, interleaved by the (k + U)/n key.
  - Seed key `FINETUNE/schedule/T2/v1`, with new random tokens.
  - Sealed schedule `~/.edgeqgate_sealed/stress_ft2/stress_sealed.json`, sha256
    `13620d947b67cf5cf0bb643e4b0ebcf8ca132f95fe8ce3f3e8c598a5b8be8587`. The public copy is
    `artifacts/finetune/stress_schedule_T2_public.json`.
  - The engines are hard links to the same files as T1/T0 (sha256 `4affc06d…` and `3b19f7eb…`).
  - The normalization manifest is `stress_ft2/engines/norm_manifest.json`, sha256 `4f5f3bcba0ddb980…`.
  - It was built on the Orin by `scripts/ft2_setup_orin.py`, which prints no token-to-cell mapping. The local
    copy of the sealed schedule was deleted unread.
- **Order**:
  - T2 runs after T0. The runner change below is deployed to the Orin only after T0 ends, never during a block.
  - T2's sealed log is hashed into `artifacts/freeze/ft2_post.json` before it is opened.
- **Rule**: the same as the T1 primary. A Newcombe 95% interval for FT − OLD; improvement at −3 cm is detected if the
  lower bound is > 0.
  - T1 stays the primary result. T2 is a separately reported symmetry check, with no multiplicity adjustment of T1.

  | T1 (+3 cm) | T2 (−3 cm) | Reading |
  |---|---|---|
  | detected | detected | The fine-tune improved held-out positions on both sides of the trained start |
  | detected | not detected | Improvement shown at +3 cm only; the −3 cm side is not shown |
  | not detected | detected | No evidence at the observed weakness; the −3 cm improvement is reported, not promoted |
  | not detected | not detected | No evidence that this fine-tune fixed position shifts |

- **Code**:
  - The runner accepts `--blind T2 ft2`: the sealed folder `stress_ft2`, the manifest required, the C1 end-of-trial
    judge. T1 and T0 behaviour is unchanged. The runner harness passes.
  - `scripts/ft_analysis.py` gains `--t2 <sealed dir>`, tested on relabelled data.
  - The runner hash at deployment is recorded when it is deployed: `so101_trial.py` `514bfee22a436821…`, deployed
    to the Orin after T0 ended (2026-10-14). The previous `a3e6fd7f` is kept as a backup.

## 13. Amendment 5 (2026-10-14, during T0, before any unsealing): exploratory gripper-chatter metric

- **Trigger**: during T0 the operator reported much less gripper chatter than in earlier experiments.
- **Metric**, fixed before any unsealing:
  - **chatter** = mean |second difference| of the commanded gripper action (`action[:, 5]` in each trial's
    `*_traj.npz`, in degrees per step²), over all steps of a non-aborted trial.
  - A second version is restricted to steps where the commanded gripper is closed by more than half of its range
    in that trial (the hold phase).
- **Comparisons**, all **exploratory** with no decision attached, as medians per arm and Mann–Whitney U:
  1. FT vs OLD within T1, T0 and T2;
  2. the OLD FP16 arm here vs the same VC-025 engine in the FP16 block (rubber bands, 2026-10-13), to separate
     the policy from the session;
  3. the FP16 blocks vs G6 cells (FP32/INT8, anti-slip pads), descriptive only, since the gripper changed.
- No result from this metric changes the T1/T0/T2 readings.
