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
