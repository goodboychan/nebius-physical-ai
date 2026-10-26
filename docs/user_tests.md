# User tests

Sessions where someone outside the build ran QuantGate from [TRY_IT.md](TRY_IT.md). Who they are is left out; what
they did, what they said and what changed is recorded. Findings feed the next commit, linked below.

## Session 1, 2026-10-24 (run together with the author)

**First pass, written from the docs (earlier the same day).** It named CSV columns and counts that are not in the
repository, so it is not counted as a run. Two points were still valid and were fixed in `8587c82`: the README
quickstart only showed `uv` (now `python3 -m venv` + `pip` first), and there was no hint how to open the HTML review.

**Second pass, run together.**
- Install to first result: no blocker. `examples/my_results.csv` worked as the tutorial: its five rows (19/20 vs 10/10
  held, 118/120 vs 117/120 passing, the swapped engine blocked by `preflight_ok=no`, the fine-tune in improvement mode)
  showed which values to change.
- Understanding: rows 1, 3 and 4 side by side made it clear why 19/20 is HOLD, why 118/120 passes, and why a high
  success rate is still blocked when the preflight fails.
- Use: non-inferiority (quantization) and improvement (fine-tune) in one CSV, usable as the record of a release
  decision.
- Asked for: exact cells to break in the guide; a one-byte tamper tip for the preflight; a way from per-episode
  logs to the CSV row; a CI example that comments the decision on a pull request.

**What changed.**
- The guide now names the cells to break.
- It has a tamper tip for each file. Tampering exposed a bug: a one-byte change to `norm_manifest.json` crashed the
  preflight. It now blocks.
- `quantgate.py tally` turns JSONL logs into the judge row. It reproduces this study's 19/20 vs 10/10 from the sealed
  log, and shows that the live judge alone gives 18/20 vs 9/10.
- `judge --gate` exits with the decision. The workflow `quantgate-gate.yml` posts it on a pull request.
- Building the CI example also exposed a bug: `quantgate.py judge` resolved relative paths against the repository
  instead of the caller's folder. It now uses the caller's folder.

## Session 2, 2026-10-26 (fresh environment, first-time developer view)

Run by a reviewer on a GX10 in a new folder and venv, at commit `a69ad28`. No robot, GPU or paid API was used, the
source was not changed, and the reviewer's own robot project was not connected.

**What worked.**
- Install took about 10.5 s and `verify` about 27 s: 209 tests, the runner harness and 22 hashes passed.
- `review --no-llm` took about 1.1 s.
- A self-made CSV (18/20 vs 19/20) gave HOLD and a next test of about 150 per arm.
- Eleven kinds of bad CSV were refused, engine and normalization tampering was blocked, and the linked
  checks → judge → preflight path worked.
- A dashboard difference seen earlier occurred only in a shallow clone; the full history reproduced cleanly.

**Their verdict.** They would use it now to put existing experiment logs through it. Before connecting it to a real
deployment approval, they want a data-connection example and clearer decision wording.

**Asked for, and what changed** (commit after `a69ad28`):
1. **HOLD shown next to "pass".**
   - The preflight now prints the decision and a one-line reason first.
   - Readiness checks show `ok` or `FAIL`. The evidence line shows `GO`, `HOLD` or `BLOCK`, never "pass".
   - The JSON has a `status` per check.
