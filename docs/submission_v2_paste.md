# QuantGate — second submission, paste-ready (Devpost fields in order)

Frozen at LOCK-4 (2026-10-23). Every number comes from committed artifacts. `[USER]` marks what only you can fill in.
Sources: the body is `docs/devpost_about.md`; the answers are `docs/submission_draft.md`.

---

## 1. Project name

QuantGate

## 2. Elevator pitch (≤ 200 characters)

Proposed for the second submission (199 characters, matches video v11):

> For developers shipping LeRobot policies to Jetson: QuantGate measures cost on the device, runs sealed real-arm trials, and says what to validate, hold or block. Earn the next test, not the approval.

First submission (178 characters, chosen 2026-10-16):

> QuantGate reviews quantized robot policies before they ship to a Jetson: cost on the device, blinded real-arm trials, and an honest verdict. Earn the next test, not the approval.

## 3. Track

Physical AI

## 4. About the project (paste as Markdown)

## Inspiration

It started as a small gesture: a robot arm that brings a drink to someone working hard. Setting the can down
properly on the coaster turned out to be the hard part, and we got curious about it.

We had a robot policy that worked: an SO-101 arm picks up a cola can and stands it on a coaster, driven by a LeRobot
ACT (Action Chunking with Transformers) policy. Then we had to put it on a Jetson Orin Nano Super. That gave us
26 ways to ship the same checkpoint: FP32, FP16 and 24 INT8 builds that differ only in how they were calibrated.

Benchmarks told us speed, and open-loop metrics all looked fine. Neither told us whether the arm would still put the
can on the coaster, or how sure we could be. Same robot, same task: one run succeeds, one fails.

So we built the tool we wanted: a **deployment review** that puts cost, offline scores and real-arm evidence side by
side, and says plainly when the evidence is not enough.

## What it does

For every candidate engine, QuantGate answers three questions.

1. **Which candidate do I validate first?**
   - It measures cost on the target device itself (trtexec, 15 W): FP16 takes **11.6 ms and 82 mJ** per inference,
     INT8 16.8–17.1 ms and 101 mJ, FP32 53.4 ms and 403 mJ.
   - On this Jetson, FP16 is the fastest and the cheapest, not INT8.
2. **Which do I distrust?**
   - Broken calibrations: a deliberately black-frame-calibrated build is caught by a simple input check.
   - Builds that do not match what was audited: a preflight checks the engine hash, the normalization manifest and
     the runner's 200 ms chunk deadline. Only an explicit `GO` passes.
3. **Can I approve deployment?** Not yet, and the review says why.
   - Success against FP32 is compared as non-inferiority at a 10 pp tolerance, with a Newcombe interval. The
     **success criterion** is met when

     $$\text{lower bound of } \big(p_{\text{cand}} - p_{\text{FP32}}\big) > -10\ \text{pp}$$

   - That is one part of a final `GO`. A `GO` also needs placement error within its 5 px tolerance, the ceiling rule
     not holding the comparison undecided, and the deployment preflight passing.
   - With 25 trials per arm the success interval is about ±28 pp wide, so every comparison is
     `INSUFFICIENT_EVIDENCE`.
   - The review also says what would settle it. Our pre-registered ceiling rule keeps two arms that are both at or
     above 95% undecided at any sample size, so more trials alone are not enough. A revised, pre-registered rule is
     needed. Under it, about 120 trials per arm give 80% power **for the success criterion**; that is not the chance
     of a final GO.

A one-command CLI (`quantgate.py review | ask | preflight | cost | verify`) rebuilds the whole review from
committed, hashed evidence.

### What is new here

A gate in front of deployment, or a model that proposes while code decides, is not new on its own. What QuantGate adds
is the combination, measured on a real arm:

1. **The same policy, compared across its deployable builds.** FP32, FP16 and 24 INT8 calibrations of one checkpoint,
   with cost measured on the Jetson and behaviour measured on the arm, side by side.
2. **Physical causes kept apart from the build.** Grip friction, the start position, a smaller can and a knocked wrist
   camera are tracked as deployment conditions, so a failure is not blamed on the precision by default.
