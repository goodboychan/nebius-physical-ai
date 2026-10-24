# Try QuantGate in 5 minutes

No robot, no GPU, no API key. You need Python 3.10+ and git. Every command below runs from committed evidence and
gives the same result on every machine.

## 0. Just look (no install)

- **Video (3 min):** https://www.youtube.com/watch?v=z80w9vig-qA
- **Dashboard:** https://claude.ai/artifact/2tUAoJHBeT8uLU96BmgPNK. Start at the Review panel: pick a build, read its
  deployment decision and why, then open "Evidence and provenance". Each record links to the file on GitHub.

## 1. Install

```bash
git clone https://github.com/goodboychan/nebius-physical-ai.git && cd nebius-physical-ai
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
# or, with uv: uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
```

It only depends on numpy, scipy and PyYAML (pytest for the tests).

## 2. Check the study yourself

```bash
.venv/bin/python scripts/quantgate.py verify          # expect: 201 passed, then 22 "ok" lines (sealed logs vs their hashes)
.venv/bin/python scripts/quantgate.py review --no-llm # rebuilds the review; open artifacts/reports/review_report.html
.venv/bin/python scripts/quantgate.py plan FP16       # what is confirmed, what is open, and the next test (also FT1, FT2, INT8, PC-B)
```

`git status` stays clean after `review --no-llm`. The rebuilt files are byte-identical to the committed ones.

## 3. Judge your own results

Open [`examples/my_results.csv`](../examples/my_results.csv) and add a row for your own builds: how many times each
build succeeded out of how many trials.

```csv
candidate,reference,cand_successes,cand_trials,ref_successes,ref_trials,gpu_ms,energy_mj,placement_ok,preflight_ok,mode,assumed_rate
my INT8,my FP32,18,20,19,20,,,yes,yes,,
```

```bash
.venv/bin/python scripts/quantgate.py judge examples/my_results.csv --rule revised
```

Expected for the first row (this study's FP16):

```
## FP16 (this study) vs FP32 (this study) (non-inferiority)
- **Deployment decision: HOLD** · evidence finding: INSUFFICIENT_EVIDENCE
- observed: 19/20 vs 10/10 · degradation 5.0 pp, 97.5% interval [-28.7, 27.3]
- next test: ... about 120 trials per arm ...
```

- Use `mode` = `improvement` for a fine-tune compared with the policy it replaces; leave it empty for "is the cheaper
  build as good as the reference".
- `--tol 5` makes the tolerance stricter, and the next test's trials per arm grow with it (about 400 per arm).
- Try a typo, such as `mode` = `improvment` or a column named `mod`. QuantGate refuses it with the row or column
  instead of guessing. Cells with only spaces count as empty, so a CSV saved from a spreadsheet works.

## 4. Preflight a build

```bash
.venv/bin/python scripts/quantgate.py preflight --card examples/candidate/candidate.json   # -> HOLD, exit 3
```

Edit [`examples/candidate/candidate.json`](../examples/candidate/candidate.json) and run it again:

| Change | Expected result |
| --- | --- |
| `"latency_ms": 264` | BLOCK, exit 4: misses the 200 ms chunk deadline |
| `"engine_sha256"` changed | BLOCK, exit 4: not the audited build |
| `"verdict": "GO"` | OK, exit 0 (synthetic card: this only tests the pass branch, it is not an approval) |
| `"latency_ms": -1` | refused, exit 2 |

The example card uses stand-in files, so these edits only exercise each branch of the preflight. In a real deployment
the verdict comes from the judge's output (`judge ... --json out.json`) and the engine hash from the build that was
audited; copy both from those files rather than typing them.

The fields are explained in the README under [Preflight your own build](../README.md#preflight-your-own-build).

## What needs more than a laptop

- `ask` and `review` without `--no-llm` call Nemotron on Nebius Token Factory and need your own `NEBIUS_API_KEY`.
- The real-arm trials need an SO-101 arm and a Jetson Orin Nano. See `quantgate.py stages` for the full pipeline.

## Tell us how it went

Open an issue with the "Try-it feedback" template:
https://github.com/goodboychan/nebius-physical-ai/issues/new?template=try-it-feedback.md

Three questions matter most:
1. Where did you get stuck between cloning and your first result?
2. Did the judge output make sense? Would you use it on your own builds?
3. What would it need before you used it for a real deployment decision?
