# From your rollouts to a deployment decision

The path from trial logs to a decision, run end to end on one example. The log (`trials.jsonl`, written by
`make_trials.py`) is **synthetic**: two builds of one policy, 40 trials each, and one aborted trial. The engine and
normalization files in `build/` are stand-ins. Replace all three with yours.

Run everything from this folder (with the venv from [docs/TRY_IT.md](../../docs/TRY_IT.md); `P` is its Python):

```bash
P=../../.venv/bin/python; Q=../../scripts/quantgate.py
```

## 1. Log one JSON object per trial

```json
{"trial_id": "T001", "session": "day1", "build": "int8", "aborted": false, "success": true, "released": true, "place_px": 11.0, "rtt_ms": 73.7}
```

| Field | What it is | Notes |
| --- | --- | --- |
| `trial_id` (+ `session`) | unique per trial | a trial seen twice, in one file or across files, stops tally |
| `build` | which build ran | any name; the same name goes in the card and the CSV |
| `success` | your outcome for the trial, true or false | decide the rule before the trials (e.g. a re-judge of the saved video, as in this study) |
| `released`, other flags | extra conditions | `--and released`, `--not human_contact` |
| `aborted`, `invalid` | trials that do not count | left out by default |
| `place_px` | placement error of a successful trial | any unit; leave it empty on failures |
| `rtt_ms` | worst round trip in the trial: observation sent to action chunk back, ms | the runner of this study logs it as `rtt_ms_max` |

## 2. Count: tally

```bash
$P $Q tally trials.jsonl --group build --candidate int8 --reference fp32 --and released \
    --placement place_px --engine build/int8.engine > results.csv
```

```
placement: degradation -0.1 px, 97.5% interval [-1.5, +1.4] vs tolerance 5 px -> placement_ok=yes
```

`results.csv` gets `int8,fp32,38,40,39,40,yes,<engine sha256>`.

- **Placement** uses this study's rule (E2). It compares the mean placement error of the candidate minus the
  reference, on successful trials, with a 97.5% bootstrap interval. `placement_ok` is `yes` if the upper bound is
  below `--placement-tol` (default 5), `no` if the lower bound is above it, and empty (undecided) otherwise.
- **`--engine`** writes the build's hash into the row, so the preflight can check that the row and the card describe
  the same build.

## 3. Describe the build: card

```bash
$P $Q card --engine build/int8.engine --norm build/int8.norm_stats.npz --candidate int8 \
    --latency-from trials.jsonl --latency-field rtt_ms --group build --out card.json
```

It writes `card.json` (engine path, hash, latency) and `build/norm_manifest.json`, so nothing is typed by hand.

- **Normalization file**: the statistics the policy was trained with, e.g. LeRobot's per-feature mean and std saved
  as `.npz`. The preflight does not read its contents. It checks that the file next to the engine is the one the
  manifest names, with the same hash. That catches the swapped-file mistake, where another policy's statistics load
  without an error.
- **Latency**: the card takes the maximum `rtt_ms` over the candidate's counted trials (aborted ones excluded), so it
  measures the worst case on the target device, not the average.
  - It must be at most the chunk deadline: 200 ms for this runner.
  - The deadline comes from the runner's constants. A new chunk is requested 10 steps before the current one ends and
    must arrive 4 steps before, at 30 Hz: (10 − 4) / 30 s.
  - Your runner's deadline may differ.

## 4. Decide: checks, judge, preflight

```bash
$P $Q preflight --card card.json --checks-only --json pre.json   # engine, normalization, timing
$P $Q judge results.csv --preflight pre.json --json judge.json   # the evidence; preflight_ok from pre.json
$P $Q preflight --card card.json --judge judge.json              # all four, verdict from judge.json
```

```
## int8 vs fp32 (non-inferiority)
- **Deployment decision: HOLD** · evidence finding: INSUFFICIENT_EVIDENCE
- observed: 38/40 vs 39/40 · degradation 2.5 pp, 97.5% interval [-10.8, 16.5]
- next test: ... about 100 trials per arm ...

preflight (evidence: judge.json (HOLD)): HOLD (exit 3) | the engine, normalization and timing are ready, but the evidence does not approve deployment yet
  ok     engine integrity  hash matches the recorded build
  ok     normalization     manifest and hash match
  ok     timing contract   max rtt_ms over 40 trials of int8 97.4 ms vs chunk deadline 200 ms
  HOLD   evidence          INSUFFICIENT_EVIDENCE is not approval: next test: about 100 trials per arm
```

How to read it:
- `ok` means a file or timing check held. It never means approval.
- The decision is on the first line. Here the build is ready, but 40 trials per arm cannot show that int8 is within
  10 pp of fp32, so it is HOLD. The next test is sized at about 100 trials per arm.

## Which rule

- `--rule revised` (the default) is the rule for a new project.
- `--rule study` reproduces this study's pre-registered rule, which has a ceiling clause: two arms both at or above
  95% stay undecided.
- Choose the rule and the tolerance (`--tol`, default 10 pp) before the trials and write them down, for example in
  the plan you share. Picking whichever rule reads better after seeing the results turns the test into a search for
  a GO. The JSON output records the rule and tolerance with every row.
