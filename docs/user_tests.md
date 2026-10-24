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
