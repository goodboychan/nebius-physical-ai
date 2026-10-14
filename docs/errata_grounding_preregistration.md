# Errata grounding with Nemotron v1 (LOCKED before any Nemotron call)

Status: locked on 2026-10-14 by the commit that adds this file, `configs/errata_grounding_v1.json` and
`scripts/d5_errata_grounding.py`. Exploratory and offline. No verdict depends on it.

## 1. Question

`D5` collects field reports with Tavily (snapshot `artifacts/retrieval/errata_g4.json`, hash ed199938…, 25 results
from 5 queries). Until now a person had to read them. The question:

> Can Nemotron 3 Super read each result and say whether it matches, contrasts with, or does not concern what we
> measured on our own build, with every claim checked by code against the snapshot and our facts?

## 2. Inputs (fixed in the config)

- **Build profile**: TensorRT 10.3 on the Orin Nano Super, ACT (ResNet-18 backbones plus a transformer), modelopt
  explicit Q/DQ, `--int8 --fp16`. Unused features are listed.
- **Facts F1–F5**, each with its numbers and source file:
  - F1: INT8 is slower than FP16 (16.8 vs 11.6 ms).
  - F2: INT8 uses more energy per inference (101 vs 82 mJ).
  - F3: `--int8` alone builds slower (28.57 vs 16.22 ms).
  - F4: the modelopt fused-MHA quantizer stays uncalibrated.
  - F5: engine builds are nondeterministic without a frozen timing cache.
- **Labels**: MATCHES (fact id), CONTRASTS (fact id), APPLIES_UNVERIFIED, NOT_APPLICABLE.
- **Reference labels** for all 25 results, written by the assistant from the snapshot text before any model call:
  - MATCHES F1: R09, R11, R13, R18.
  - CONTRASTS F1: R14, R15 (YOLO on Orin Nano, where INT8 is faster than FP16).

## 3. Procedure

- One call per result to `nvidia/nemotron-3-super-120b-a12b` on Nebius Token Factory, at temperature 0.
- Each call receives the build profile, the facts, the label definitions, and that result's title, URL and content.
- The model must answer in JSON: `label`, `fact_id`, `quote` (verbatim from the content), `explanation`.
- **Validator** (code; a claim that fails is shown as rejected, never silently fixed):
  1. The JSON parses, and the label is one of the four.
  2. `fact_id` is present exactly when the label is MATCHES or CONTRASTS, and it names a real fact.
  3. `quote` is at least 20 characters and appears in the result's content (case and whitespace normalised).
  4. Every number in `explanation` appears in the quote, in the result content, or in the cited fact's numbers.
- **Output**: `artifacts/reports/errata_grounded.{json,md}`.
  - The table of matches shows our numbers from the facts file, inserted by code. It does not use the model's
    wording for numbers.

## 4. Metrics (reported as they come; no pass threshold)

- **Primary**:
  - Recall of the six reference MATCHES/CONTRASTS results, counting the label, the fact id and validator-passed
    claims.
  - The number of results the model labels MATCHES or CONTRASTS that the reference does not.
- **Secondary**: the full 4 × 4 agreement table, validator rejections by rule, latency, and tokens per call.

## 5. Reading

- The point is whether Nemotron can turn a list of links into checked statements of the form "this field report
  matches what we measured", which a developer can trust because code has checked every quote and number.
- Disagreements in the APPLIES_UNVERIFIED / NOT_APPLICABLE region are expected and are reported, not tuned away.
  The prompt and inputs are fixed by this commit.
