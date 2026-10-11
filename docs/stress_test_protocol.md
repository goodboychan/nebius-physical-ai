# Stress test protocol v1 — LOCKED

Status: **locked 2026-10-11**, after QuantGate `LOCK-3` and the G6 analysis, before the first stress trial. The lock is
the commit that adds this file; its sha256 goes in `docs/decision_log.md`. The protocol does not change any G6 analysis.
Decisions are the user's (2026-10-10 and 2026-10-11).

## 1. Question

G6 ended near ceiling: FP32 24/25, INT8 cells 9/10 to 25/25, and no detected difference between INT8 cells or against
FP32 (`artifacts/reports/g6_analysis.json`). Quantization error often shows up when inputs leave the training
distribution. The stress test asks:

> Under conditions the policy never saw in its demonstrations, do the worst-fidelity INT8 artifacts degrade more
> than the best-fidelity INT8 artifact and the FP32 reference?

This is a separate question from G6. The policy, engines and runtime are unchanged.

## 2. Artifacts (from LOCK-2, no new builds)

| Role | Cell | Configuration |
|---|---|---|
| reference | `VC-000` | Orin FP32 engine (G6 `ARM-FP32`) |
| best fidelity | `VC-002` | INT8, calib 16, success-only, per-channel — top of `score_align` and `score_mag` |
| worst fidelity | `VC-005` | INT8, calib 16, late-phase-only, per-tensor — bottom of both |
| practitioner default | `VC-020` | INT8, calib 1024, success-only, per-channel — top of `score_cheap_A` |

The engine files are the G6 files, hard-linked under new anonymous tokens (the G6 token map was published when G6 was
unsealed).

## 3. Conditions and schedule

| Code | Change | Everything else |
|---|---|---|
| `S1` | Cola can (the training can) at a start mark **shifted 3 cm** sideways from the training start mark, same orientation | as G6 |
| `S4` | **Yellow can**: 175 ml, 190 g, 50 mm diameter, 10 cm tall (training can: cola, 268 g, 66 mm), at the training start mark | as G6 |

- The S1 direction is perpendicular to the line from the training start mark to the coaster, toward the side with
  more free table space. The operator tapes the new mark once, before the first S1 trial. The first S1 trial's
  overhead video records where it is. The mark does not move afterwards.
- 4 cells × 2 conditions × **12 trials** = 96 trials.
- Blocks run by condition, because the scene changes physically. The block order comes from the seed: **S1 first, then
  S4**. Within a block, cells are interleaved with the G6 rule: key (k + U)/n, seeded from
  `seed_from(PREREG-SEED-2026-09-14, "STRESS/schedule/v1", ranking_hash)`.
- Schedule: `scripts/stress_schedule.py`. Public file `artifacts/stress/stress_schedule_public.json`. Sealed file on
  Orin `~/.edgeqgate_sealed/stress/stress_sealed.json`, sha256
  `9549b96be27644dce90b0358888114e152c98d5a10b3628bdc4cc08407b190aa`. The operator sees only trial numbers.
  Latency is hidden on screen and in the public log, as in G6.
- Execution is identical to G6: 30 Hz, chunk 100, prefetch 10 + blend 4, 60 s, the same release and contact questions,
  and invalid trials rerun under the same number. Runner: `so101_trial.py --blind S1|S4`.
- Session checks are the G6 checks: light, wrist and coaster.

## 4. Success criterion

The success criterion is `docs/success_criterion.md`, unchanged. For **S4 only**, the two can-geometry values in §3 of
that file are measured for the yellow can, because they depend on the can's height and lid:

- **Procedure** (`scripts/so101_can_calib.py`, before any S4 trial):
  1. Stand the yellow can upright and centered on the empty coaster.
  2. Find the bright top circle over 30 overhead frames.
  3. Set the perspective offset = coaster center − median top center.
  4. Set the top-radius range = [floor(0.81 r), ceil(1.34 r)]. These ratios reproduce the locked cola range: median cola
     top radius 20.9 px over 30 G6 RETEST end frames, against the locked range 17–28.
  5. The judge must call the centered can a success with base distance ≤ 5 px. If it does not, no S4 trials are run and
     the issue is reported.
- The result (`stress_can_S4.json`) and its sha256 are committed to the decision log before the first S4 trial. This
  is a measurement made before any policy outcome. Nothing else in the criterion changes.