2. **From rollouts to the numbers.** New [`examples/rollout/`](../examples/rollout/) runs a JSONL log through
   tally → card → checks → judge → preflight.
   - It is synthetic and labelled so.
   - It explains each log field, the normalization file and how latency is measured (worst case; the 200 ms
     deadline from the runner's constants).
   - `tally --placement` applies the study's placement rule (E2). It reproduces the FP16 reading, −0.6 px
     [−2.6, +1.4].
   - `tally --engine` writes the build's hash into the row.
   - `quantgate.py card` writes the card and the normalization manifest from the files and logs.
3. **Which rule.**
   - `revised` is now the default, for a new project. `study` (alias `current`) reproduces this study's rule.
   - The output says to fix the rule and tolerance before the trials, and the JSON records both on every row.
4. **Path through the local HTML.** The review page opens with a "Decision path" table: decision → what still blocks
   approval → evidence files → next test, with links to each candidate's plan.
5. **Shallow clone.** TRY_IT.md says to clone the full history and why.

## Session 3, 2026-10-26 (an external public log, AI-run usability test)

An AI reviewer ran this at `0c2cf17` on a fresh environment, with vplan's public D70 evaluation release (hash checked).
It is not an independent user, a robot reproduction or a deployment approval.

**What they did.**
- They dropped the 200 impossible-task rows of 800 and kept both methods on the same 300 tasks, provider failures
  included.
- Their own count, 195/300 vs 107/300, matched the published totals and all 16 scene strata.
- tally and judge ran, and gave HOLD / IMPROVEMENT_DETECTED. The preflight was not filled, because there was no real
  engine, normalization or device latency.

**Where they stopped, and what changed.**
1. **The same task id under both methods was refused as a duplicate.** `tally --pair FIELD` now names the field that
   links a task across builds. Ids are then unique per build, and the row is marked `design=paired`. The duplicate
   error points to `--pair`.
2. **The number 3 did not match the name "3".** Build names are compared as text. A miss lists the names seen with
   their types, and the same name stored as both number and text is refused.
3. **Failures were sometimes null, not false.** A null outcome now stops tally with a message to decide its meaning
   per source: `--missing fail` or `--missing drop`. [`examples/external/convert.py`](../examples/external/convert.py)
   shows source-specific rules written down per status, kept on each converted trial.
4. **Accepted is not the same as statistically valid.**
   - This data was paired, while the intervals here assume independent arms. Their output gave about 21.5–36.7 pp;
     the source's paired bootstrap gave 23–36 pp.
   - judge now takes a `design` column (independent or paired). A paired row is counted and previewed, but never GO
     and without a next-test size, and it says not to use it for a deployment decision.
   - Paired statistics are not implemented.

## Session 4, 2026-10-26 (a public real-robot episode log, AI-run usability test)

An AI reviewer ran this at `8242fe1` with PhAIL's public `episodes.csv` (pinned commit). They kept 113 episodes with
the same object, instruction and starting object count: OpenPI 9/30 as the reference, GR00T 6/27, ACT 6/28 and
SmolVLA 0/28, all HOLD. Partial successes, safety stops and timeouts stayed in the denominator.
- They did not read this as a fair ranking or a deployment check, because each model was recorded under its own
  conditions and at its own time.
- The preflight refused to run without an engine, hash or latency.
- The environment's security review blocked the editable install's build step. That command was not retried, so the
  README install was not verified there. The browser view was not checked.

**Found, and what changed.**
1. **"50% pooled observed" was a mislabel.** The pooled rate was 15.5–26.3%, but the plan used the planner's 50%
   floor and called it observed.
   - The next test now reports both rates: `observed_pooled_rate`, and `planning_rate` with its basis. For example:
     "50%, the planner's floor: the pooled observed rate is 26.3%".
2. **Data whose independence or homogeneity is not verified.**
   - judge takes a separate `collection` column: controlled (default) or observational. `design` is how trials are
     analysed; `collection` is how they were gathered.
   - Observational rows are previews: never GO, no next-test size.
   - Adding this exposed a real bug: a preview row's finding could still say GO, and `preflight --judge` reads the
     finding. A preview row's finding is now never GO or IMPROVEMENT_DETECTED (the preview reading is kept in
     `preview_finding`), and the preflight treats a preview row as not evidence. The bug applied to paired rows since
     the previous commit.
3. **`eval.outcome` (a CSV column) vs `eval` → `outcome` (nested JSON).**
   - tally reads CSV directly and matches a field name exactly before reading it as a nested path.
   - A missing field lists the fields that exist and the closest match.
   - Text outcomes need an explicit `--map Success=true ...`; an unmapped value stops tally.
4. **Disagreeing sources.**
   - `--where FIELD=VALUE` filters to one condition.
   - `--audit` writes one line per input row: source, line, id, build, counted or excluded, and why.
   - [`examples/external/`](../examples/external/) shows it on a synthetic per-episode CSV.
