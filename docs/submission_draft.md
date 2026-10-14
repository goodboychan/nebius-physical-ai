# QuantGate — Devpost submission draft (v2, 2026-10-12)

Status: **draft v2**, rewritten around the developer's decision, following the storytelling review. All experiment slots are filled (stress and FP16 unsealed 2026-10-13). `[USER]` marks the user's own
ratings. Every number cites a committed artifact. Wording rules: say "not detected", never "no effect"; FP16 is
"the cost-favored candidate" until its real-arm run is analyzed; completed and planned trials are counted
separately.

---

## Tagline

**QuantGate — Evidence before deployment.**

## Elevator pitch (≤ 200 chars)

QuantGate helps robot developers decide which precision of a policy to ship to a Jetson, showing engine cost,
real-arm behavior and how strong the evidence is, before the robot leaves the lab.

## The problem

You have a working robot policy and a small edge device. You can ship it as FP32, FP16 or one of many INT8 builds.
Benchmarks tell you speed, and open-loop metrics look fine. Neither tells you whether the arm will still put the can
on the coaster, or how sure you can be. Real-arm testing of every candidate is slow, so teams guess.

## What QuantGate does

For each candidate engine, QuantGate puts three kinds of evidence side by side and turns them into a **deployment
review**: what the evidence supports, what is still missing, and what to test next.

1. **Cost on the real device.** It builds every candidate as a TensorRT engine on the Jetson and measures latency,
   energy and size there.
2. **Offline audit.** It scores every candidate on 2,000 held-out robot states, fanned out on Nebius Jobs, and freezes
   the ranking before any real trial.
3. **Real-arm check.** It runs blinded, interleaved trials on the arm to test whether the audit's ranking holds. The
   AI layers are checked against the same evidence: a Cosmos-Reason2 supervisor and judge, and Nemotron 3 Super.
   Nemotron writes the report and checks Tavily field reports against our own measurements. Neither model is
   trusted on its own word: code decides every verdict and number, and checks what the models may add (verbatim quotes, restricted wording); the limits of those checks are stated.

The results were sealed until all trials were logged, so no candidate was picked after seeing its results.

## The three decisions QuantGate supports

| Developer's question | Evidence | QuantGate's answer |
|---|---|---|
| Which candidate do I validate first? | FP16 is cheapest on this Jetson (11.6 ms, 82 mJ per inference), and went 19/20 on the arm with placement within tolerance of FP32 | **FP16**: the recommended candidate to validate |
| Which candidates do I distrust? | Black-frame and noise calibrations: flagged by a simple input check, and by action MSE and both audit scores. The last three use thresholds set on the same 24 normal cells, so "no normal cell flagged" holds by construction (`simple_checks_vs_audit.json`) | **Calibration anomalies**: flagged offline. On the arm, PC-B went 11/12 against FP32 10/12, so the warning was not confirmed (insufficient evidence). Reject such builds at the input check anyway (`positive_control_analysis.json`) |
| Can I approve deployment? | Success against FP32 is undecided for every candidate at these sample sizes, and position changes are not validated | **Not yet**: on hold, with the missing checks listed |

The recommendation (what to test first) and the approval (whether to ship) are shown separately. A candidate can be
recommended while its approval is on hold.

## What we found, and how it changes the decision

Scope throughout: one pick-and-place task, one ACT policy, a Jetson Orin Nano Super at 15 W, and TensorRT 10.3.

