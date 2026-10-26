# An external evaluation log, converted

External evaluations rarely log trials the way the QuantGate runner does. This example shows the three places where a
first conversion usually stops, and what to do at each. The data is **synthetic** (`make_raw.py`), in the shape such
logs often have:
- 40 tasks, each run once by config `1` (baseline) and config `3` (the method);
- configs stored as numbers;
- `judge.success` set to `null` when a run never reached the judge.

```bash
P=../../.venv/bin/python; Q=../../scripts/quantgate.py
$P make_raw.py && $P convert.py
$P $Q tally trials.jsonl --group config --candidate 3 --reference 1 --pair task_id --set mode=improvement > results.csv
$P $Q judge results.csv
```

## 1. Null is not an outcome: write the rule per source

Reading `raw.jsonl` directly stops at the first run that never reached the judge:

```
error: trial a002-c1: judge.success is null or missing. Decide what that means in this source (a failure, or not run) and say so: --missing fail or --missing drop
```

- A null can mean a failure, a run that never happened, or a lost record. Which one depends on the source.
- [`convert.py`](convert.py) writes the rule down per status:
  - a plan the method refused before execution counts as a **failure**, because the task was not done;
  - a provider error counts as a **failure** too, because the source's published totals keep it in the denominator.
- Each converted trial keeps its rule (`"rule": "provider_error -> fail"`).
- An unknown status stops the conversion.
- `tally --missing fail|drop` applies one rule to every null. Use it only when one rule really fits the whole source.

## 2. The same task under two builds: a pair, not a duplicate

Using `task_id` as the trial id is refused:

```
error: duplicate trial 'task001': ... each trial may be counted once. If this id is a task that every build ran (a paired design), use --pair FIELD
```

- Keep two ids. Each attempt needs its own id (`trial_id`, unique per build and run). The task id (`task_id`) links
  the two builds.
- `--pair task_id` checks the pairing and reports it: `paired on 'task_id': 40 pairs with both builds, 0 unpaired`.
- It also marks the CSV row `design=paired`.

## 3. Numbers and text: `3` is `"3"`

- Build names are compared as text, so config `3` in the log matches `--candidate 3`.
- If a name does not match, the error lists the names it saw with their types: `builds seen: '1' (int), '3' (int)`.
- A log that stores the same name as both a number and a string is refused, because that usually means two sources
  were merged inconsistently.

## What the result means: a paired design is a preview here

```
## 3 vs 1 (improvement, paired design: PREVIEW ONLY)
- **Deployment decision: HOLD** · evidence finding: IMPROVEMENT_DETECTED (unpaired reading, not for deployment)
- observed: 19/40 vs 8/40 · difference 27.5 pp, 95% interval [6.8, 45.3]
```

- QuantGate's intervals treat the two builds as independent samples. That fits this study, where each trial runs one
  build.
- When both builds run the same tasks, the right interval comes from the pairs (a paired bootstrap, or McNemar's test
  for discordant pairs). The independent interval can land close to it, but that does not make it valid.
- So a `design=paired` row is counted and shown, but it is never GO, it has no next-test size, and it says not to use
  it for a deployment decision.
- Paired analysis is not implemented. Until it is, analyse the pairs with your own pre-registered method.

# A per-episode CSV with text outcomes, recorded per model

`episodes.csv` (**synthetic**, `make_episodes.py`) has the shape some real-robot evaluations publish:
- one row per episode;
- outcomes as text in a column named `eval.outcome`;
- several objects and instructions;
- each model recorded on its own days.

```bash
$P make_episodes.py
$P $Q tally episodes.csv --id episode_id --group model --candidate gr00t --reference openpi --success eval.outcome \
    --map Success=true --map Stalled=false --map Safety=false --map Timeout=false --map Partial=false \
    --where object=spoons --where "instruction=put the spoons in the box" --where start_objects=3 \
    --set collection=observational --audit audit.jsonl > results.csv
$P $Q judge results.csv
```

## Field names: a column called `eval.outcome` is not `eval` → `outcome`

