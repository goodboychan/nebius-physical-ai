# QuantGate — Devpost submission draft (2026-10-12)

Status: **draft**. Sections marked `[PENDING S4]` are filled in after stress v2 S4 is unsealed and analyzed. Items
marked `[USER]` are the user's own ratings and opinions. Every number cites a committed artifact; if a number changes,
update it from the artifact, never from memory.

---

## Elevator pitch (≤ 200 chars)

QuantGate gates quantized robot policies before they reach a Jetson arm, and it measured what actually broke them:
not INT8, but grip margin, a 3 cm shift, and an AI judge that never says no.

## Inspiration

Edge deployment of robot policies usually means INT8. Open-loop metrics look fine, yet closed-loop behaviour can change,
and checking every quantized variant on the real robot is slow and sometimes unsafe. We wanted to know two things:
whether an offline audit could screen INT8 variants before they touch the robot, and whether the screen holds up
against a real arm. We also wanted the answer to be trustworthy, so the whole experiment was pre-registered, blinded
and hash-locked before the first real trial.

## What it does

1. **Builds a variant grid.** One FP32 ACT policy (LeRobot, 51.6M parameters) is trained on 120 SO-101 teleoperation
   demos. It is quantized with NVIDIA TensorRT Model Optimizer into 24 INT8 variants that differ only in calibration
   choices (size 16–1024, data composition, per-tensor vs per-channel), plus FP16 and FP32. All are built as TensorRT
   engines on a Jetson Orin Nano Super.
2. **Audits offline.** Five predictors score every variant on 2,000 held-out states, in bootstrap fan-out on Nebius
   Jobs: two fidelity scores with tail statistics (CVaR@90), a practitioner heuristic, open-loop MSE and latency. The
   ranking is frozen and hashed (`LOCK-2`) before any real trial.
3. **Gates on the real arm.** 245 blinded, interleaved trials run on the SO-101 (pick a can and stand it on a
   coaster). The operator never sees which engine is running, and the cell-to-engine map stays sealed until `LOCK-3`.
4. **Supervises and judges with AI.** `nvidia/Cosmos-Reason2-2B` on a Nebius AI endpoint watches every run at 2 Hz in
   shadow mode, and is also asked at the end whether the task succeeded.
   `nvidia/nemotron-3-super-120b-a12b` on Nebius Token Factory writes go / no-go deployment reports, and every number
   in a report is machine-checked against the evidence. Tavily collects TensorRT and Jetson errata, with queries
   derived from the real build environment.
5. **Stress-tests.** A follow-up with pre-registered stop rules tests what happens when the deployment margins shrink:
   gripper friction, a shifted start position, and an unseen can.

## Results

Sources: `artifacts/reports/g6_analysis.json`, `g6_supplement.json`, `d4_retro_judge_g6.json`,
`power_bench/SUMMARY.md`, and `docs/sessions/stress_operator_notes.md`.

**1. INT8 calibration choices did not matter, in this regime.**
- FP32 succeeded 24/25. Each of the 10 INT8 cells tested succeeded between 9/10 and 25/25.
- Primary endpoint, audit-selected vs random-selected cells: 73/75 vs 73/75. The difference is 0.0 pp, 95% CI
  [−6.8, +6.8].
- Best vs worst fidelity: +0.7 pp, 95% CI [−6.4, +14.1].
- The same cell re-measured on another day differed by −4.0 pp, 95% CI [−19.5, +12.4], which is wider than any
  between-cell contrast.
- Offline rank vs real placement error: Spearman 0.02 for `score_align` and 0.08 for `score_mag`.
- We report this as "no gap detected", not as "no effect". In this regime, the honest conclusion is that an elaborate
  audit pipeline was unnecessary.

**2. On the Orin Nano Super (15 W, TensorRT 10.3), FP16 beats INT8.**

GPU compute time per 100-step chunk, from trtexec:
- FP16: 11.6 ms, 82 mJ per inference.
- INT8: 16.8–17.1 ms, 101 mJ.
- FP32: 53.4 ms, 403 mJ.

INT8 draws about 1 W less while it runs but is slower, so it uses more energy per inference. Calibration choice
changes neither latency nor power. *(Note: an earlier Python-loop latency probe from the audit put FP16 at about the
INT8 level. The claim above uses the trtexec measurement only, and the FP16 real-arm run below settles end-to-end
behaviour.)*

**3. Deployment margins dominated quantization** (observational, same arm and policy, not randomized against each
other).
- Gripper anti-slip pads removed: 8/24 on the nominal scene. Most failures were the can slipping.
- Rubber bands on the gripper: 22/24 on the nominal scene.
- Start spot shifted 3 cm: 0/3. The policy first reaches for the memorized training position, grasps air, then
  knocks the can over while re-grasping.