| Finding | Evidence | What it means for the developer |
|---|---|---|
| On this device FP16 has the lowest latency and energy per inference | trtexec: FP16 11.6 ms and 82 mJ; INT8 16.8–17.1 ms and 101 mJ; FP32 53.4 ms and 403 mJ (`power_bench/SUMMARY.md`) | Don't pick an engine by its precision label. Measure on the target. FP16 is the cost-favored candidate. On the arm: FP16 19/20, FP32 10/10, INT8 10/10; placement within tolerance of FP32; success undecided at this sample size; end to end 24.7 ms against 34.3 and 79.0 ms (`fp16_analysis.json`). Field reports point the same way: Nemotron, reading Tavily results, tied an NVIDIA forum report of ModelOpt INT8 running slower than FP16 on Orin NX to this measurement, with a code-checked verbatim quote. It also labelled the 2.7× Orin Nano INT8 regression thread correctly, but the validator rejected that answer for rounding the thread's numbers (`errata_grounded.md`) |
| Audit-picked INT8 cells did not beat random ones | 73/75 against 73/75, 95% CI [−6.8, +6.8] pp; offline rank against placement, Spearman 0.02–0.08 (`g6_analysis.json`) | In this setting, the offline ranking is not evidence that one calibration is better |
| Against FP32 the evidence is insufficient for every INT8 cell | 194/200 against 24/25. At a 10 pp tolerance the Newcombe intervals span about ±23–53 pp, so all 10 cells are "insufficient evidence" (`g6_q2_sensitivity.json`) | "No failures seen" is not "safe". Showing a cell is within 10 pp would take about 110–120 trials per arm (a planning estimate that assumes both true success rates are equal at about 96–97%; it is not a guarantee) |
| Deployment conditions moved success far more | No anti-slip pads 8/24; rubber bands 23/24; start moved 3 cm 0/3 in a small, early-stopped test (observational, cause not isolated); unseen yellow can 48/48, every engine 12/12 (`stress_v2_analysis.json`) | Validate the grip, positions and objects you will actually face |
| The AI judge needed validation, and validation fixed its setup | First setup: 1/21 held-out failures caught. After a dev/eval re-evaluation (409 recorded trials), an explicit-criterion prompt caught 20/21 [0.77, 0.99] with 5/252 false alarms, 4 of them on the unseen yellow can (4/33) (`cosmos_judge_eval_preregistration.md`) | Treat an AI judge as a component under test: validate the exact prompt on labelled held-out trials, and watch per-object error rates |

These results are about this task, this device and this experimental range. They do not show that INT8 is harmless
in general, or that calibration never matters.

## The deployment review (what the developer takes away)

The dashboard opens with this card (`dashboard/audit_gate.html`, "Deployment review"):

- **Cost-favored candidate**: FP16, measured on the Orin.
- **Real-arm status**: FP16 19/20, placement within tolerance of FP32, success insufficient evidence. INT8: all 10 cells insufficient evidence against FP32.
- **Verified for**: the cola can at the trained start mark, a fixed coaster, locked camera exposure and the gripper
  configuration in use.
- **Weak spots**: grip friction and changes in start position.
- **AI judge reliability**: not reliable in the first setup (1/21). The validated prompt caught 20/21 offline; the live
  re-check is pending.
- **Next actions**: plan about 110–120 trials per arm (a planning estimate that assumes both true success rates are equal at about 96–97%; it is not a guarantee) to settle FP16 (or any cell) against FP32, add varied start
  positions, re-check the validated judge prompt live, and check grip friction on the deployed gripper.

It is a review aid, not an automatic approval. The trial videos sit next to the numbers, so the reader can see each
failure.

## How we built it (NVIDIA and Nebius, each where it did real work)

| Step | What runs | Where |
|---|---|---|
| Training | LeRobot ACT, 120 teleoperated demos, 100k steps | **Nebius Jobs** (L40S, 1 h 57 min), data in **Nebius Object Storage** |
| Candidates | 24 INT8 calibration variants with **TensorRT Model Optimizer**, plus FP16 and FP32 | NGC container |
| Engines and cost | **TensorRT** 10.3 engines with a frozen timing cache (builds were otherwise nondeterministic); latency and power with trtexec and tegrastats | **Jetson Orin Nano Super** |
| Offline audit | 25 cells × bootstrap scoring on 2,000 held-out states | **Nebius Jobs** fan-out with a quota-aware controller |
| Real arm | 30 Hz TensorRT policy server with chunk prefetch and blending, so all engines have identical timing; blinded schedule | SO-101 + Jetson |
| AI supervisor and judge | **Cosmos-Reason2-2B**, 2 Hz shadow mode, plus an end-of-trial question | **Nebius AI Endpoint** (L40S, vLLM), started per session |
| Deployment report | Code decides the verdicts; **Nemotron 3 Super** explains them; a structured validator checks each candidate's verdict, fractions and latency in the prose (`d3_report_v2.md`) | **Nebius Token Factory** |
| Errata, grounded | **Tavily** search with queries derived from the real build (snapshot hashed). **Nemotron 3 Super** labels each of the 25 results against our measured facts (matches / contrasts / applies but unverified / not applicable), with structured output; code checks that every quote is verbatim, and the report shows only those quotes and our own facts (`errata_grounding_preregistration.md`) | Tavily API + **Nebius Token Factory** |
| Experiment record | 5 experiments, 73 runs, filled from committed artifacts by a script; each run tagged with its source file and commit | **Nebius Managed MLflow**, run only for publishing and capture |
| Portability probe | The same checkpoint and calibration frames on a Hailo-8 (Raspberry Pi 5); backbones INT8 on Hailo, transformer FP32 on the CPU | Hailo DFC on a GPU workstation, measured on the device |

