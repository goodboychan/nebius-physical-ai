# Related work notes (2026-10-11)

These notes support QuantGate and the AEP-facing physical registration
(`docs/aep_physical_registration_v1.md`). Every number is quoted from the cited paper; nothing is recomputed. Each entry
says how much of the paper was read.

## Closest: offline prediction of quantization-induced degradation

**PreDE — "Predict Before You Deploy: Offline Prediction of Quantization-Induced Task Degradation for World Action
Models"** (Xu, Guo, Chen, Du, Shi; arXiv 2609.19441, 2026-09-16). Full text read.

- Question: from offline action deviation on a fixed observation log, can one accept, reject or defer a quantization
  configuration before closed-loop evaluation?
- Method: a policy-specific calibration on a development set fixes two thresholds (largest acceptable deviation,
  smallest degraded deviation). New configurations are accepted, rejected or deferred. The paper formalizes this under a
  "within-setting single-crossing" hypothesis, stated as a post hoc formalization.
- Models and settings: five world action models (Cosmos Policy, UVA, mimic-video, RynnVLA-002, Fast-WAM). Simulation on
  LIBERO, RoboCasa-24, PushT and PushT-M. RTN, HQQ, ViDiT-Q INT8, SVDQuant-style W4A4 and QServe-style W4A8.
- Held-out result: 21 decisions on 28 held-out configurations (75% coverage), all matching the observed labels.
  Deferred candidates include a 33-point loss.
- Real robot: a Franka Research 3 with two tasks (cup, cubes), 450 trials, running on an RTX 5080 server. Groups are fixed
  before the trials. Every high-deviation configuration (W2) degrades significantly. No low-deviation comparison is
  significant at 0.05 (for example, HQQ W3 on cups is −10.0 pp, Newcombe 95% [−31.4, +11.0]). W4A4 gives a 1.37×
  query speedup and about 44% less peak memory. The RTN W2 stress tests use fake quantization.
- Cross-policy note: Fast-WAM W3 loses 5.4 pp at a smaller deviation than Cosmos HQQ W3, which loses 0.51 pp. A shared
  deviation threshold therefore fails across policies.
- **Difference from QuantGate**:
  - Server GPU and fake quantization, versus real TensorRT INT8 engines on a Jetson edge device.
  - Variants that differ by bit width (W2–W8), versus 24 INT8 variants that differ only in calibration choices (size,
    composition, granularity) — the decision practitioners actually face at a fixed precision.
  - Prospective grouping without preregistration, blinding or interleaving, versus a preregistered, operator-blinded,
    seeded-interleaved, sealed and hashed protocol.
  - One deviation metric, versus five predictors compared head to head (alignment, magnitude, practitioner heuristic,
    open-loop MSE, latency).
  - Not reported there: build nondeterminism with a frozen-cache fix, INT8 slower than FP16 on Orin, and inference
    latency as a confound in real-arm comparisons.
- **How it bears on our result**: their low-deviation groups show no significant degradation. Our INT8 calibration
  variants all sit in a narrow deviation range, and the K2 interim fired, so the two results are plausibly in the same
  direction. This is to be confirmed after LOCK-3, and only for our regime.

## Offline–closed-loop dissociation for compressed policies

**"Anatomy of a Closed-Loop Collapse: A Causal Case Study of a Compressed VLA Policy"** (Jia; arXiv 2609.23048, IROS
2026 ScaleInfra workshop poster). Full text read.

- An 8-layer distillation of Octo-Base keeps 86% of the parameters and passes the model family's own offline checks
  (teacher ratios 0.996 and 1.000). In closed loop it collapses to 0/72, against the teacher's 40/72, on SimplerEnv
  WidowX pick-and-place. Simulation only.
- The failure is stage-localized: transport to target is 0%. Four standard fixes fail. Substituting deployment-
  distribution teacher rollouts restores parity (18/36 vs 17/36 held-out).
- Its operational claim: offline gates are insufficient as standalone acceptance tests, and a few dozen closed-loop trials
  found what they missed. It states that the offline–closed-loop gap itself is established prior work and is not its
  own claim.
- **Relevance**: it motivates closed-loop qualification, which supports the AEP claim and QuantGate's insistence on real
  trials. The compression there is distillation rather than PTQ, and the evidence is simulation only.

## Robustness loss of quantized VLAs out of distribution

**"Beyond In-Distribution Preservation: Recovering Generalization in Quantized VLAs via Vulnerability-Oriented Tuning"**
(arXiv 2610.05745, 2026-10-05). **Abstract only, full text not read.**

- From the abstract: PTQ is known to preserve VLA performance under standard evaluation conditions, and the paper asks
  whether it also preserves the full-precision model's robustness and generalization.
- **Relevance**: it is the motivation for the stress test (S1 start-position shift, S4 unseen can). Read the full text
  before citing any specific number.

## Other entries, to read before citing

- Critical Interval MSE — offline validation for robot manipulation policies (arXiv 2606.29898).
- PTQ methods for VLAs, which optimize quantization rather than evaluate it: QuantVLA (2602.20309), Mix-QVLA
  (2606.19565), SQIL (ICCV 2025), CHASE-VLA (2610.02666), FoldQuantVLA (2609.24433), Q-WAM (2609.33269).
- An evaluation-gap reference cited by both papers above: AutoEval (Zhou et al., arXiv 2503.24278).
- Classic covariate-shift accounts: Ross & Bagnell 2010, Ross et al. 2011 (DAgger).

## Positioning rules for writing

- Do not claim to be the first offline predictor of quantization degradation, or the first real-robot study of it.
  PreDE precedes us by about three weeks.
- Position QuantGate as: fixed-precision calibration choices, real edge INT8 engines, a preregistered and blinded
  protocol, a head-to-head comparison of predictors, and deployment pitfalls.
- State the scope: one task, one checkpoint, one backend, one vision ACT policy. This is an extension, not a
  generalization.
- Ceiling caveat: a narrow deviation range plus a near-ceiling task means "no detected difference" may reflect a small
  effect size. Report the stress test as the first response, and note that a wider deviation range (more aggressive
  quantization, as in PreDE) would be needed to show where degradation starts.
