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
    `*_traj.npz`, in gripper units per step², where the gripper is 0–100; unit corrected 2026-10-15, values unchanged), over all steps of a non-aborted trial.
  - A second version is restricted to steps where the commanded gripper is closed by more than half of its range
    in that trial (the hold phase).
- **Comparisons**, all **exploratory** with no decision attached, as medians per arm and Mann–Whitney U:
  1. FT vs OLD within T1, T0 and T2;
  2. the OLD FP16 arm here vs the same VC-025 engine in the FP16 block (rubber bands, 2026-10-13), to separate
     the policy from the session;
  3. the FP16 blocks vs G6 cells (FP32/INT8, anti-slip pads), descriptive only, since the gripper changed.
- No result from this metric changes the T1/T0/T2 readings.

## 14. Results (2026-10-14, unsealed after T2)

Order kept:
1. T1 and T0 logs were hashed (`ft_post.json`), then T2 was run and hashed (`ft2_post.json`).
2. The video consensus re-judge was run blind to cells (`artifacts/finetune/rejudge/`). Block totals were T1 15/24,
   T0 22/24 and T2 12/24, each equal to the live automatic judge.
3. Only then was the data unsealed. The unsealed logs match both post records (`artifacts/trials/ft_unsealed/`,
   `ft2_unsealed/`).

Analysis: `scripts/ft_analysis.py`, written to `artifacts/reports/ft_analysis.json`.

| Block | FT-FP16 | OLD-FP16 (VC-025) | FT − OLD, Newcombe 95% | Pre-registered reading |
|---|---|---|---|---|
| **T1, +3 cm (primary)** | **12/12** | 3/12 | **+75.0 pp [+37.8, +91.1]** | **improvement detected** |
| **T2, −3 cm (symmetry, §12)** | **10/12** | 2/12 | **+66.7 pp [+26.9, +83.6]** | **improvement detected** |
| T0, training mark (secondary) | 10/12 | 12/12 | E1 degradation [−15.4, +49.0] pp at 97.5%, indeterminate; E2 +5.3 px [−7.3, +30.8], indeterminate | **INSUFFICIENT_EVIDENCE** |

- **Reading (§10 and §12 tables)**:
  - T1 detected and T0 INSUFFICIENT_EVIDENCE: **"Position improved; whether nominal performance is maintained is
    undetermined."**
  - With T2 also detected: **the fine-tune improved held-out positions on both sides of the trained start.**
  - At the training mark the fine-tune failed twice (T0 trials 18 and 22: pushed off the coaster, knocked over while
    setting down) and OLD did not fail. The interval cannot separate this from noise at 12 vs 12.
- **Failure modes by arm**, from the operator notes plus the unsealed cells:
  - The repeated "set half on the coaster" failures in T1 (2, 3, 6, 8) were all OLD.
  - The T2 failures the operator saw were trial 12 (FT: set down, then knocked over by the gripper moving nearby)
    and trial 14 (OLD: never grasped).
- **Live Cosmos C1 judge**, prospective on new data (`artifacts/reports/ft_cosmos_live_judge.json`):
  - It caught **21/23 failures** (Wilson 95% 0.73–0.98) with **1/49 false alarms** (0.004–0.107) and no
    abstains. Median latency was 392 ms.
  - By block: T1 caught 8/9, T0 1/2, T2 12/12. The only false alarm was in T0.
  - The prompt chosen on the dev split and checked on eval held on live trials.
- **Gripper chatter** (§13, exploratory; `artifacts/reports/ft_chatter.json`). Values are the median mean
  |Δ²| of the commanded gripper, in gripper units (0–100) per step²:

  | | FT | OLD | MWU p |
  |---|---|---|---|
  | T1 (+3 cm) | 0.134 | 0.588 | 0.012 |
  | T2 (−3 cm) | 0.147 | 0.662 | 0.0004 |
  | T0 (training mark) | 0.167 | 0.106 | 0.0003 |

  - Off the training position, OLD chatters about 4× more than FT, consistent with the hesitation and regrasping
    seen in stress S1.
  - At the training mark, FT chatters more than OLD.
  - No difference was detected between OLD today and the same VC-025 engine in the FP16 block (p = 0.13). This does
    not show that the session had no effect (correction, external review 6).
  - **Post hoc, not in §13**: in the FP16 block the INT8 cell VC-002 has a median of 0.314, against 0.134 for
    VC-025 FP16 and 0.162 for VC-000 FP32. In G6, VC-002 has 0.288 against 0.113 for VC-000. This is about twice
    the chatter at a similar success rate. It is reported as a hypothesis for a pre-registered check: INT8 can
    change motion smoothness without changing success.
