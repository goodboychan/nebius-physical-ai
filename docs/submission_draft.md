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
   AI layers are checked against the same evidence: a Cosmos-Reason2 supervisor and judge, and a Nemotron 3 Super
   report writer. Neither is trusted on its own word.

The results were sealed until all trials were logged, so no candidate was picked after seeing its results.

## What we found, and how it changes the decision

Scope throughout: one pick-and-place task, one ACT policy, a Jetson Orin Nano Super at 15 W, and TensorRT 10.3.

| Finding | Evidence | What it means for the developer |
|---|---|---|
| On this device FP16 has the lowest latency and energy per inference | trtexec: FP16 11.6 ms and 82 mJ; INT8 16.8–17.1 ms and 101 mJ; FP32 53.4 ms and 403 mJ (`power_bench/SUMMARY.md`) | Don't pick an engine by its precision label. Measure on the target. FP16 is the cost-favored candidate. On the arm: FP16 19/20, FP32 10/10, INT8 10/10; placement within tolerance of FP32; success undecided at this sample size; end to end 24.7 ms against 34.3 and 79.0 ms (`fp16_analysis.json`) |
| Audit-picked INT8 cells did not beat random ones | 73/75 against 73/75, 95% CI [−6.8, +6.8] pp; offline rank against placement, Spearman 0.02–0.08 (`g6_analysis.json`) | In this setting, the offline ranking is not evidence that one calibration is better |
| Against FP32 the evidence is insufficient for every INT8 cell | 194/200 against 24/25. At a 10 pp tolerance the Newcombe intervals span about ±23–53 pp, so all 10 cells are "insufficient evidence" (`g6_q2_sensitivity.json`) | "No failures seen" is not "safe". You would need about 110–120 trials per arm to show a cell is within 10 pp |
| Deployment conditions moved success far more | No anti-slip pads 8/24; rubber bands 23/24; start moved 3 cm 0/3 (observational); unseen yellow can 48/48, every engine 12/12 (`stress_v2_analysis.json`) | Validate the grip, positions and objects you will actually face |
| The AI judge, as configured, missed every failure | Shown the final frame of 245 trials, Cosmos-Reason2 answered "Yes" every time and caught 0 of the 7 failures. Live at 2 Hz on 215 trials, it never left CONTINUE (`d4_retro_judge_g6.json`) | A high agreement rate on mostly-successful data means little. Validate an AI judge on failures before you use it |

These results are about this task, this device and this experimental range. They do not show that INT8 is harmless
in general, or that calibration never matters.

## The deployment review (what the developer takes away)

The dashboard opens with this card (`dashboard/audit_gate.html`, "Deployment review"):

- **Cost-favored candidate**: FP16, measured on the Orin.
- **Real-arm status**: FP16 19/20, placement within tolerance of FP32, success insufficient evidence. INT8: all 10 cells insufficient evidence against FP32.
- **Verified for**: the cola can at the trained start mark, a fixed coaster, locked camera exposure and the gripper
  configuration in use.
- **Weak spots**: grip friction and changes in start position.
- **AI judge reliability**: not reliable in the current setup.
- **Next actions**: plan about 110–120 trials per arm to settle FP16 (or any cell) against FP32, add varied start
  positions, validate the judge with video input, and check grip friction on the deployed gripper.

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
| Deployment report | **Nemotron 3 Super** writes the report from frozen evidence; a validator checks every number | **Nebius Token Factory** |
| Errata | Tavily search with queries derived from the real build; the snapshot is hashed | Tavily API |

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

## Accomplishments

- A complete gate from cloud to real arm. Every number is traceable to a hashed artifact.
- 245 completed blinded real-arm trials in the main study, plus stress blocks. Pre-registered stop rules were applied
  as written.
- A review that says plainly when the evidence is not enough, including for our own AI components.

## What we learned

- Measure cost on the target device; precision labels mislead.
- "No failures seen" needs its interval next to it, together with the number of trials it would take to decide.
- Validate the judge, both the AI one and your own.

## What's next

- Settle FP16 against FP32 on success with about 110–120 trials per arm.
- Shorter replanning intervals (10 / 30 / about 90 steps) crossed with start-position shifts, to separate trajectory
  memorization from slow reaction.
- An offline re-evaluation of Cosmos: one frame with a larger output budget, and the last seconds of video.
- Structured verdicts: code decides, and Nemotron explains each verdict with links to its evidence.

## Built with

NVIDIA Cosmos-Reason2-2B · NVIDIA Nemotron 3 Super · NVIDIA TensorRT · TensorRT Model Optimizer · Jetson Orin Nano
Super · Nebius AI Cloud (Jobs, AI Endpoints, Object Storage) · Nebius Token Factory · Tavily · LeRobot · SO-101 · vLLM ·
PyTorch

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
checks every number against the evidence and flags forbidden claims, so a report is rejected rather than trusted.

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

**What we hope to see from Nemotron next**: `[USER]`.

**Did you use Tavily?** Yes. `scripts/d5_errata_collector.py` makes runtime Tavily API calls, with queries derived from
the actual TensorRT version, device and operator types, and freezes the results as a hashed snapshot attached to the
deployment report.
