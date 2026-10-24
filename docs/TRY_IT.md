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
.venv/bin/python scripts/quantgate.py review --no-llm # rebuilds the review as one HTML file (below)
.venv/bin/python scripts/quantgate.py plan FP16       # what is confirmed, what is open, and the next test (also FT1, FT2, INT8, PC-B)
```

Open the review in a browser:

```bash
xdg-open artifacts/reports/review_report.html     # Linux;  macOS: open ...;  Windows: start ...
```

`git status` stays clean after `review --no-llm`. The rebuilt files are byte-identical to the committed ones.

## 3. Judge your own results

Open [`examples/my_results.csv`](../examples/my_results.csv) and add a row for your own builds: how many times each
build succeeded out of how many trials. Only six columns are required; the rest can stay empty.

| Column | Meaning | Example |
| --- | --- | --- |
| `candidate`, `reference` | the build you want to ship and the one it must not be worse than | `my INT8`, `my FP32` |
| `cand_successes`, `cand_trials` | successes and trials of the candidate | `18`, `20` |
| `ref_successes`, `ref_trials` | successes and trials of the reference | `19`, `20` |
| `placement_ok`, `preflight_ok` | did the build pass your placement check and the preflight (`yes`, `no`, empty) | `yes` |

Any pass/fail outcome works (grasp, reach the goal, no collision), as long as each trial counts as one success or
one failure. For a first try, copy this line to the end of the file, then change `18` and `20` to your own numbers:

```csv
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
- See it refuse bad input. In the last row (`Fine-tune`), change `improvement` in the `mode` column to `typo`, or in
  the first row change `11.6` in the `gpu_ms` column to `-5`, then run judge again: it stops with the row number and
  exit 2 instead of guessing. Renaming the `mode` header to `mod` is refused too. Cells with only spaces count as
  empty, so a CSV saved from a spreadsheet works.

### From trial logs to the CSV row

If your runs are logged one JSON object per trial (JSONL), `tally` counts them per build and prints the row. Say
what counts as a success, because the count depends on it. This study's FP16 log gives 18/20 vs 9/10 with the live
automatic judge, and 19/20 vs 10/10 (the published result) with the pre-registered outcome:

```bash
.venv/bin/python scripts/quantgate.py tally artifacts/trials/fp16_unsealed/stress_fp16_F0_sealed.jsonl \
    --candidate VC-025 --reference VC-000 \
    --success artifacts/fp16/rejudge/F0_consensus.json:success_geom --and released --not human_contact
```

For your own log: `--group` is the field naming the build (default `cell`), `--success` the outcome field (default
`success`; dotted paths work), `--append my_results.csv` adds the row, and `--set placement_ok=yes` fills other columns.
Trials marked `invalid` or `aborted` are left out by default (`--drop`).

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

Or change one byte of a file next to the card: `printf x >> examples/candidate/policy.engine` blocks at the engine
check, and the same on `policy.norm_stats.npz` blocks at the normalization check. This is the swapped-file mistake the
preflight exists to catch. Run `git checkout examples/candidate` afterwards.

The example card uses stand-in files, so these edits only exercise each branch of the preflight. In a real deployment
the verdict comes from the judge's output (`judge ... --json out.json`) and the engine hash from the build that was
audited; copy both from those files rather than typing them.

The fields are explained in the README under [Preflight your own build](../README.md#preflight-your-own-build).

## 5. Link the judge and the preflight

On their own, judge asks whether the preflight passed (`preflight_ok`) and the preflight asks for the judge's verdict.
Linked, each takes the other's answer from a file instead of a hand copy. They are tied together by the card's
`candidate` (its CSV row) and `engine_sha256` (the CSV row's build):

```bash
cd examples/gate
Q=../../scripts/quantgate.py
python $Q preflight --card candidate.json --checks-only --json pre.json               # engine, normalization, timing -> OK
python $Q judge results.csv --rule revised --preflight pre.json --json judge.json     # preflight_ok filled from pre.json -> GO
python $Q preflight --card candidate.json --judge judge.json                          # all four checks, verdict from judge.json -> OK
```

(Use `../../.venv/bin/python` if the venv is not active.) Then try `printf x >> ../candidate/policy.engine`: the
checks block, judge turns the row into BLOCK, and so does the preflight. Run `git checkout ../candidate` afterwards.
A CSV row whose `engine_sha256` is another build, or a hand-typed `preflight_ok` that disagrees with the checks, is
refused with exit 2.

### In CI (a configurable example)

[`.github/workflows/quantgate-gate.yml`](../.github/workflows/quantgate-gate.yml) runs these three steps when the
results or the card change. It writes the outcome to the job summary and, on a pull request, as a comment. In this
repository it gates the `examples/gate/` files with `FAIL_ON: block`. To use it in yours:

1. Set `RESULTS` and `CARD` to your files.
2. Put the same paths under `on.pull_request.paths` and `on.push.paths`.
3. Pin `QUANTGATE_REF` to a commit.
4. Choose `FAIL_ON`: `block` fails on BLOCK, `hold` fails on HOLD or BLOCK, `none` reports only.

The first step refuses a misconfiguration with exit 2 instead of letting the gate open silently: a `FAIL_ON` that is
not one of the three, or `RESULTS`/`CARD` not covered by the path filters. The PR comment step has not yet run on a
real pull request in this repository.

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
