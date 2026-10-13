# Positive control — pre-registration v1 (LOCKED before the engines are built)

Status: locked on 2026-10-13 by the commit that adds this file. It was written before any positive-control ONNX,
engine, offline score or trial existed. The user decided to run it (2026-10-13).

## 1. Why

Every candidate so far was a reasonable INT8 build, and the gate never had to say NO-GO: every verdict is
"insufficient evidence". A gate is only credible if it can catch a bad candidate. This test feeds the pipeline a
**deliberately broken but realistic** INT8 build and asks two things:

> Q1. Does the offline audit flag it?
> Q2. Does the real arm agree with the offline verdict?

## 2. Candidates (a calibration-data mistake)

Two variants are built the same way as `VC-007` (INT8, calibration size 64, success-only frames, per-tensor). They
use the same 64 calibration samples and the same robot states. Only the **calibration images** are replaced.

| Code | Calibration images | Realistic mistake it stands for |
|---|---|---|
| `PC-N` | i.i.d. standard normal noise in normalized image space (seeded) | calibrating on synthetic or random tensors |
| `PC-B` | all-black frames (pixel 0, then the training normalization) | calibrating while a camera feed is dead |

The FP32 checkpoint, export, TensorRT flags and frozen timing cache are unchanged (`build_grid_lerobot.py` options,
`build_engines_orin.sh`). Script: `scripts/build_positive_control.py`.

## 3. Offline gate (Q1), fixed now

The offline pipeline is the one used for the 25 cells: Orin engine outputs on the 2,000 audit states, then
`g4_build_payload.py`, then CVaR@90 with 200 bootstrap replicates (`audit_job_g4.py` code).

- **Offline NO-GO** if the candidate's `score_mag` 95% CI lower bound is above the highest `score_mag` 95% CI upper
  bound among the 24 INT8 cells. The same rule is applied for `score_align`; NO-GO needs both.
- **Selection for the real arm**: if exactly one variant is offline NO-GO, run it. If both are, run the one with the
  larger `score_mag` point estimate. If neither is, run the one with the larger `score_mag` anyway, and Q1 is
  reported as "not flagged".

## 4. Real-arm test (Q2)

- The selected variant gets **12 trials** and FP32 `VC-000` gets **12 trials**. They are interleaved with seed key
  `POSITIVE-CONTROL/schedule/v1`, using new anonymous tokens, and the operator is blinded. Runner:
  `so101_trial.py --blind P0 pc` (the same runner as stress v2 and FP16, with the pre-run seal and LOCK-2 check).
- Hardware and scene: the current rubber-band gripper, the cola can at the training start mark, and the nominal
  scene, as in the FP16 block.
- **Safety**: a broken policy may move unpredictably. Joint commands stay clipped to the follower limits, as always.
  The operator keeps a hand on Ctrl+C. An operator abort counts as a failure (`unsafe`). **Stop rule: after 2
  operator aborts the block stops**, and the trials so far are reported. Nothing else changes after an outcome has
  been seen.
- Outcome: the consensus re-judge (stress protocol §11) ∧ released ∧ no human contact ∧ not aborted.
- Analysis (`scripts/stress_analysis.py` `compare`): the reference is VC-000.
  - E1 uses Newcombe at 97.5% (family = 2 endpoints). E2 uses the bootstrap and needs at least 5 placements per arm.
  - Verdicts are GO, NO-GO or INSUFFICIENT_EVIDENCE.
  - With 12 against 12 trials, **E1 materially_degraded needs the candidate at 5/12 or below** when FP32 is 12/12,
    or at 4/12 or below when FP32 is 11/12.

## 5. Readings, fixed now

| Offline | Real arm | Reading |
|---|---|---|
| NO-GO | NO-GO | The gate catches a gross calibration error, and the offline verdict is confirmed |
| NO-GO | not NO-GO | The offline audit is over-sensitive here; the policy tolerates even this error |
| not flagged | NO-GO | The offline audit missed a real failure: a strong negative result for the audit |
| not flagged | not NO-GO | The policy is insensitive to this error; there is no evidence about the audit |

## 6. Order lock

1. This file is committed **before** the ONNX build.
2. The offline scores and the selection are committed before the trial schedule is generated and before any trial.
3. After the last trial, the sealed log is hashed into `artifacts/freeze/pc_post.json`. Only then is it opened.

## 7. Schedule (fixed after selection, before any trial)

- Selected: **PC-B** (`artifacts/positive_control/offline_selection.json`).
- Sealed schedule `~/.edgeqgate_sealed/stress_pc/stress_sealed.json`, sha256
  `639fa756d85412ed421be9d9f748161ff49baed1a892274a4ea9e7223823b876`, with 24 trials (PC-B 12, VC-000 12). The public
  copy is `artifacts/positive_control/stress_schedule_public.json`. Script: `scripts/pc_schedule.py`.
- Runner `so101_trial.py` `61d8e194…`, invoked as `--blind P0 pc`.

## 8. Amendment 1 (2026-10-13, before any positive-control trial; interpretation only)

The real-arm column in §5 lumped GO and INSUFFICIENT_EVIDENCE together as "not NO-GO". They are separate readings.
The procedure, sample sizes and stop rule are unchanged.

| Offline | Real-arm verdict (PC-B vs FP32) | Reading |
|---|---|---|
| NO-GO | **NO-GO** (E1 or E2 materially degraded) | The offline warning for a gross calibration error matches the real arm |
| NO-GO | **GO** (both endpoints tolerance-compatible) | In this setting the offline warning was too strong; the policy tolerated this error |
| NO-GO | **INSUFFICIENT_EVIDENCE** | Unresolved. The real-arm meaning of the warning is not settled at this sample size. This is **not** read as "the policy tolerated it" or as "the audit was over-sensitive" |

Scope, stated now: even a NO-GO / NO-GO result shows only that the audit catches a **gross** calibration error. It says
nothing about whether the audit ranks normal INT8 candidates correctly; G6 found no evidence that it does.

## 9. Runner fix before the first trial (2026-10-13)

An external review found that a Ctrl+C before the first state was recorded raised an exception, so the abort record
was lost. This is the abort path this block relies on. The runner (`so101_trial.py` `59b0669c…`) now:
- saves an empty trajectory with `aborted=true`;
- records runtime errors as aborts;
- waits for any in-flight policy reply, so that the next trial cannot read it;
- passes each frame's capture time to the shadow supervisor.

Verified with `tests/runner_abort_harness.py`, which needs no hardware. No outcome or analysis rule changes.

## 10. Amendment 2 (2026-10-13, before any trial): Cosmos replayed offline

The Nebius endpoint could not be scheduled: a start request had waited 20+ minutes with no L40S instance allocated.
The block therefore runs **without the live shadow supervisor**. That supervisor never affects the arm or the
outcome, so nothing in §3–§5 changes.

When the endpoint is up, Cosmos-Reason2 is replayed offline on each trial's saved overhead video:
- the same 2 Hz sampling (every 15th frame) with the same CONTINUE / FALLBACK / ABORT prompt;
- the same end-of-trial question on the last frame (`scripts/d4_replay.py`, written before the trials).

Two differences from live operation are disclosed: the replay sees AV1-compressed frames instead of raw camera frames,
and live latency is not measured. The replay is descriptive (EX-3) and is never used for an outcome.
