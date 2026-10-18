# Cosmos-Reason2 as a success judge — offline evaluation v1 (LOCKED before any new query)

Status: locked on 2026-10-14 by the commit that adds this file. The user decided to run it. The study is exploratory:
every input is a video already recorded, and no outcome of any study depends on it.

## 1. Question

In the configuration used so far (one final frame, a one-word answer, 8 output tokens), Cosmos-Reason2-2B almost always
answered "Yes". It caught 0 of 7 G6 failures and 2 of 23 later failures. Is that a property of the model, or of the
configuration?

> Which input and answer setup, if any, lets Cosmos-Reason2-2B detect a failed trial from the overhead video?

## 2. Data and ground truth

- **Trials**: every recorded real-arm trial with a saved overhead video: G6 main and retest, stress v1, stress v2 S0,
  S1 and S4, FP16, and the positive control. The videos are the stored files.
- **Label**: does the can stand on the coaster at the end? This comes from the consensus re-judge (stress protocol
  §11), which agrees with the sealed outcomes on G6 (245/245), with the live judge on stress v1 (25/25), and with the
  operator's reports on v2, FP16 and the positive control. Released and contact are not part of this label.
- **Split**, seeded with `COSMOS-JUDGE/split/v1`: one third of the trials, stratified by label, form the **dev** set for
  prompt development; two thirds form the **eval** set, which is touched once. Script:
  `scripts/cosmos_judge_eval.py`.

## 3. Conditions

| Code | Input | Answer |
|---|---|---|
| `C0` | last frame (JPEG q85) | the current prompt, one word, max_tokens 8 (baseline) |
| `C1` | last frame | reason briefly, then end with `Answer: YES` or `Answer: NO`; max_tokens 768 |
| `C2` | last 3 s of video, subsampled to 4 fps, as an MP4 | the same as C1 |

- Temperature 0, the same endpoint (vLLM, L40S), and the model `nvidia/Cosmos-Reason2-2B`.
- **Prompt development is on dev only**: at most **3 prompt variants** each for C1 and C2. The variant with the best
  dev balanced accuracy is kept; ties go to the shorter prompt. The chosen prompts are committed before eval runs.
- An answer that cannot be parsed counts as **abstain**.

## 4. Metrics (eval set), reported for each condition

- Failure recall: NO on label-failure trials.
- False-alarm rate: NO on label-success trials.
- Abstain rate.
- Balanced accuracy (mean of failure recall and success recall, with abstains counted as wrong).
- Median latency per query.
- Wilson 95% intervals on the rates.

There is no pass threshold. The result is read as "which setup, if any, works", with intervals.

## 5. Order lock

1. This file and the script are committed before any C1 or C2 query.
2. The dev runs and the chosen prompts are committed before the eval run.
3. Eval runs once per condition. Its results are reported as they come, including if no condition improves.

## 6. Dev results and chosen prompts (committed before eval, 2026-10-14)

Dev: 136 trials, 10 failures (`artifacts/cosmos_judge/dev/`, `dev_scores.jsonl`).

| Condition | Failure recall | False alarms | Abstain | Balanced accuracy |
|---|---|---|---|---|
| C0 (baseline) | 0/10 | 0/126 | 0 | 0.50 (always YES) |
| C1 p1 | **10/10** | **3/126** | 0 | **0.988** |
| C1 p2 | 10/10 | 126/126 | 0 | 0.50 (always NO) |
| C1 p3 | — | — | 136 (answered "Yes" without the required format) | 0.00 |
| C2 v1 | 5/10 | 47/126 | 83 | 0.25 |
| C2 v2 | 10/10 | 126/126 | 0 | 0.50 (always NO) |
| C2 v3 | 10/10 | 126/126 | 0 | 0.50 (always NO) |

- **Chosen**: C1 → **p1**. C2 → **v3**: v2 and v3 tie at 0.50, and v3 is the shorter prompt (rule §3).
- In every condition the model wrote only the final line, with no reasoning text, despite the 768-token budget.
- Note, stated now: the prompt sensitivity is large. Small wording changes flip the model between always-YES and
  always-NO, and the eval result is read with that in mind.

## 7. Eval results (run once per condition, 2026-10-14)

Eval: 273 trials, 21 failures (`artifacts/cosmos_judge/eval/`, `eval_scores.jsonl`).

| Condition | Failure recall (Wilson 95%) | False alarms (Wilson 95%) | Abstain | Balanced accuracy | Median latency |
|---|---|---|---|---|---|
| C0 baseline | 1/21 [0.008, 0.23] | 0/252 | 0 | 0.52 | — |
| **C1 p1** (final frame, explicit criterion, `Answer:` format) | **20/21** [0.77, 0.99] | **5/252** [0.009, 0.046] | 0 | **0.966** | 893 ms |
| C2 v3 (last 3 s of video) | 21/21 | 252/252 (always NO) | 0 | 0.50 | 1017 ms |

- The C1 dev result held on eval. One failure was missed: stress v1 S0 trial 2, where the can was set down tilted and
  fell. Of the 5 false alarms, 4 are S4 yellow-can trials and 1 is a positive-control trial.
- Video input (C2) collapsed to always-NO with the chosen prompt.
- **Reading**:
  - In this setup Cosmos-Reason2-2B can serve as an end-of-trial success judge, but only with an explicit success
    criterion and a fixed answer format on the final frame.
  - It is very sensitive to wording (§6), so a deployment must re-validate the exact prompt on held-out labelled
    trials.
  - The live 2 Hz supervisor prompt (CONTINUE / FALLBACK / ABORT) was not re-evaluated here.

## Out-of-distribution batch (2026-10-18, amendment 7 blocks; not pre-registered as a judge test)

- **What**: the frozen C1 p1 prompt, unchanged, on the final overhead frame of all 72 generalization trials (TYP: the
  yellow can at +3 cm; T6P/T6M: the cola can at ±6 cm). These scenes were never used to choose the prompt.
- **How**: an offline batch (`cosmos_judge_eval.py run`), after the blocks and **after unsealing**. The prompt and
  model were fixed beforehand and the judge sees only the frame, so unsealing cannot inform it. It is still labelled
  as post-unsealing, not live. Labels: the consensus re-judge. The endpoint was started for this batch and stopped
  right after.
- **Result** (`artifacts/finetune/judge/GEN_C1p1_batch.json`):
  - Failures caught **55/61** (90%, Wilson 95% [80, 95]); false alarms **0/11** [0, 26]; no abstains; median
    latency 716 ms.
  - By block: TYP 20/21 caught, 0/3 false alarms; T6P 24/24; T6M 11/16 caught, 0/8 false alarms.
- **Misses**: 6, all of two kinds.
  - Four T6M grasp failures (trials 1, 6, 8, 10). The can was never grasped and stayed upright at the −6 cm start;
    the judge answered YES. The prompt asks "upright on the coaster", and a standing can off the coaster is its blind
    spot.
  - Two edge placements (TYP 6, T6M 23).
- **Reading**: the prompt transfers to a new can and new positions with no false alarms. It confuses "standing" with
  "standing on the coaster" when an upright can is left away from the coaster. It stays a monitor to validate, not
  an outcome source.