- Unseen yellow can: `[PENDING S4]`.

**4. AI judges must be validated before they are trusted (the RLAIF caveat).**
- Retrospective test: Cosmos-Reason2 was shown the final frame of all 245 G6 trials and asked whether the can stood
  on the coaster. It answered **"Yes" 245 times** and caught **0 of the 7 failures**. The 97% agreement only mirrors
  the success rate.
- In the stress blocks so far it said "No" on only 2 of 20 operator-confirmed failures (public logs: v1 S0 16, v2 S0 1, v2 S1 3).
- Our own geometric judge also produced false failures once the can sat slightly off-center (a spurious circle on the
  coaster). We found this from operator reports, fixed it with a blind, pre-declared re-judge rule, verified that the
  rule changes no G6 outcome, and still disclose the one remaining false negative.

## How we built it

- **Data**: 120 teleoperated demos on an SO-101. Overhead C922 and OpenMV AE3 wrist cameras. Seeded 80/20/20 splits
  with loader-level guards so that audit states never touch training or calibration.
- **Training**: LeRobot 0.6.1 ACT, 100k steps on Nebius Jobs (L40S, 1 h 57 min). Data and weights live in Nebius
  Object Storage.
- **Quantization**: TensorRT Model Optimizer INT8 Q/DQ ONNX. Orin TensorRT 10.3 engines built with a frozen timing
  cache, because builds are otherwise nondeterministic.
- **Audit**: 25 cells × bootstrap scoring, fanned out on Nebius Jobs (CPU), with a controller that keeps the job count
  under the quota.
- **Runtime**: a TensorRT policy server on the Orin at 30 Hz with chunk prefetch and blending. Supervision is
  Cosmos-Reason2 on a Nebius AI endpoint (vLLM on L40S, about 330 ms round trip), in shadow mode so that network delay
  cannot contaminate outcomes.
- **Reports**: Nemotron 3 Super on Token Factory turns frozen evidence into deployment reports. A validator rejects
  any number that is not in the evidence. Tavily errata snapshots are hashed for reproducibility.
- **Integrity**: a pre-registration and a decision log that is never rewritten. Hash locks run `LOCK-1` → `LOCK-2`
  → `LOCK-3`, with sealed schedules and stop rules fixed before outcomes. All amendments and deviations are logged
  with timestamps.

## Challenges

- **INT8 slower than FP16** on the deployment target, the opposite of the usual assumption.
- **Nondeterministic engine builds** gave different engine files from the same inputs. A frozen timing cache made the
  outputs bit-identical.
- **Latency as a confound**: the FP32 chunk boundary is slower than INT8, which changed arm motion. Prefetch with
  blending equalized the timing across cells before any counted trial.
- **Real hardware**: overload foldback, a camera that hung after unclean exits, a motor packet error, slipping grasps,
  and anti-slip pads that kept shifting.
- **A fragile judge**: the circle detector's verdict depended on the RGB → gray conversion path.

## Accomplishments

- A pre-registered, operator-blinded, hash-sealed real-robot study of quantization, finished inside a hackathon:
  245 + 120+ trials.
- A clear, reusable deployment answer for this hardware: FP16. INT8 calibration tuning bought nothing.
- Evidence that hardware margin and distribution shift are larger risks than quantization error for this policy.
- A measured failure of an AI judge, which is a concrete caution for RLAIF-style pipelines.

## What we learned

- A deployment gate has to test **margins** (grip, position, object), not only numerics.
- "No difference detected" needs its noise floor next to it. Our same-cell retest CI was wider than the effect we were
  looking for.
- Validate the judge, both the AI judge and our own.

## What's next

- Run the FP16 engine on the real arm (pre-registered, 20 trials) to close the precision question end to end.
- Use a wider deviation range, such as more aggressive quantization, to find where degradation starts.
- Recompute the offline audit on out-of-distribution inputs, to see whether score gaps widen there.
- Try an AI judge that uses multiple frames or video before considering any RLAIF use.

## Built with

NVIDIA Cosmos-Reason2-2B · NVIDIA Nemotron 3 Super · NVIDIA TensorRT · NVIDIA TensorRT Model Optimizer · Jetson Orin
Nano Super · Nebius AI Cloud (Jobs, AI Endpoints, Object Storage) · Nebius Token Factory · Tavily · LeRobot · SO-101 ·
vLLM · PyTorch

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
- `nvidia/Cosmos-Reason2-2B` for vision supervision, because it is small enough for about 330 ms round trips at 2 Hz.

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
