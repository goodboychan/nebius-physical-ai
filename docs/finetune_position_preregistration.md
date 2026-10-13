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
