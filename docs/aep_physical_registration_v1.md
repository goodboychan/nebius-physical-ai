# AEP-facing registration: physical SO-101 closed-loop audit (v1)

Status: **registered before unsealing** (2026-10-08). Mirrored in the AEP repository at
`docs/mlsys27/physical_so101_closed_loop_v1/PROTOCOL.md` with a seal of this file's SHA-256.

This registration adds analyses to the QuantGate G6 experiment so that its real-arm results can be used as
evidence about the AEP claim *"better fixed-state fidelity need not improve closed-loop performance in quantized
neural policies."* It does **not** change QuantGate's primary endpoint, hypotheses, arms, schedule, or success
criterion. Those stay as locked in `docs/preregistration.md`, `artifacts/freeze/lock2.json`
(record `5fb513a4…`) and the sealed schedule (`3a1c6fed…`).

## What has been seen before this lock

- G2 FP32 baseline: 20/20 success (not part of G6).
- G6 main session trials 1–30: **aggregate only**, 30/30 success, all `judge_auto.reason = ok`. The operator also
  remarked that some placements were "barely on the coaster". **No per-cell outcome has been opened.** The sealed
  file `~/.edgeqgate_sealed/g6_sealed.json` has not been read for outcome purposes.
- Offline fixed-state scores for all cells (they are the frozen LOCK-2 inputs).

Therefore `analysis_role = registered_audit`, `locked_before_outcome = true` for per-cell outcomes, with the
aggregate disclosure above.

## Mapping to AEP terms

| AEP term | Here |
|---|---|
| artifact | one Orin TensorRT engine (INT8 cell `VC-0xx`, or the FP32 reference engine for `VC-000`) built from the single G2 checkpoint |
| fixed-state fidelity | `score_mag`: CVaR@90 over 2,000 held-out audit states of the RMS (over 100 chunk steps) action error vs the FP32 torch reference, normalized units (decision_log 2026-10-07) |
| closed-loop task outcome | (E1) binary success per `docs/success_criterion.md`; (E2) placement error `place_err_px` (EX-4), 1 px ≈ 1.4 mm |
| reference condition | `ARM-FP32` (`VC-000`), interleaved in the same session (IG-8) |
| policy class / backend | LeRobot ACT (vision, 51.6M, transformer) on Jetson Orin TensorRT 10.3 — **not** the state-MLP policies or the Hailo / EdgeTPU / QNN backends of the AEP paper |

## Data

- Session `g6_main` only. `ARM-RETEST` (separate session) is excluded here and reported separately.
- Invalid trials (operator-marked setup errors) are excluded. Operator aborts (`unsafe`) count as failures for E1
  and are excluded from E2.
- E2 uses trials where the can top was detected in all 15 final frames. Non-detected trials are counted and reported.
- Unit of analysis: trial. Trials are **not paired** (each trial runs one artifact), so intervals are unpaired.

## Questions, decision rules, and falsification

Degradation is defined so that larger = worse: E1 `rate(reference) − rate(candidate)`; E2
`mean(candidate) − mean(reference)`.
Tolerances (practical equivalence, fixed now): **E1: 10 percentage points. E2: 5 px (about 7 mm).**
Intervals: unpaired percentile bootstrap over trials, 10,000 draws, PCG64 seed derived from
`PREREG-SEED-2026-09-14/AEP-physical-v1`. Decision per AEP harness semantics: upper bound < tolerance →
`tolerance_compatible`; lower bound > tolerance → `materially_degraded`; otherwise `indeterminate`.

### Q1 — Does better fixed-state fidelity buy better closed-loop outcome? (the AEP claim)

Compare the best-fidelity group with the worst-fidelity group among cells with real-arm data.
- Best-fidelity group = `ARM-AUDIT` cells (VC-002, VC-020, VC-010). They are also the top 3 by `score_mag`.
- Worst-fidelity group = `ARM-LOW` cells (VC-005, VC-007), the bottom 2 by `score_align` and by `score_mag`.
- Reference role: best group. Candidate role: worst group. 95% two-sided, single family of 2 (E1, E2) →
  Bonferroni marginal 97.5%.
- **Consistent with the AEP claim** if both evaluable endpoints are `tolerance_compatible`: the worse-fidelity
  artifacts are not materially worse closed-loop.
- **`falsified_if`**: either endpoint is `materially_degraded`. That would mean that, on this physical task, better
  fixed-state fidelity *did* buy better closed-loop outcome. It is reported as a counterexample to the claim's
  generality, not explained away.
- `indeterminate` on an endpoint is reported as such. No extra trials are added to resolve it.

### Q2 — Per-artifact qualification against the FP32 reference

For each INT8 cell with real-arm data (AUDIT 3, RANDOM 3, LOW 2, CHEAP 2 = 10 cells), compare it with `ARM-FP32`
on E1 and E2. Family = 10 cells × 2 endpoints = 20, family confidence 95%, Bonferroni marginal 99.75%.
Report the decision per cell and endpoint.

### Q3 — Rank association (descriptive, as already registered in EX-4)

Spearman correlation between the frozen `score_mag` ranking and the per-cell mean E2 over the 10 INT8 cells, with a
label-permutation p-value (10,000 permutations). Descriptive only; no decision.

## Ceiling rule (fixed now)

If both groups in a comparison have E1 success ≥ 95%, E1 for that comparison is reported as
**`indeterminate (ceiling)`** regardless of the interval, and the conclusion rests on E2. A ceiling on E1 is not
evidence that fidelity is irrelevant. It may only mean that the task is too easy to show a difference, and the
write-up must say so.

## Scope limits to state in any paper use

- One task, one scene, one start position, one FP32 checkpoint, one backend (TensorRT on Orin), vision ACT policy.
- Trials are interleaved and operator-blinded (IG-4, IG-5), but the operator is the developer.
- Placement error is measured by one overhead camera with a perspective correction. Circle-detection jitter on a
  stationary can is 3–6 px, the same order as the E2 tolerance.
- This is an **extension** to a different policy class and to a physical plant. It is not a replication of the
  AEP simulation results.

## Timing

The analyses run only after QuantGate `LOCK-3` (all `g6_main` trials done). The planned stress test with harder
conditions will be registered separately before it runs. It is the intended response to the ceiling risk.