## 5. Analysis (`scripts/stress_analysis.py`, sha256 `9b3d1084…`, committed with this lock)

E1 is binary success. E2 is placement error in px: the base distance in every non-aborted trial where the can top is
detected, the same definition as G6. The decision semantics are those of `docs/aep_physical_registration_v1.md`:

- `tolerance_compatible` if the CI upper bound is below the tolerance.
- `materially_degraded` if the CI lower bound is above it.
- `indeterminate` otherwise.
- Tolerances are E1 10 pp and E2 5 px.
- Ceiling rule: if both success rates are ≥ 95%, E1 is `indeterminate (ceiling)`.

**Primary**, per condition: `VC-005` (worst) vs `VC-002` (best).
- Degradation = best − worst for E1 and worst − best for E2.
- Unpaired percentile bootstrap with 10,000 draws.
- The family is 2 conditions × 2 endpoints, so Bonferroni gives a two-sided 98.75% CI.
- `falsified_if` (the AEP-direction claim, "better fixed-state fidelity need not improve closed-loop performance", in
  this regime): `materially_degraded` on any primary endpoint.

**Secondary**:
- Each of `VC-002`, `VC-005` and `VC-020` vs `VC-000`, per condition. The family is 12, so the CI is 99.58%.
- `VC-020` vs `VC-002` per condition: calibration size 1024 vs 16, with the same composition and granularity. The CI is
  98.75%.

**Descriptive**:
- Stress vs nominal (G6 main) success rate per cell.
- D4 shadow verdicts, and whether any failure is flagged (EX-3).
- D4 end-of-trial judge: after each non-aborted trial, the last overhead frame goes to Cosmos-Reason2 with the question
  "Is the can standing upright on the coaster now? (YES/NO)". Its answer is compared with the criterion outcome, giving
  agreement and a confusion matrix. **It is never used for the outcome.** It is a first look at AI-judge reliability,
  the step toward RLAIF.

**Power, stated now**: with 12 vs 12 trials and a 98.75% CI, E1 can only reach `materially_degraded` for a large drop
(roughly 50 pp or more). Smaller drops will read as `indeterminate`. Results are reported as effect sizes and CIs, in
the §7.2 wording ("not detected", never "no effect").

## 6. Order lock

1. This file, `scripts/stress_analysis.py`, the schedule, and the runner changes are committed before the first stress
   trial. The judge refactor keeps the locked values as defaults, and G6 output was checked to be identical.
2. The S4 can measurement is committed before the first S4 trial.
3. After the last trial, the sealed logs `stress_S1_sealed.jsonl` and `stress_S4_sealed.jsonl` are hashed into
   `artifacts/freeze/stress_lock_post.json`. Only then are they opened and `stress_analysis.py` run.
4. If the session fails (hardware, a K1-type collapse in every cell), the trials run so far are reported as they are.
   No condition, cell or tolerance is changed after a stress outcome has been seen.

## 7. Amendment 1 (2026-10-11, before any stress trial; no stress outcome seen)

- **Change**: the anti-slip pads on the gripper are removed from this session on. User's reason: the pads kept
  shifting during trials, re-adjusting them was unreliable, and they damaged the can surface.
- **Consequence**: hardware now differs from G6. S1 and S4 would mix the scene change with the gripper change.
- **Added block S0**, run before S1: nominal scene (cola can, training start mark), pads removed, 4 cells × 6 = 24
  trials. It uses the same tokens, runner and blinding, and is interleaved with seed key
  `STRESS/schedule/v1/amend1/S0`. The S1 and S4 blocks are unchanged. Sealed schedule v2 sha256
  `f3fd12e9023daee673a17279f441c0d19e6259482cc06dd04dc9883023b5db70`; v1 `9549b96b…` is kept on Orin as
  `stress_sealed.json.v1`. Runner: `so101_trial.py --blind S0`. Block order: **S0 → S1 → S4**. Total 120 trials.
- **Analysis**:
  - The primary and secondary comparisons (§5) are unchanged. They are within-condition comparisons between cells, and
    every cell uses the same gripper.
  - The stress-vs-nominal description now uses S0 as the same-hardware baseline (per cell, Newcombe 95%). G6 main is
    reported as a second reference, labeled as different hardware.
  - The S0 results are descriptive only. With n = 6 per cell they cannot support a decision.