- **Limitations**:
  - The operator reported that the two policies' motions were visibly distinguishable (T1 and T2), so operator
    blinding was partial. Outcomes come from the automatic judge and the video re-judge, which agree block by block.
  - The −3 cm mark was added during the session (§12).
  - One task, one object, 12 trials per arm per position.

## 15. Amendment 6 (2026-10-15, after §14, before any T0R trial): an independent replication at the training mark

- **Why**: external review 6 suggested one more arm block: an independent replication of T0. It should check whether
  the two failures of the fine-tune at the training mark repeat, not try to settle non-inferiority.
  - T0 was FT 10/12 against OLD 12/12. Both FT failures disturbed the can at placement: trial 18 pushed it off the
    coaster, trial 22 knocked it over while setting it down.
  - This amendment is written after T0 was unsealed, so the design knows the T0 outcome. That is why the primary
    question is a descriptive replication question and the pooled test is labelled as chosen after T0.
- **Design**:
  - Block **T0R**: the cola can at the training start mark, rubber-band gripper, the same scene as T0.
  - FT-FP16 12 and OLD-FP16 (`VC-025`) 12, interleaved by the (k + U)/n key.
  - Seed key `FINETUNE/schedule/T0R/v1`, with new random tokens.
  - Sealed schedule `~/.edgeqgate_sealed/stress_ft3/stress_sealed.json`, sha256
    `7b589a8c1b6cca0e96abb2e99597ff527d62006af11e59aa6bece1a9fad516b5`. The public copy is
    `artifacts/finetune/stress_schedule_T0R_public.json`.
  - The engines are hard links to the T1/T0 files (sha256 `4affc06d…` and `3b19f7eb…`).
  - The normalization manifest is `stress_ft3/engines/norm_manifest.json`, sha256 `05055421302ef09d…`.
  - The engine folder was built by `scripts/ft3_setup_orin.py`, which prints no token-to-cell mapping. The local
    copy of the sealed schedule was deleted unread.
- **Runner**:
  - `so101_trial.py --blind T0R ft3`, sha256 `609ee74ba9bf0802…`, deployed 2026-10-15 with no block running.
  - The previous `514bfee2` is kept as a backup.
  - Behaviour is the same as T0: the manifest is required, the C1 end-of-trial judge records if the endpoint is up,
    and the stop rule is 2 operator aborts.
- **Outcome**: as §4. The consensus video re-judge is run blind to cells before unsealing.
- **Failure modes**:
  - Before unsealing, each failed trial gets one mode label from the operator notes and the overhead video, written
    blind to cells into `artifacts/finetune/T0R_modes.json`.
  - Labels: `placement disturbance` (the can is pushed or knocked while or after it is set down), `grasp`,
    `transport` or `other`.
- **Analysis** (`scripts/ft3_analysis.py`, written now and dry-run on relabelled T0 data):
  - **Primary (replication, descriptive)**: the FT failures in T0R and their modes.

    | FT failures in T0R | Reading |
    |---|---|
    | 0 | The two T0 failures did not repeat in 12 trials. This does not show the failure is absent: the Wilson 95% upper bound for 0/12 is 24%. |
    | ≥ 1, at least one `placement disturbance` | The training-mark failure mode repeats. Next: a targeted fix (release-and-retreat demonstrations), not approval. |
    | ≥ 1, none `placement disturbance` | FT failed at the training mark again, by a different mode. Report as is. |

    OLD failures are reported alongside, descriptively.
  - **Secondary**: T0 + T0R pooled, 24 vs 24, with the `stress_analysis.compare` semantics (97.5%, tolerances
    10 pp and 5 px). This pooling was chosen after T0 was seen.
    - Stated now: **GO is unreachable**. Even 24/24 against 24/24 meets the ceiling rule and is indeterminate.
    - NO-GO on success needs FT ≤ 15/24 pooled (≤ 5/12 in T0R) if OLD stays 24/24.
    - The expected verdict is INSUFFICIENT_EVIDENCE. Approval of FT at the training mark stays on hold either way.
  - **Exploratory**: gripper chatter (§13 metric), FT against OLD in T0R, MWU two-sided.
    - T0 showed FT > OLD (0.167 against 0.106, p = 0.0003).
    - The direction counts as repeated if FT > OLD with p < 0.05. Otherwise the reading is "not repeated".