3. **A fix that was checked, twice.** Failure found → new demonstrations → fine-tune → sealed comparison at conditions
   never in training, then the same again for the gaps the first fix left.
4. **The line between "better" and "approved".** An improvement, a cheaper build or a passing check is reported as what
   it is; deployment stays HOLD until the pre-registered rule says otherwise.

### Which model does what

| Part | Model or tool | Its job | What it is not allowed to do |
|---|---|---|---|
| The robot policy | ACT (51.6M), trained on Nebius Jobs | picks up the can | — |
| The candidates | TensorRT FP32 / FP16 / INT8 engines on the Jetson | the builds under review | — |
| The judge | Cosmos-Reason2 on a Nebius AI Endpoint | says whether the can ended standing on the coaster | decide a verdict on its own; it was validated on held-out recordings first |
| The writer | Nemotron 3 Super on Nebius Token Factory | explains the review in words | write any number, verdict or approval word (code rejects them) |
| The verdicts | plain code | every number, interval and GO / HOLD / BLOCK | — |

## Who it is for

Teams that ship learned robot policies to edge accelerators such as Jetson and Hailo: robotics startups, labs moving a
policy into a product, and integrators who must sign off a build. The need recurs. Every retrain, quantization,
compiler or device change makes a new artifact, and each artifact needs its own evidence.

- **Free entry point (Apache 2.0)**: the on-device preflight that blocks a build that does not match what was
  audited, and the CLI that rebuilds the review from hashed evidence with no GPU or API key.
- **What a team would pay for**: a review per deployment artifact (cost on the target device, the blinded real-arm
  protocol, the validated judge and the evidence report), and the same check in CI on every new build. The compute
  behind it (fine-tuning jobs, the judge, the report agent) runs on Nebius.
- **First users**: the LeRobot and SO-101 community, reached through the public datasets and this repository.
- **Why now**: from 20 January 2027 the EU Machinery Regulation (2023/1230) puts machine-learning safety components
  under third-party conformity assessment. QuantGate does not claim compliance. Its pre-registered, hashed records are
  the kind of evidence such reviews ask for.
- **Status**: not yet tried by outside teams. Every number here comes from our own arm.

## How we built it

- **Data and training**:
  - 120 teleoperated demonstrations, recorded with LeRobot.
  - ACT (51.6M parameters, 100-step chunks) trained on **Nebius Jobs** with an L40S GPU.
  - 26 TensorRT engines built on the Jetson with a frozen timing cache, so the same file always behaves the same.
- **Offline audit**: 2,000 held-out states scored on 48 CPU jobs on Nebius Jobs. The ranking was frozen before any
  real trial.
- **Real arm**: **745 trials** in 18 sessions, all under sealed, interleaved schedules.
  - The operator saw trial numbers only. In the fine-tune blocks the two policies moved visibly differently, so
    operator blinding there was partial; outcomes come from an automatic judge and a blind video re-judge.
  - Logs are hashed before they are unsealed, so no rule can change after the results are seen.
  - The primary analyses were pre-registered. Rules set after aggregate results and post-hoc observations are
    labelled as such in the decision log.
- **AI layers on Nebius**:
  - **Cosmos-Reason2 on a Nebius AI Endpoint** judges the final frame of each trial.
  - **Nemotron 3 Super on Nebius Token Factory** explains the review in words.
  - Code writes every verdict and number. A validator rejects model text that contains digits, verdict labels or
    approval words.
- **Cost of one review**: about **\$31** of Nebius cloud.

### Open data, end to end

The training input of every policy is public: 120 base demonstrations with their train/val/audit split, 50 position
demonstrations (fine-tune v1) and 50 yellow-can and far-start demonstrations (fine-tune v2), all LeRobot v3 under
CC BY 4.0. The split, the checkpoint choice on the validation set, the held-out conditions and the sealed evaluations
are linked in the README's "Data and lineage" table, so the path from a demonstration to an arm result can be checked.

## What we found

- **The offline audit did not predict the arm.**
  - Its top-ranked INT8 cells went 73/75, and randomly picked cells also went 73/75.
  - The offline rank did not track placement error either (Spearman 0.02–0.08).