## Challenges

- INT8 was slower than FP16 on the target, the opposite of the usual assumption.
- Engine builds were nondeterministic; a frozen timing cache fixed it.
- Inference latency changed arm motion at chunk boundaries. We equalized it before any counted trial.
- Hardware: overload foldback, a camera that hung after an unclean exit, slipping grasps and shifting pads.
- Our own judges needed checking:
  - The circle detector produced false failures when the can sat off-center. We fixed this blind with a pre-declared
    re-judge.
  - An external review caught that our percentile bootstrap was too optimistic at zero failures. We corrected it with
    Newcombe intervals, both before unsealing the follow-up tests and as a separate sensitivity analysis for G6.

## Feedback to NVIDIA and Nebius

We logged every tool problem as we hit it (`docs/tool_feedback.md`). Each entry has the symptom, the cause and a
suggested fix.

- **TensorRT Model Optimizer**: PyTorch's fused multi-head-attention fast path bypasses `out_proj`, so a quantizer
  stays uncalibrated. Export then fails with "Quantizer has not been calibrated", which does not point to the fast
  path. A hint in the error would save hours on every transformer policy.
- **trtexec**: `--int8` alone falls back to FP32 with reformat layers. That build ran at 28.57 ms against 16.22 ms
  with `--int8 --fp16`, with no warning. The builder already knows the fallback count, so it could print it.
- **TensorRT on Jetson**: builds were nondeterministic in latency until we froze the timing cache. Measured on the
  Orin, INT8 was slower and used more energy than FP16 (16.8 vs 11.6 ms, 101 vs 82 mJ). Field reports agree.
- **Nebius AI Cloud**:
  - Capacity visibility: an AI Endpoint stayed in PROVISIONING for over 20 minutes before `NotEnoughResources`.
  - The `--platform` default is the most expensive GPU.
  - `--inject-file` documents its 64 KiB limit per file, but enforces it on the total.
  - Regional quota combinations are not obvious; eu-north1 had GPU quota but zero CPU quota.
  - Job overhead (about 4–5 minutes) dominates small jobs.
  - The Managed MLflow console does not refresh its provisioning status, and `PermissionDenied` does not name the
    missing permission.
- **Token Factory**: a Studio key authenticates against the Cloud API but returns empty lists, so "no access" looks
  like "no resources". Free-text JSON from Nemotron broke in 14 of 25 answers; structured output fixed all of them.

## Accomplishments

- A complete gate from cloud to real arm. Every number is traceable to a hashed artifact.
- 245 completed blinded real-arm trials in the main study, plus stress and FP16 blocks. Integrity caveats: the main study (G6) was pre-registered and blinded end to end. In the follow-ups the operator stayed blind to cells throughout, but some rules were set after aggregate outcomes were seen and before cells were unsealed: the stress re-judge rules (§9, §11) and the stress v2 design after v1 stopped. S1 was stopped early by the user after 3 trials. All are logged. Stop rules were applied
  as written.
- A review that says plainly when the evidence is not enough, including for our own AI components.

## What we learned

- Measure cost on the target device; precision labels mislead.
- "No failures seen" needs its interval next to it, together with the number of trials it would take to decide.
- Validate the judge, both the AI one and your own.
- **Constrain the format, then verify the content.**
  - Structured output took Nemotron's parseable answers from 11/25 to 25/25.
  - With every rule satisfied, 2 of the 6 reference matches and contrasts were recovered. Ignoring the validator,
    the labels agreed on 5 of 6, from five distinct sources, against reference labels we wrote ourselves.
  - The number check in the validator is weak, since swapped values can pass it. So the report shows only verbatim
    quotes, which are strictly checked, and our own facts, never a model-written number. It is an early-stage
    review assistant, not an oracle.