- **Order**: run T0R → hash the sealed log into `artifacts/freeze/ft3_post.json` → blind consensus re-judge and mode
  labels → unseal into `artifacts/trials/ft3_unsealed/` → `ft3_analysis.py`.
- **Limitations stated now**: operator blinding is partial, as in T1/T2, though the policies' motions differ less at
  the training mark. It is one more session, on another day, at the same scene.

## 16. T0R results (2026-10-15, unsealed after ft3_post.json)

Order kept:
1. The T0R sealed log was hashed into `artifacts/freeze/ft3_post.json` (pushed).
2. The video consensus re-judge was run blind to cells: 23/24, equal to the live automatic judge.
3. The failure-mode label was written blind (`artifacts/finetune/T0R_modes.json`: trial 2 → `grasp`).
4. Only then was the log unsealed. It matches the post record (`27cedfd6…`).

Analysis: `scripts/ft3_analysis.py`, written to `artifacts/reports/ft3_analysis.json`.

| | FT-FP16 | OLD-FP16 (VC-025) | Reading |
|---|---|---|---|
| **T0R, training mark (primary, replication)** | **12/12** | 11/12 (trial 2: pushed the can while approaching, never grasped) | **Not repeated in 12 trials.** The FT failure rate's Wilson 95% upper bound is 24% |
| T0 + T0R pooled (secondary, chosen after T0) | 22/24 | 23/24 | E1 degradation +4.2 pp [−16.3, +25.3] at 97.5%; E2 −2.0 px [−8.6, +9.8]; **INSUFFICIENT_EVIDENCE**, as stated in advance |
| Gripper chatter (exploratory) | median 0.141 | 0.131 | MWU p = 1.0: the T0 direction (FT > OLD) **did not repeat** |

- **Reading**:
  - The two placement-disturbance failures of FT in T0 (trials 18 and 22) did not recur in 12 more trials at the same
    mark, on another day.
  - This does not show the failure mode is absent. Non-inferiority at the training mark is still not settled
    (pooled INSUFFICIENT_EVIDENCE).
  - FT stays the candidate to validate where the start position varies. It is not yet a replacement at the trained
    spot.
- **Live Cosmos C1 judge** (prospective): it caught 1/1 failures with 1/23 false alarms and no abstains.
  - Over all fine-tune blocks (T1, T0, T2, T0R; 96 trials): 22/24 failures caught, 2/72 false alarms.
- **Limitations**: operator blinding is partial, as in T1/T2. It is one more session, at the same scene. The touch
  calibration for the Isaac Sim twin was done just before the block. The grid sheet was then removed, and the wrist
  check failed until it was.

## 17. Amendment 7 (2026-10-17, after §16, before any generalization trial): a held-out object and positions beyond the demonstrations

- **Why**: FT is the candidate to validate where the start position varies (§14, §16), but its reach is untested
  beyond ±3 cm and the cola can. Two earlier ideas would not answer that.
  - **±4 cm** is inside the fine-tune demonstrations (−4, −2, 0, +2, +4 cm), so it is not a held-out test.
  - **The yellow can at the training mark** gave 48/48 for the old policy (stress v2, S4). Both policies would sit at
    the ceiling, so the comparison would be uninformative.
  - So this amendment tests FT where the old policy is expected to fail, with one new element each time.
  - It is written after T1, T0, T2 and T0R were unsealed, so the design knows those results. No trial of the blocks
    below exists.