- **The risk was in the deployment conditions, not the precision.**
  - Removing the gripper's anti-slip pads dropped success to 8/24.
  - Moving the start 3 cm gave 0/3.
- **We fixed the weakness with data and re-tested it under a rule fixed in advance.**
  - 50 new demonstrations at −4…+4 cm and a 25-minute fine-tune on Nebius Jobs.
  - At held-out positions: **12/12 vs 3/12 at +3 cm** (+75 pp, 95% CI [+38, +91]) and **10/12 vs 2/12 at −3 cm**.
  - We then mapped how far the fix reaches, under a new pre-registration: **8/12 vs 0/12 at −6 cm**, beyond the
    demonstrations, but **0/12 vs 0/12 at +6 cm** and **0/12 vs 3/12 with a smaller yellow can at +3 cm**. The review
    now states the range where the fine-tune is a candidate, and where it is not. A pre-registered re-test, after we
    found and removed a scene deviation (stray markers, a knocked wrist camera), gave the same no-gain readings.
  - **Then we fixed those gaps too.** Fifty more demonstrations (the yellow can, starts at +5 and +7 cm) and a second
    fine-tune: **12/12 vs 7/12 with the yellow can** and **12/12 vs 2/12 at +6 cm**, both at conditions never in
    training, with no drop at the trained spot (12/12 vs 12/12).
  - At the trained spot it is still undecided (22/24 vs 23/24, with a pre-registered replication), so the review
    does not approve it there.

## Challenges we ran into

- **Our own AI judge was wrong at first.**
  - Cosmos caught 1 of 21 failures with a one-word prompt. A validated prompt caught 20/21 on held-out recordings.
  - It then held up live on 96 new trials: 22/24 failures caught, 2/72 false alarms.
  - We learned to treat the judge as a component to test, not an oracle.
- **INT8 was slower than FP16 on this device.** That contradicts the usual assumption, and only on-device
  measurement showed it.
- **Small samples.** Honest intervals at 12–25 trials are wide. We had to design the review to say "not yet" instead
  of overclaiming.
- **Blinding a visible fix.** The fine-tuned policy moves visibly differently, so operator blinding was partial.
  Outcomes come from an automatic judge and a blind video re-judge, which agree.
- **Hardware is the unglamorous failure mode**: empty episodes, voltage errors and gripper friction. Each became a
  recorded deployment condition.

## Failure cases we publish

We keep these in the write-up on purpose; each one changed what the review says.

- **A knocked wrist camera.** Success at the trained spot suddenly fell. We kept every result sealed, ruled out the
  software, found stray markers and a wrist camera knocked off-axis, and fixed the mount. A pre-registered health
  check then read "back to nominal" (gripper chatter 0.11, near the earlier 0.13). Six trials run in the bad scene
  were discarded unopened.
- **The fix has a reach, and the scene mattered.** The first fine-tune worked from −6 to +3 cm with the cola can, but
  not at +6 cm or with a smaller yellow can. A second fine-tune fixed both (12/12). In that session the first
  fine-tune also did better than before (7/12 and 2/12 against 0/12), so part of the earlier gap was the knocked camera.
- **The first AI judge setup missed 20 of 21 failures.** After validation it still misses some: cans left standing at
  the start look like successes to it.
- **An offline warning that the arm did not confirm.** A deliberately broken calibration scored badly offline but went
  11/12 on the arm in 12 trials.
- **A hypothesis we could not confirm.** INT8 seemed to make the gripper chatter twice as much; a pre-registered test
  found 1.3x, not significant (p = 0.12).
- **The simulator cannot predict the arm yet.** An Isaac Sim twin agreed with 10 of 14 real runs only because it
  predicts failure every time.

## What we learned

- Measure cost on the target device. The precision name does not tell you the cost.
- "No failure observed" is not safety evidence. A review should say how far the evidence goes.
- An AI supervisor or judge is a part to validate, with held-out data, before trusting it.
- Pre-registration and sealing are cheap, and they make every number defensible.

## What's next

- On-policy audit and distillation from the 500+ logged rollouts.
- Hailo-8, which today misses the 200 ms deadline and is blocked by the preflight, in a shadow-mode run.
- The same review on an Isaac Sim twin of this task for thousands of closed-loop trials. The twin is calibrated to
  the real arm on a GB10 desktop, and its candidates would be re-checked on the real arm.