- **A verdict belongs to a target, not to "INT8".**
  - We used the same checkpoint and the same calibration frames on a Hailo-8.
  - Going from 16 to 1024 calibration frames *raised* the Orin INT8 error (0.054 → 0.062) and *lowered* the Hailo
    error (0.048 → 0.035).
  - The vendor emulator differed from the device by about half the quantization error.
  - This probe is offline only, and Hailo quantizes less of the graph.

## What's next

- Settle FP16 against FP32 on success: about 110–120 trials per arm (a planning estimate that assumes both true success rates are equal at about 96–97%; it is not a guarantee).
- Shorter replanning intervals (10 / 30 / about 90 steps) crossed with start-position shifts, to separate trajectory
  memorization from slow reaction.
- Re-check the validated Cosmos judge prompt live, on new trials. The offline re-evaluation is done: 1/21 → 20/21
  failures caught on held-out videos.
- A sealed real-arm block on the Hailo-8 target (FP32 vs Hailo, 12 vs 12), pre-registered separately.
- Structured verdicts (done in report v2): next, link each verdict to its trials and videos on the dashboard.
- **On-policy audit and distillation.** Build the audit buffer from the states the deployed engine actually visits:
  the 385 logged real-arm rollouts already have states and both camera videos. Label those states offline with the
  FP32 teacher, then use them in two ways:
  1. score candidates on the deployment distribution instead of demonstration states, to narrow the offline-to-real gap;
  2. run quantization-aware, on-policy distillation (DAgger with FP32 as the expert) to try to recover a broken build
     such as PC-B.
  Distillation can only close the student-teacher gap. It cannot fix weaknesses the teacher shares, such as the
  position shift; those need new demonstrations, as in the position fine-tune.

## Built with

NVIDIA Cosmos-Reason2-2B · NVIDIA Nemotron 3 Super · NVIDIA TensorRT · TensorRT Model Optimizer · Jetson Orin Nano
Super · Nebius AI Cloud (Jobs, AI Endpoints, Object Storage, Managed MLflow) · Nebius Token Factory · Tavily · LeRobot · SO-101 · vLLM ·
PyTorch · Hailo-8 (portability probe)

---

## Survey answers (draft)

**Repository URL**: `[after making the repo public]`. Apache 2.0. README setup instructions are still to be written.

**Demo URL**: not required (Physical AI). Video `[TODO]`.

**Which model(s) did you use, and why that size/variant?**
- `nvidia/nemotron-3-super-120b-a12b` for the deployment-report agent (D3). The report has to read a large evidence
  bundle (about 6.4k prompt tokens) and keep every number exact. In our six-model comparison on Token Factory, Super
  had **0 unmatched numbers** in every run, took 9–14 s per report, and always produced the complete four-section
  format (`artifacts/reports/d3_model_compare.json`). The larger and smaller variants either leaked reasoning text or
  truncated.
- `nvidia/Cosmos-Reason2-2B` for vision supervision, because it is small enough for about 330 ms round trips at 2 Hz. In our setup (one frame, one-word answer, 8 output tokens) it did not detect failures, so we report it as a configuration that needs validation, not as a model verdict.

**Nemotron output quality (1–10)**: `[USER]`.
- Worked well: numeric fidelity to the evidence, section structure, and honest "cannot decide" when no threshold was
  given.
- Fell short: it once invented a latency trend that was not in the data (caught by our validator), and it inserted a
  stray Polish fragment ("znacz…") into Korean text.

**Fine-tune, prompt-engineer or out of the box?** Out of the box, with prompt engineering. A fixed system prompt
defines the four-section format and the forbidden claims, and the evidence is passed as JSON. A post-hoc validator
checks numbers and, in report v2, each candidate's verdict, success fractions and latency against a code-decided table, so a report is checked rather than trusted. (The v1 validator only checked that each number existed somewhere in the evidence; an external review showed it missed swapped values, which v2 catches: `tests/test_d3_structured.py`.)

**Compared with other models**: In the same Token Factory harness, Super was the only variant with zero unmatched
numbers and a complete format in every repeat. Ultra and the smaller variants leaked reasoning or truncated.
`[USER: add any personal comparison]`

**Most valuable Nebius capabilities**:
- **Jobs**: ACT training (L40S, 1 h 57 min) and the 25-cell bootstrap audit (CPU fan-out, with a controller under
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