- **Design**: FT-FP16 12 and OLD-FP16 (`VC-025`) 12 per block, interleaved by the (k + U)/n key.
  - Seed key `FINETUNE/schedule/GEN/v1`, with new random tokens. Block order is fixed: **TYP → T6P → T6M**.

  | Block | Scene | Role |
  |---|---|---|
  | `TYP` | **yellow can** (175 ml, 50 mm) at the **+3 cm (S1) mark**: a held-out object at a held-out position | primary |
  | `T6P` | cola can at a new **+6 cm** mark, beyond the demonstration range | secondary |
  | `T6M` | cola can at a new **−6 cm** mark | secondary |

  - The ±6 cm marks are taped on the same axis as the other marks.
  - Sealed schedule `~/.edgeqgate_sealed/stress_ft4/stress_sealed.json`, sha256
    `59d6bced0bbaf049e6f99dda6629a3294c69671afb105aa4bd17fba883275553`. The public copy is
    `artifacts/finetune/stress_schedule_GEN_public.json`.
  - The engines are hard links to the T1/T0 files (sha256 `4affc06d…` and `3b19f7eb…`).
  - The normalization manifest is `stress_ft4/engines/norm_manifest.json`, sha256 `e358eb33f4281c1b…`.
  - The engine folder was built by `scripts/ft4_setup_orin.py`, which prints no token-to-cell mapping. The local
    copy of the sealed schedule was deleted unread.
- **Checks before the first trial of a block** (none uses a policy):
  - **Yellow can judge values (TYP)**: `so101_can_calib.py stress_can_TYP.json`, measured as in the stress protocol
    §4. It is re-measured because the camera-to-arm registration has differed between sessions.
    - The judge must call the centred can a success with base distance ≤ 5 px; otherwise TYP is not run.
    - The file and its sha256 are committed before the first TYP trial. The runner refuses TYP without the file.
  - **Reach (T6P, T6M)**: the operator moves the follower with the leader arm to the can at the ±6 cm mark once.
    - If the gripper cannot close around the can there, that block uses a ±5 cm mark instead.
    - The choice is written in the decision log before the block's first trial.
- **Runner**: `so101_trial.py --blind TYP|T6P|T6M ft4`, sha256 `f499c1b0009c6b5d…`, deployed 2026-10-17 with no
  block running. The previous `609ee74b` is kept as a backup.
  - The blocks behave as T1: the manifest is required, and the C1 end-of-trial judge records if the endpoint is up.
  - The stop rule is 2 operator aborts per block.
- **Outcome**: as §4. The consensus video re-judge (stress §11, built for the yellow can) is run blind to cells
  before unsealing. Failure modes are labelled blind, as in §15.
- **Analysis** (`scripts/ft4_analysis.py`, written now and dry-run on relabelled T1/T2 data):
  - **Primary (TYP)**: FT − OLD success difference, Newcombe 95%; improvement detected iff the lower bound > 0.
  - **Secondary (T6P, T6M)**: the same rule, each reported separately, with no multiplicity adjustment of the primary.
  - Power, as §5: 12 against 12 detects only a large gap.

  | TYP | Reading |
  |---|---|
  | detected | The position fix carries to a new object at a held-out position |
  | not detected, FT ≥ 9/12 | FT handles the object, but the old policy did too often enough that no gain is shown |
  | not detected, FT < 9/12 | No evidence that the fix carries to this object |

  | T6P / T6M | Reading |
  |---|---|
  | detected | The fine-tune extrapolates past its demonstration range on that side |
  | not detected | No evidence of extrapolation on that side; the supported range stays ±3 cm |

- **Date stop**: a block not started by 2026-10-25 is reported as not run, never partially analysed by choice.
- **Order**: run the blocks → hash the sealed logs into `artifacts/freeze/ft4_post.json` → blind consensus re-judge
  and mode labels → unseal into `artifacts/trials/ft4_unsealed/` → `ft4_analysis.py`.
- **Limitations stated now**: operator blinding is partial (the motions differ), as in T1/T2. The yellow can's lower
  mass (190 g against 268 g) also changes the grasp.

- **Yellow can judge values, measured 2026-10-17 before any TYP trial**: `artifacts/finetune/stress_can_TYP.json`,
  sha256 `7ebd6cc4dd59622e…`. Top radius median 20.9 px, `r_range` [16, 29], `top_to_base` [4.4, 22.4]; self-check
  success with base distance 0.0 px (PASS). The same file is on the Orin beside the runner.