**Earn the next test, not the approval.**

## 5. Built with

NVIDIA Cosmos-Reason2-2B, NVIDIA Nemotron 3 Super, NVIDIA TensorRT, TensorRT Model Optimizer, Jetson Orin Nano Super, Nebius AI Cloud (Jobs, AI Endpoints, Object Storage, Managed MLflow), Nebius Token Factory, Tavily, LeRobot, SO-101, vLLM, PyTorch, Hailo-8 (portability probe)

## 6. "Try it out" links

- Dashboard (no robot needed): https://claude.ai/artifact/2tUAoJHBeT8uLU96BmgPNK
- Code (Apache 2.0, public): https://github.com/goodboychan/nebius-physical-ai
- Datasets:
  - https://huggingface.co/datasets/chans/quantgate-so101-coaster
  - https://huggingface.co/datasets/chans/quantgate-so101-coaster-positions
  - https://huggingface.co/datasets/chans/quantgate-so101-coaster-positions-v2

## 7. Video demo link

https://www.youtube.com/watch?v=z80w9vig-qA (upload `video/final/quantgate_v12_4k.mp4`; 2:57, about 101 s of the real arm)

## 8. Image gallery (15 images, 1800×1200, in this order)

Files: `video/devpost_gallery_15_v4.zip` (`docs/media/gallery_v4/`). Suggested captions:

1. `01_thumbnail.png` — QuantGate: evidence before deployment
2. `02_same_robot.png` — Same robot, same task: one run succeeds, one fails; a 3 cm shift makes it miss
3. `03_what_it_tells_you.png` — What QuantGate tells the developer: validate FP16 first, deployment HOLD, the next test planned
4. `04_workflow.png` — How it works: models suggest and describe, code decides
5. `05_review_fp16.png` — The Review panel: validate first, the deployment decision and why, the next test
6. `06_preflight.png` — Before the arm: HOLD or BLOCK, never a silent GO
7. `07_engine_cost.png` — Measured on the Jetson: FP16 11.6 ms and 82 mJ per inference
8. `08_cost_is_not_approval.png` — Cost is not approval: FP16 vs FP32 19/20 vs 10/10, INSUFFICIENT_EVIDENCE, HOLD
9. `09_audit_vs_arm.png` — The offline score did not predict the arm: 73/75 vs 73/75
10. `10_what_moved.png` — What moved success: grip and start position
11. `11_found_fixed.png` — Found, fixed with data, re-tested sealed: +3 cm 12/12 vs 3/12
12. `12_reach_on_the_table.png` — Where the fine-tune works, on the table
13. `13_finetune_v2.png` — Fine-tune v2 closed both gaps: 12/12 vs 7/12 and 12/12 vs 2/12
14. `14_failures_we_publish.png` — Physical failures we found and publish
15. `15_ai_layers.png` — AI layers, validated before use: Cosmos-Reason2 22/24 live, Nemotron explains

## 9. Submission file (≤ 35 MB)

`video/QuantGate_submission_v2.zip` (24.8 MiB): the repository snapshot with `START_HERE.md`. The narration audio and
the two older galleries are left out for size; they are in the repository.

## 10. Survey answers

**Repository URL**: https://github.com/goodboychan/nebius-physical-ai. Apache 2.0. Setup and reproduction are in the README (`quantgate.py verify | review | plan`; no GPU or API key needed to rebuild the review).

**Demo URL**: the dashboard, https://claude.ai/artifact/2tUAoJHBeT8uLU96BmgPNK (no robot needed). Video: https://www.youtube.com/watch?v=z80w9vig-qA.

**Which model(s) did you use, and why that size/variant?**
- `nvidia/nemotron-3-super-120b-a12b` for the deployment-report agent (D3). The report has to read a large evidence
  bundle (about 6.4k prompt tokens) and keep every number exact. In our six-model comparison on Token Factory, Super
  had **0 unmatched numbers** in every run, took 9–14 s per report, and always produced the complete four-section
  format (`artifacts/reports/d3_model_compare.json`). The larger and smaller variants either leaked reasoning text or
  truncated.
