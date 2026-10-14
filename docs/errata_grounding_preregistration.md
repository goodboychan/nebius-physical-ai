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

## 6. Run v1 (2026-10-14), as pre-registered

Output: `artifacts/reports/errata_grounded_v1.{json,md}`.

- **Primary recall: 1/6.** Only R15 (CONTRASTS F1) was accepted with the reference label. There were no extra
  positives, and 10 of 25 answers were accepted.
- **Rejections**:
  - 14 under rule R1. The answer was not valid JSON: the model left the `explanation` value unquoted.
  - 1 under rule R3. The quote was not found in the content (R23).
- **The rejected raw answers include correct labels**: MATCHES F1 for R11, R13 and R18, with verbatim quotes. The
  failure is the output format, not the labelling. They stay rejected in v1, as the rule says.
- **One accepted answer has the wrong fact**: R09 (SqueezeBits) was labelled MATCHES F4 (the attention quantizer)
  where the reference is F1 (INT8 slower).
- Median latency 4.2 s per call. Tokens: 27.0k prompt and 17.5k completion in total, mostly reasoning tokens.

## 7. Amendment 1, written after v1 and before v1.1

- **The only change is the output format.** Calls use Token Factory structured output (`response_format` JSON
  schema): `label` is an enum of the four labels, and `fact_id`, `quote` and `explanation` are strings.
- The prompt, the inputs, temperature 0, the validator and the reference labels are unchanged.
- Structured output was checked only on an unrelated dummy text (a banana-bread recipe), never on a snapshot
  result.
- v1.1 runs once and is reported next to v1. The format change is disclosed wherever v1.1 is cited.

## 8. Run v1.1 (structured output, amendment 1), 2026-10-14

Output: `artifacts/reports/errata_grounded.{json,md}`.

| | v1 (free text) | v1.1 (structured output) |
|---|---|---|
| Valid JSON | 11/25 | **25/25** |
| Accepted by the validator | 10/25 | 20/25 |
| **Primary**: reference MATCHES/CONTRASTS recovered and accepted | 1/6 | **2/6** (R13 MATCHES F1, R15 CONTRASTS F1) |
| Reference positives with the right label and fact, ignoring the validator | — | **5/6** (all except R09) |
| Extra positives (accepted) | none | R12 |
| Label agreement on all 25, ignoring the validator | — | 18/25 |
| Rejections | R1 ×14, R3 ×1 | R4 ×4 (in 3 results), R3 ×2 |
| Median latency per call | 4.2 s | 4.2 s |

**Reading**

- **Structured output fixed the format completely.** Once the answer is valid JSON, Nemotron's labels agree with
  the reference on 5 of the 6 field reports that match or contrast with our measurements.
  - It found the ModelOpt INT8 regression thread on Orin Nano (R11, R18), DEIMv2 on Orin NX (R13), and the YOLO
    reports where INT8 is faster (R14, R15).
  - It linked R09 (SqueezeBits) to F3 instead of F1. Both facts are about INT8 being slow, but F3 is the
    `--int8`-only build.
- **The validator is strict by design, and that strictness costs recall here.**
  - R11 and R18 were rejected because the explanation rounded numbers from the content: 23.97 → "24",
    114.5 → "114", 41.8 → "42".
  - R14 was rejected because the validator does not read numbers with a unit attached in the content ("15W").
    This is a validator limitation, found after the run. It is not fixed for this result.
  - Sensitivity, stated now and not used as the primary result: with unit-attached numbers recognised, R14 would
    pass (3/6). The rounded numbers would still fail. Exact numbers only is the rule we want for a deployment
    report.
- **Disagreements are mostly at the APPLIES_UNVERIFIED / NOT_APPLICABLE boundary**: 5 reference NOT_APPLICABLE
  results were labelled APPLIES_UNVERIFIED. Nemotron is more inclusive than the reference.
  - The one accepted extra positive, R12, is a forum index page whose only relevant text is the title of the 2.7×
    regression thread. It is arguably a match through the title. The reference labelled it NOT_APPLICABLE.
- **What a developer gets**: a table of field reports, each tied to one of our measured facts by a verbatim quote that
  code has checked. Here that means two accepted rows linking the Orin INT8 slowdown to independent reports, plus
  a contrast row. No fabricated quote was accepted. The number check is weak; see §9.

## 9. Correction after external review 4 (2026-10-14): what the validator does and does not check

- **R3 (quote) is strong.** The quote must occur verbatim in the result's content, so a fabricated quote cannot be
  accepted.
- **R4 (numbers in the explanation) is weak.** It checks only that each number occurs somewhere in the content,
  the quote or the cited fact. It does not catch any of the following, all reproduced in
  `tests/test_errata_grounding.py`:
  - Swapped values, e.g. FP16 and INT8 QPS exchanged.
  - Numbers with a unit attached, e.g. "999ms". The pattern skips them.
  - Single-digit claims, e.g. "7x".
- **Consequence for the report.**
  - The earlier wording "every number is real" overstated the check and is withdrawn.
  - What holds: the rendered report shows no model-written numbers at all. It shows the label, the fact id, the
    verbatim quote (R3) and our own fact text from the config. A test now pins this.
  - The explanations stay in the JSON for audit only.
- **Further caveats on §8.**
  - Two of the six reference positives, R11 and R18, are the same forum thread (same URL, different excerpts). The
    six cover five distinct sources.
  - The reference labels were written by the assistant, not by an independent expert.
  - The headline result remains **2/6 with every rule satisfied**. The 5/6 figure ignores the validator.
- **For a next version (to be pre-registered)**: structured claims in place of free text.
  - Each claim gives subject, metric, value and unit, and code checks it against the quote.
  - The report sentence is generated from those fields.
