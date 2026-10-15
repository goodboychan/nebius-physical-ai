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
- **Correction (external review 5, 2026-10-14).** An earlier version of this entry summarised PreDE as "server GPU and
  fake quantization". That understated it.
  - PreDE measures **real low-precision execution** on the robot's RTX 5080 server: W4A4 gives a 1.37× action-query
    speedup and about 44% lower peak memory.
  - Only the RTN W2 stress tests use fake quantization, with bf16 storage.
  - It also shows that **grouping matters at the same bit width**: on Cosmos/LIBERO, RTN W3 reaches 97.40% with group
    size 128 and 20.05% per channel.
  - Its rule already has an explicit **defer** outcome, the analogue of our INSUFFICIENT_EVIDENCE, and an evidence
    criterion of 2 SE on the success difference.
- **Difference from QuantGate**, stated narrowly:
  - Target. TensorRT 10.3 engines on a Jetson Orin Nano Super (edge, batch 1), versus a desktop-class server GPU.
  - Variant axis. 24 INT8 variants that differ only in calibration (size, composition, granularity), versus bit
    width, grouping and quantizer.
  - Protocol. Pre-registration, operator blinding, seeded interleaving and sealed, hashed outcomes. PreDE fixes its
    decisions and groups before outcomes but does not report blinding or interleaving.
  - Outcome. Our offline audit did **not** beat random selection (73/75 vs 73/75). PreDE's calibrated thresholds
    did predict its held-out labels. The two results are not in conflict, since our deviation range is narrow and
    near the ceiling, but QuantGate cannot claim a better screening rule.
  - Not reported there: build nondeterminism with a frozen timing cache, INT8 slower than FP16 on the target, and
    inference latency as a confound in real-arm comparisons.
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

## Edge deployment of ACT and VLAs on Jetson (added 2026-10-14, external review 5)

**"Bimanual Manipulation Within an 8 GB Budget: Zero-Copy Sensing and Quantized ACT on an Entry-Level Jetson"**
(Singh et al., GTRI; arXiv 2608.03938, 2026-08-04). Full text read.
- **Setup**: bimanual SO-101 on a Jetson Orin Nano Super (8 GB), ACT trained for 100k steps, TensorRT FP16 and INT8.
  The task is a deformable beanbag.
- **Results**:
  - Mean inference latency is 114.02 ms in PyTorch, 17.93 ms in FP16 and 12.65 ms in INT8.
  - Success is 19/20, 18/20 and 19/20 across the three precisions.
  - TensorRT's general-purpose INT8 calibration quantizes the ResNet-18 backbone but accepts **0 of 145 transformer
    layers**. As a result the INT8 engine is only 0.9% smaller than FP16.
  - Numerical deviation rose 15–40× while success was preserved. They note the forgiving target as a reason not to
    generalise this fidelity-versus-success divergence.
- **Overlap**: the same hardware tier, ACT and TensorRT, and the observation that numerical error does not settle
  success. Neither is a unique QuantGate finding.
- **Contrast worth stating**: there, INT8 is faster than FP16 (implicit calibration, backbone only). Here,
  modelopt explicit Q/DQ on the whole graph makes INT8 slower than FP16 (16.8 vs 11.6 ms). The quantized scope
  explains the difference, consistent with our Hailo probe. This supports "measure the engine you ship" and argues
  against any general claim about INT8 on Orin.

**FoldQuantVLA** (Ho et al.; arXiv 2609.24433, 2026-09-21). Full text read.
- **Method and speed**: W4A4 VLA engines with custom TensorRT plugins, on a Jetson AGX Orin and Ada GPUs. On Orin,
  W4A4 is 1.20–1.33× faster than the float TensorRT engine.
- **Robot results**: real-robot trials on SO-101 and ALOHA, 20 per task and arm. A selective INT8 configuration
  raises pooled GR00T N1.7 success from 80.0% to 92.5%.
- **Statements relevant to us**:
  - ModelOpt W4A16 AWQ is slower than the float engine on all four checkpoints.
  - A fixed action-cosine threshold does not transfer between checkpoints.
  - "Deployment requires checkpoint-specific latency and closed-loop evaluation."
- **Overlap**: real edge engines and closed-loop checks. "We measured real edge engines" is not a differentiator.

**VLAQuantBench** (Xu et al., the PreDE group; arXiv 2609.25376, 2026-09-21). **Abstract and introduction only.**
- **Scope**: controlled closed-loop PTQ evaluation, with 409 runs and 94,574 simulation episodes. It varies layer
  scope, numerical format and calibration.
- **Findings**: the interactions are recipe-dependent. For example, uncalibrated W4A4 on a π0.5 action-head subset
  goes from 7.0% to 70.5% when the scope is widened.
- It reports real-kernel and physical-robot measurements as a complement. Read the full text before citing more.
- **Bearing**: evaluation scale is theirs. QuantGate's contribution should be framed as a deployment decision
  procedure, not as a benchmark.

## VLMs as robot success judges

**"FailBench: How Reliable are VLMs at Judging Robot Task Success?"** (Navasardyan, Danielyan, Davtyan; Metric AI Lab;
arXiv 2609.03611, 2026-09-03). alphaXiv report read, not the full PDF.
- **Benchmark**: 2,197 attempts from 14 public sources, mostly with organic failures, and 13 detectors.
- **Results**:
  - The best mean balanced accuracy is 0.77 (Gemini 3 Flash).
  - Purpose-built failure detectors underperform most general VLMs.
  - There is a systematic bias toward "success" under ambiguity.
  - Contact-dependent outcomes are near chance.
  - Cropping to the outcome region adds about 2.3 points.
