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