- **Reach check, 2026-10-17 before any T6P or T6M trial** (operator, leader arm, not recorded): at both the +6 cm and
  −6 cm marks the gripper reaches and closes around the cola can, so both blocks keep ±6 cm.
  - At −6 cm the follower did not keep up with the leader while lifting. This is noted now as a possible arm limit at
    that position (torque or joint range), the same for both policies.
  - A T6M result with both policies failing on the lift is read as that limit, not as evidence about the fine-tune.
    Lift failures stay labelled `transport` or `grasp` by the blind mode labelling.

## 18. Generalization results (2026-10-18, unsealed after ft4_post.json)

Order kept:
1. The three sealed logs were hashed into `artifacts/freeze/ft4_post.json` (pushed) before any was opened.
2. The video consensus re-judge was run blind to cells: TYP 3/24, T6P 0/24, T6M 8/24, equal to the live automatic
   judge and to the operator's reports.
3. The failure-mode labels were written blind (`artifacts/finetune/GEN_modes.json`, 61 failures).
4. Only then were the logs unsealed. All three match the post record.

Analysis: `scripts/ft4_analysis.py`, written to `artifacts/reports/ft4_analysis.json`.

| Block | FT-FP16 | OLD-FP16 (VC-025) | FT − OLD, Newcombe 95% | Reading (§17 table) |
|---|---|---|---|---|
| **TYP, yellow can at +3 cm (primary)** | **0/12** | 3/12 | −25.0 pp [−53.2, +4.1] | **not detected, FT < 9/12: no evidence that the fix carries to this object** |
| T6P, cola can at +6 cm | 0/12 | 0/12 | 0.0 pp [−24.2, +24.2] | not detected: no evidence of extrapolation on the + side |
| T6M, cola can at −6 cm | **8/12** | 0/12 | **+66.7 pp [+29.9, +86.2]** | **detected: the fine-tune extrapolates past its demonstrations on the − side** |

- **Failure modes** (blind labels):
  - TYP: FT 12/12 `grasp`; OLD 8 `grasp` and 1 edge placement.
  - T6P: every failure of both policies is `grasp` (the can stays at its start; the gripper goes to the trained spot).
  - T6M: OLD 12/12 `grasp`; FT 1 `grasp`, 2 edge placements and 1 `placement disturbance` (trial 9). So FT reached
    and carried the can in 11 of 12 trials.
- **Reading**:
  - The position fine-tune does **not** carry to the smaller yellow can at +3 cm. FT's 0/12 is not a detected
    degradation (the interval includes 0), but it gives no support for object generalization.
  - The supported range is **asymmetric**: −6 cm is handled (8/12), +6 cm is not (0/12).
  - FT stays the candidate where the start varies between −6 and +3 cm with the cola can. It is not a general
    object or position solution.
- **Limitations**: operator blinding was partial, as in T1/T2. One session per block. At −6 cm the arm lagged the
  leader during the reach check; FT still lifted the can there in 11 trials, so the arm limit did not decide T6M.

- **Post-result scene note (2026-10-20, found during the Q8 hardware check)**: the overhead frames of TYP, T6P and T6M
  show small red round markers on the start axis next to the can. They are absent in T1, T0 and T0R. These markers were
  not in the demonstrations, so the generalization blocks tested FT under one more change than §17 lists: a visual
  distractor of the can's colour. The pre-registered readings in §18 stand as computed, with this limitation added. A
  re-test without the markers would separate the two effects.

## 19. Amendment 8 (2026-10-20, before any re-test trial): T6P and TYP re-run without the red markers

- **Why**: §18 found red round markers next to the can in TYP, T6P and T6M, absent from the demonstrations. This
  amendment re-runs the two no-gain blocks without them, to separate the markers from the conditions.
  - T6M showed an improvement despite the markers and is not re-run.
