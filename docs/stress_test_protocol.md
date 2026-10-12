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

## 8. Stress test v2 — rubber-band gripper (2026-10-11, before any v2 trial)

**Why v2.** v1 was stopped by the S0 rule. S0 (pads removed) gave 8/24 successes, below 12, so S1 and S4 were not run
(S1 had 1 trial, run before S0). The operator saw that most failures were the can slipping out of the gripper.
- The v1 sealed logs are hashed in `artifacts/freeze/stress_v1_post.json`: S0 `5691a2da…`, S1 `bfb422d6…`.
- They **stay sealed until v2 is complete**, so that per-cell v1 results cannot shape v2. Only the public totals were
  seen.
- v2 is a new test designed after seeing those totals. That is stated here, not hidden.

**Change.** The user puts rubber bands on the gripper fingers to raise friction. The pads stay off. Nothing else
changes: cells, engines, runtime, success criterion, S1 mark, S4 can, and the Cosmos question.

**Design.**
- Blocks are fixed in the order **S0 → S1 → S4**, at 4 cells × 6, 12 and 12 trials = 120 trials.
- New anonymous tokens and seed key `STRESS/schedule/v2` (`scripts/stress_schedule_v2.py`).
- Sealed schedule `~/.edgeqgate_sealed/stress_v2/stress_sealed.json` sha256
  `ddfa696e61f15953ad2b07e16df33f6ab1fc24ad6f1b4d783d94879e3d9328f4`; public copy
  `artifacts/stress_v2/stress_schedule_public.json`.
- Runner: `so101_trial.py --blind S0|S1|S4 v2`.

**Rules.**
- **S0 stop rule** (same as v1): if S0 has fewer than 12/24 successes in total, S1 and S4 are not run.
- **Session checks**: the light and coaster checks are as before. The rubber bands can change how the gripper looks in
  the wrist camera. If the wrist check then fails, the wrist reference may be re-saved **once**, after the bands are on
  and before the first v2 trial. That reference is used for the whole of v2.
- S4 can measurement: `so101_can_calib.py`, as in §4. This is done before the first S4 trial.

**Analysis.**
- `stress_analysis.py --version v2` runs the same primary and secondary comparisons and the same descriptive analysis as
  §5 and §7. The v2 S0 is the same-hardware baseline.
- After the last v2 trial, the v2 sealed logs are hashed into `artifacts/freeze/stress_v2_post.json`. Only then are
  both v1 and v2 opened.
- v1 is reported as a separate descriptive result: no pads, S0 only, plus 1 S1 trial.

## 9. Amendment v2-1 (2026-10-12, during v2 S0 after trial 6, blind to cells)

- **Finding**: the operator reported that every v2 trial judged a failure so far (S0 3, 5, 6) had the can standing on
  the coaster. The last overhead frames confirm it. The live judge's stillness test failed these trials because the
  circle detector jumped to a wrong circle in 1–2 of the last 15 frames. With the rubber bands, the can sits about
  20 px off center (inside the 35 px target; about 6 px in G6). A bright circle on the coaster rim or logo then
  competes with the can top. The jump is sensitive to tiny frame differences: it can be reproduced from the video with
  the runner's RGB → gray path but not with direct luma decoding.
- **Rule for v2**: every v2 trial is judged offline from its saved overhead video by `scripts/stress_rejudge.py`.
  - The locked geometry is unchanged.
  - Stillness allows ≤ 3 of 15 frames more than 8 px from the median.
  - Success = this geometric judge ∧ released ∧ no human contact ∧ not aborted.
  - The live judge is kept in the log and reported as a sensitivity analysis.
  - The S0 stop rule uses the re-judged outcome.
  - `stress_analysis.py --version v2 --rejudge …` applies the rule.
- **Checked before adoption** (offline, every G6 video): the rule changes no G6 outcome. The strict rule re-run offline
  fails G6 main 52, a live success; the new rule passes it. The rule was chosen from the operator's report and the
  frames, without any cell information. It is applied identically to every v2 trial. The live screen will keep showing
  the strict live verdict.

## 10. Amendment v2-2 (2026-10-12, before any stress v2 outcome was unsealed; S4 paused at trial 11)

- **Problem (external review, confirmed)**: the E1 (success) interval came from an unpaired percentile bootstrap. When
  a group has 0 failures (for example 12/12), every resample is 100%, so the interval collapses and
  "tolerance_compatible" is reached far too easily. G6 Q2 shows the effect: VC-007 15/15 against FP32 24/25 gave a
  bootstrap interval of about [−20, 0] pp. The Newcombe interval at the same 99.75% level is [−32.3, +34.0] pp.
- **Change** (`scripts/stress_analysis.py` `7d99864d…`, shared by `fp16_analysis.py`):
  - The E1 decision uses the **Newcombe hybrid-score interval at the same confidence level**. The bootstrap E1
    interval stays as a secondary field.
  - E2 needs at least 5 placements per arm; otherwise it is indeterminate.
  - Each comparison gets a verdict: **GO** (both endpoints tolerance_compatible), **NO-GO** (any materially_degraded)
    or **INSUFFICIENT_EVIDENCE**.
- **Consequence, stated now**: the change makes the decisions more conservative. With 12 against 12 trials,
  `materially_degraded` on E1 now needs a drop of at least 58 pp from a 12/12 reference (5/12 or fewer) or 67 pp from 11/12. Smaller drops read as indeterminate.
  The S0 stop rule and the outcome rules are unchanged.
- The stress v2 and FP16 sealed logs have not been opened. The public S4 tally seen so far is 11 trials with no
  operator-reported failure.

## 11. Amendment v2-3 (2026-10-13, after the last v2 trial and the post-lock hash, before any v2 cell result was opened)

- **Finding**: the §9 rule (the nearest circle per frame, at most 3/15 outliers) gives S4 v2 24/48. The operator saw
  all 48 trials succeed. Every one of the 24 failures is "moving", with 4–7 outlier frames on the same spurious circle
  near (399, 365). With the shorter yellow can, the expected top position sits close to it. This is a measurement
  failure, not a policy outcome. Only public, cell-blind information was used (the videos and the operator's report).
- **Rule** (`scripts/stress_rejudge_consensus.py` `382acdf3…`): the same detector, brightness threshold, radius range and
  offsets.
  - The can top is the **consensus** circle: the candidate present, within 8 px, in the most of the last 15 frames.
  - Standing and still means at least 12/15 frames contain it.
  - Inside means the consensus median plus the offset lies within 35 px of the coaster center.
  - No candidate means a failure.
- **Validated before adoption**, on every video available, all cell-blind:
  - G6: 245/245 agree with the sealed outcomes.
  - Stress v1: 25/25 agree with the live judge.
  - Stress v2 S0: 23/24, the one failure is trial 9, a real drop.
  - S1: 0/3, all three real failures.
  - S4: 48/48, matching the operator.
  - Results: `artifacts/reports/judge_validation/`, `artifacts/stress_v2/rejudge/*_consensus.json`.
- **Primary for v2 and FP16**: this consensus rule ∧ released ∧ no contact ∧ not aborted. The §9 rule and the live
  judge are reported as sensitivity analyses.