- tally reads CSV directly: empty cells are null, and `true`/`false` in any case are booleans.
- A field name is matched exactly first, so the column `eval.outcome` works. Only after that is it read as a nested
  path, so `eval` → `outcome` in JSON works too.
- A wrong name is reported as a missing field, with the fields that exist and the closest match:
  `has no field 'eval_outcome' ...; did you mean eval.outcome?`

## Text outcomes: say which text is a success

- Without `--map`, the first text outcome stops tally: `eval.outcome is the text 'Success'. Say which texts are a success`.
- Map every value the source uses. An unmapped value stops tally instead of being guessed.
- Whether `Partial` or `Safety` is a failure is the source's definition, and your plan's. Here none of them is
  dropped from the denominator.
- `--map NAME=missing` marks a value as not run, and then `--missing` decides what that means.

## One condition, and why each row was left out

- `--where` keeps only the episodes of one condition: object, instruction and starting objects.
- `--audit audit.jsonl` writes one line per input row with the source file, line, id, build, `counted` or
  `excluded`, and the reason, e.g. `condition not met: object is 'towels', wanted 'spoons'`.
- tally prints the totals: `audit: 60 counted, 100 excluded (condition not met: 20; build 'act' is neither ...)`.
- Keep the audit with the result. If two sources disagree about an episode (the object in the CSV against the
  recording's metadata), the audit shows whether that episode was counted, and why.

## Collected per model, on different days: observational

The models were not run under one interleaved schedule, so a difference can come from the day, the setup or the
operator as much as from the model. `collection=observational` keeps the counts and the reading, as a preview:

```
## gr00t vs openpi (non-inferiority, observational data: PREVIEW ONLY)
- **Deployment decision: HOLD** · evidence finding: INSUFFICIENT_EVIDENCE (preview only, not for deployment)
- observed: 6/30 vs 9/30 · degradation 10.0 pp, 97.5% interval [-14.9, 33.4]
```

- `design` and `collection` are separate:
  - `design` is how the trials are analysed: independent or paired.
  - `collection` is how they were gathered: `controlled`, meaning both builds under the same conditions on a pre-set
    interleaved or randomized schedule, or `observational`, meaning anything else or not verified.
- A row is a full reading only when it is independent and controlled. Anything else is a preview: never GO, no
  next-test size, and the preflight treats it as not evidence.

# Before and after on fixed seeds: what the average hides

`seeds.csv` (**synthetic**, `make_seeds.py`) has 60 seeds, each run by version `before` and `after`. `near_miss` is
recorded only when an episode ends in success or timeout; otherwise it is empty.

```bash
$P make_seeds.py
$P $Q tally seeds.csv --id run_id --group version --candidate after --reference before --success outcome \
    --map success=true --map collision=false --map dropped=false --map timeout=false \
    --pair seed --safety near_miss --detail outcome --regressions regressions.jsonl --set mode=improvement > results.csv
$P $Q judge results.csv
```

```
pairs: 26 improved, 5 regressed, 22 both succeed, 7 both fail; of the regressions, 0 with a safety event, 2 with no safety record
  regressed: pair '20': candidate trial 'after-020' failed, reference trial 'before-020' succeeded; safety event: not recorded; outcome: 'dropped'
  ...
- pairs: 26 improved, 5 regressed (0 with a safety event, 2 with no safety record) · regressed trial ids: tally --regressions · shown, not used in the decision
- safety events: 7 in 51 recorded trials of after, 0 in 38 of before (trials without a record are not counted as none) · shown, not used in the decision
```

- **Per pair, not only the average.** Success went from 27/60 to 48/60, but five seeds that succeeded before fail
  after.
  - `--pair` counts the four transitions.
  - `--detail outcome` shows how each regression failed.
  - `--regressions` writes each regressed pair with both trial ids, so you can open the two episodes.
- **Not recorded is not "none".**
  - `--safety near_miss` counts a trial only when the field is true or false. An empty field is reported as "no
    safety record".
  - Without `--safety`, judge says `safety events: not provided` rather than staying silent.
- **Shown, not decided.** These counts sit next to the decision and do not change it. A rule that blocks on
  regressions or safety events has to be pre-registered like any other. This log is also a tuning set, so it says
  nothing about generalization.