- **Design**: as §17, FT-FP16 12 and OLD-FP16 (`VC-025`) 12 per block, interleaved. Order fixed: **T6PR** (cola can
  at +6 cm), then **TYPR** (yellow can at +3 cm). Seed key `FINETUNE/schedule/GEN/v2`, new tokens.
  - Sealed schedule `~/.edgeqgate_sealed/stress_ft5/stress_sealed.json`, sha256
    `ba26a9ccd67c1f5dbd1216e710f0601dc5a1e7a9733e68f4fb7e8bf9606f2b6c`. The public copy is
    `artifacts/finetune/stress_schedule_GEN2_public.json`.
  - Engines `4affc06d…` (FT) and `3b19f7eb…` (OLD); manifest `24bd9984d00aab47…`.
  - Runner `so101_trial.py --blind T6PR|TYPR ft5`, sha256 `a2adda1f5ea04d02…`, deployed with no block running.
  - TYPR uses the yellow-can judge values measured on 2026-10-17 (`stress_can_TYP.json`, PASS).
- **Gate**: the re-tests run only if the health check H1 (fp16 prereg §12) does not read "not nominal".
- **Analysis**: `scripts/ft5_analysis.py` (dry-run on relabelled T6P data), the §17 rule for each block.
  - T6PR is primary, TYPR secondary.
  - Reported beside T6P/TYP. Differing results mean the markers mattered; the same results mean the §18 readings
    stand without the marker caveat.
- **Order**: H1 → T6PR → TYPR → hash into `artifacts/freeze/ft5_post.json` → blind re-judge and mode labels → unseal.
- **Date stop**: a block not started by 2026-10-25 is reported as not run.
- **Hardware note for §18 and §19 (2026-10-20)**: wrist-camera frames at the rest pose show the orange gripper band out
  of view from TYP (10-17), and the fingertips partly out of view from 10-19. A can had struck the wrist camera. The
  camera was re-aimed toward the centre before H1, which restored the T0R view. The re-tests (§19) therefore also undo
  this change; their comparison with T6P/TYP cannot separate the markers from the wrist view.

## 20. Amendment 8 results (2026-10-21, unsealed after ft5_post.json)

Order kept:
1. Both sealed logs were hashed into `artifacts/freeze/ft5_post.json` (pushed) before either was opened.
2. The consensus re-judge was run blind to cells: T6PR 0/24, TYPR 0/24, equal to the live judge and the operator's
   reports (`artifacts/finetune/rejudge/{T6PR,TYPR}_consensus.json`).
3. Failure-mode labels were written blind (`artifacts/finetune/GEN2_modes.json`): all 48 at the grasp stage.
4. Only then were the logs unsealed. They match the post record (`47e8a484…`, `aad20c02…`).

Analysis: `scripts/ft5_analysis.py`, written to `artifacts/reports/ft5_analysis.json`. Flagged: H1 read "unclear"
(fp16 prereg §13).

| Block | FT-FP16 | OLD-FP16 (`VC-025`) | Difference, Newcombe 95% | Reading | Beside §18 |
|---|---|---|---|---|---|
| **T6PR** (primary), cola can +6 cm | 0/12 | 0/12 | 0 pp [−24.2, +24.2] | no improvement detected | T6P 0/12 vs 0/12: the same |
| **TYPR** (secondary), yellow can +3 cm | 0/12 | 0/12 | 0 pp [−24.2, +24.2] | no improvement detected | TYP 0/12 vs 3/12: OLD lost its 3 successes |

- **Failure kinds** (blind labels, then read by cell): FT failed every trial with (a), never finding the can's start
  position (24/24). OLD failed with (a) except six (b) trials (T6PR 2, 4; TYPR 18, 19, 21, 24), where it reached the
  can and pushed it away while closing.
- **Reading**:
  - **T6PR**: the §18 reading stands without the marker caveat. At +6 cm neither policy succeeds; +6 cm stays outside
    the fine-tuned policy's verified range.
  - **TYPR**: FT is again 0/12, so the §18 reading for FT (no gain on the yellow can) stands. OLD fell from 3/12 to 0/12.
    The red markers and the wrist view were restored together, so which change mattered cannot be separated. That OLD's
    earlier successes depended on the marker period is possible but not shown.
  - The verified range in the next-test plan stays: cola can, −6 to +3 cm.
- **Limitations**: one session per block; 12 vs 12 detects only a large gap; scene status "unclear" by H1.
