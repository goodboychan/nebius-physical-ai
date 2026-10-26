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