- **Overlap**: validating an AI judge before trusting it is established. Our Cosmos result (first setup 1/21, a
  validated prompt 20/21 on held-out trials, false alarms concentrated on the unseen can) is a small, setup-specific
  instance of the same lesson. It is not a new idea. Their success bias matches our first setup's "Yes" answers.

## Continual RL post-training and "no forgetting" claims (added 2026-10-15)

**"ACCRUE: Continual Off-Policy Reinforcement Learning for Robot Foundation Models"** (Kim, Lee, Narang, Guo; NVIDIA and
KAIST; arXiv 2610.18596, 2026-10-14; https://accrue-rl.github.io/). Full text read via alphaXiv.
- **Method**:
  - A lightweight actor and critic over action chunks (H = 16 in sim, 10 on the robot), on frozen DINOv3 features.
  - Both are inherited across tasks. Prior behaviour is kept by distilling the actor toward cached targets on 20–100
    retained episodes per task.
  - Simulation uses GR00T N1.7 with FastSAC on the Isaac-based FORGE and AutoMate assembly tasks.
  - On the real robot, a LoRA fine-tune on 5–10 SpaceMouse demonstrations per task comes first. Then FastTD3, chosen
    because explicit exploration-noise control "avoids erratic contact behavior". The sparse reward is labelled by an
    operator.
- **Results**:
  - 31.0–68.5% less real-robot interaction than single-task RL (AutoMate), 38.7–42.9% on NIST.
  - Retention: 18–20/20 per earlier task (118/120 pooled).
  - A stage stops once the running success over 20 episodes reaches 19/20. Code: "coming soon".
- **Relation to us**:
  - Same question as our position fine-tune: fix a weakness, then check that the old condition holds (T0, T0R).
    They fix it with RL, we did it with 50 new demonstrations.
  - Read with our rule (Newcombe, 10 pp tolerance):
    - 19/20 against 20/20 per task is undecided: degradation [−11.6, +23.6] pp at 95%.
    - Pooled, 118/120 sits within tolerance: [−1.7, +5.9] pp, if the reference is near 100%. But pooling hides
      per-task drops.
    - The stop rule ends a stage at a high running estimate, so the stage-end rate is biased upward.
  - Safety: no safety filter, interventions or hazard counts are reported for real-robot exploration.
  - An automatic reward labeller (for example our Cosmos judge, 22/24 caught and 2/72 false alarms prospectively)
    would need the same validation, because a false "success" becomes a wrong reward.
  - A quantized base policy is another base-policy change under the inherited critic, so the same deployment check
    applies.
- **Use**: cite as the RL alternative to our demonstration fine-tune and as an example of retention evidence. It is
  not prior art for the quantization gate.

## What QuantGate can and cannot claim as new (after external review 5)

- **Cannot claim**:
  - an offline deployment gate or an accept/reject/defer rule (PreDE);
  - real edge-engine measurement or SO-101 + Orin + ACT + TensorRT (2608.03938, FoldQuantVLA);
  - "numerical error does not predict success" as a finding;
  - judge validation as an idea (FailBench);
  - a screening score that beats random (ours tied random, 73/75 vs 73/75).
- **Can claim**, as an integrated hackathon system:
  - one review that puts the measured target cost, a sealed and blinded real-arm comparison with intervals, the
    runtime's timing contract, input and normalization integrity checks, and the AI layers' measured reliability
    side by side;
  - a decision that changed because of it: FP16 to validate first, approval on hold, a position weakness found and
    a fine-tune evaluated under a pre-registered rule;
  - a fixed-precision calibration axis on a real edge target, with a reversal of the calibration-size effect across
    two INT8 targets (Orin vs Hailo-8, offline).
- **Name collision**: a public Hugging Face project called `quantgate-student` (an action-chunk compression gate)
  exists. Use the subtitle "a robot deployment review" wherever the name appears.

## Other entries, to read before citing

- Critical Interval MSE — offline validation for robot manipulation policies (arXiv 2606.29898).
- PTQ methods for VLAs, which optimize quantization rather than evaluate it: QuantVLA (2602.20309), Mix-QVLA
  (2606.19565), SQIL (ICCV 2025), CHASE-VLA (2610.02666), Q-WAM (2609.33269). FoldQuantVLA is now covered above.
- An evaluation-gap reference cited by both papers above: AutoEval (Zhou et al., arXiv 2503.24278).
- Classic covariate-shift accounts: Ross & Bagnell 2010, Ross et al. 2011 (DAgger).

## Positioning rules for writing

- Do not claim to be the first offline predictor of quantization degradation, or the first real-robot study of it.
  PreDE precedes us by about three weeks. See "What QuantGate can and cannot claim" above.
- Position QuantGate as: fixed-precision calibration choices, real edge INT8 engines, a preregistered and blinded
  protocol, a head-to-head comparison of predictors, and deployment pitfalls.
- State the scope: one task, one checkpoint, one backend, one vision ACT policy. This is an extension, not a
  generalization.
- Ceiling caveat: a narrow deviation range plus a near-ceiling task means "no detected difference" may reflect a small
  effect size. Report the stress test as the first response, and note that a wider deviation range (more aggressive
  quantization, as in PreDE) would be needed to show where degradation starts.