- `nvidia/Cosmos-Reason2-2B` as the end-of-trial judge: it reads the final overhead frame and answers an explicit criterion (the can upright on the coaster). It is small enough to serve from one L40S endpoint. The first setup (one-word answer) caught 1/21 failures; after a dev/eval re-evaluation the validated prompt caught 20/21 on held-out recordings and then 22/24 with 2/72 false alarms on 96 new real-arm trials. A 2 Hz shadow supervisor (CONTINUE/ABORT) did not detect failures and is reported as such.

**Nemotron output quality (1–10)**: `[USER]`.
- Worked well: numeric fidelity to the evidence, section structure, and honest "cannot decide" when no threshold was
  given.
- Fell short: it once invented a latency trend that was not in the data (caught by our validator), and it inserted a
  stray Polish fragment ("znacz…") into Korean text.

**Fine-tune, prompt-engineer or out of the box?** Out of the box, with prompt engineering. A fixed system prompt
defines the four-section format and the forbidden claims, and the evidence is passed as JSON. The report has gone through three versions.
- **v1**: the validator only checked that each number existed somewhere in the evidence.
- **v2**: the validator checked each candidate's sentences. An external review then showed three wrong sentences
  passing it: two candidates both called GO, a reference's 10/10 attached to the candidate, and GPU time called
  end-to-end latency.
- **v3**: every verdict, number and status is written by code. Nemotron writes only "why the review looks like this"
  and "questions to resolve", and code rejects any digit, verdict label, approval word or known misreading
  (`tests/test_d3_v3.py`).
  - The first v3 runs still misread two facts in plain words. FP16 was said to use "the least power"; it has the
    least energy per inference but draws more power while running. The AI judge was called trustworthy. Both
    patterns are now rejected, and the earlier runs are kept (`d3_report_v3_first*.json`).
  - A plain-words misreading of a new kind cannot be excluded by rules, so section 5 is labelled model-written.

**Compared with other models**: In the same Token Factory harness, Super was the only variant with zero unmatched
numbers and a complete format in every repeat. Ultra and the smaller variants leaked reasoning or truncated.
`[USER: add any personal comparison]`

**Most valuable Nebius capabilities**:
- **Jobs**: ACT training (L40S, 1 h 57 min), two fine-tunes (about 25 min each) and the 25-cell bootstrap audit (CPU fan-out, with a controller under
  the instance quota).
- **AI Endpoints**: Cosmos-Reason2 on L40S with vLLM, started and stopped per robot session, with token auth and
  weights read from our Object Storage bucket.
- **Object Storage**: demos, checkpoints and model weights shared by Jobs and Endpoints.
- **Token Factory**: Nemotron through an OpenAI-compatible API, with no GPU server to keep warm for a model used
  about one minute per report.

**Recommend running Nemotron on Nebius (1–10)**: `[USER]`.

**Experience compared with previous environments (1–10)**: `[USER]`.

**What would have helped**: `[USER]`. Candidates from our logs:
- Clearer quota errors on Jobs; we hit the instance limit and had to write a controller.
- vLLM argument quoting on endpoint creation, which broke one endpoint.
- Faster endpoint cold start, which took about 10 minutes from stopped.
- **Capacity visibility per region and platform.** On 2026-10-13 an AI Endpoint start waited over 20 minutes with no
  indication, then failed with `NotEnoughResources` (eu-north1, L40S). About an hour later, a Job in the same region got
  an L40S immediately. What would help:
  1. a live availability indicator per region and GPU type, in the console and the CLI;
  2. a fast failure or an estimated wait, instead of a silent timeout;
  3. suggested fallback regions or platforms, or an opt-in automatic fallback;
  4. a notification or queued reservation when capacity frees up.
  These would avoid launching VMs in the wrong region and retrying blind.

**What we hope to see from Nemotron next**: `[USER]`.

**Did you use Tavily?** Yes. `scripts/d5_errata_collector.py` makes runtime Tavily API calls, with queries derived from
the actual TensorRT version, device and operator types, and freezes the results as a hashed snapshot attached to the
deployment report.
