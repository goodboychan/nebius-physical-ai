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
