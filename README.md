<p align="center"><img src="docs/assets/quantgate_logo.png" alt="QuantGate" width="420"></p>

# QuantGate — a robot deployment review

**Evidence before deployment.** QuantGate helps robot developers decide which precision of a policy to ship on an
edge device. It shows the engine's measured cost, its real-arm behavior and how strong the evidence is.

> QuantGate screens INT8 robot policies offline on Nebius and gates which ones reach a Jetson-powered SO-101 arm.
> Cosmos-Reason2 watched the real runs (215 live, 245 retrospectively) and Nemotron writes the deployment report. The whole real-arm study was
> pre-registered, operator-blinded and hash-sealed (follow-up caveats under Limitations).

**License: [Apache 2.0](LICENSE)** · Nebius × NVIDIA Global AI Hackathon, Physical AI track · internal code name
`edgeqgate`

The logo's Q stands for QuantGate and quantization. The open passage at the lower right is the gate, and the small
square leaving it is a candidate that has cleared review for its next test. Passing the gate means "worth
validating next", not "approved": in this study no INT8 build was approved against FP32 (insufficient evidence).

## Results at a glance

<p align="center"><img src="docs/assets/risk_magnitude.png" alt="What moved the success rate" width="760"></p>

Numbers come from committed artifacts. The figure's script lists its sources.

1. **No success advantage from INT8 calibration choice was detected in this regime.**
   - FP32 succeeded 24/25. The 10 INT8 cells tested succeeded 194/200.
   - Audit-selected vs random cells: 73/75 vs 73/75. The difference is 0.0, 95% CI [−6.8, +6.8] pp.
   - The same cell re-measured on another day had a wider CI, [−19.5, +12.4] pp.
   - The offline rank did not predict placement: Spearman 0.02–0.08.
   - This is reported as *no difference detected*.
   - Against FP32, every INT8 cell is also *insufficient evidence* at a 10 pp tolerance. The Newcombe intervals are
     too wide at these sample sizes ([`g6_q2_sensitivity.json`](artifacts/reports/g6_q2_sensitivity.json)).
   - Sources: [`g6_analysis.json`](artifacts/reports/g6_analysis.json),
     [`g6_supplement.json`](artifacts/reports/g6_supplement.json).
2. **On the Orin Nano Super (15 W), FP16 is the cost-favored candidate.**
   - GPU compute: FP16 11.6 ms, INT8 16.8–17.1 ms, FP32 53.4 ms.
   - Energy per inference: 82, 101 and 403 mJ.
   - On the real arm FP16 succeeded 19/20, against FP32 10/10 and INT8 10/10 (one interleaved blinded session).
     Placement was within tolerance of FP32 (−0.63 px, CI [−2.64, +1.37]). Success: insufficient evidence at this
     sample size. End to end it took 24.7 ms per chunk, against 34.3 ms for INT8 and 79.0 ms for FP32
     ([`fp16_analysis.json`](artifacts/reports/fp16_analysis.json)).
   - Source: [`power_bench/SUMMARY.md`](artifacts/reports/power_bench/SUMMARY.md).
3. **Deployment margins mattered more than precision** (observational).
   - Without the gripper pads: 8/24. With rubber bands: 23/24.
   - In a small test with the start spot moved 3 cm: 0/3 (stopped after 3 trials). The arm first reached toward the trained
     start spot. Item 5 follows this up.
   - An unseen yellow can: 48/48, all four engines 12/12. Placement was within the 5 px tolerance of FP32 for every
     INT8 cell ([`stress_v2_analysis.json`](artifacts/reports/stress_v2_analysis.json)).
   - Source: [`stress_operator_notes.md`](docs/sessions/stress_operator_notes.md).
4. **The AI judge was validated and improved, within limits.**
   - In its first setup (final frame, one-word answer) Cosmos-Reason2 caught 1 of 21 failures on a held-out set.
   - After a dev/eval-split re-evaluation, a final-frame prompt with an explicit success criterion and an `Answer:` format caught **20/21** failures (Wilson 95% 0.77–0.99) with **5/252** false alarms on the same held-out set.
   - The false alarms concentrate on the unseen yellow can (4/33, 12%).
   - The setup is very sensitive to wording, the change combined prompt, format and token budget, and it judges only the end state (median 893 ms).
   - **Live, prospective re-check**: the same prompt, unchanged, ran on 72 new fine-tune trials. It caught **21/23**
     failures (0.73–0.98) with **1/49** false alarms ([`ft_cosmos_live_judge.json`](artifacts/reports/ft_cosmos_live_judge.json)).
     Other objects and scenes are still open.
   - Source: [`cosmos_judge_eval_preregistration.md`](docs/cosmos_judge_eval_preregistration.md), [`eval_scores.jsonl`](artifacts/cosmos_judge/eval_scores.jsonl).

5. **The position weakness was found, fixed and re-tested under a pre-registered rule.**
   - Data and training: 50 new teleoperated demos at −4, −2, 0, +2 and +4 cm. A 20k-step fine-tune from the same
     checkpoint on Nebius Jobs (L40S, 1,489 s). The FP16 engine cost is unchanged.
   - Evaluation: blinded and interleaved, 12 vs 12 per position, against the old policy, at positions not in
     training.

     | Start position | Fine-tuned | Old | FT − old, Newcombe 95% | Pre-registered reading |
     |---|---|---|---|---|
     | **+3 cm** (primary) | **12/12** | 3/12 | +75 pp [+38, +91] | improvement detected |
     | **−3 cm** (symmetry, added during the session and registered before any unsealing) | **10/12** | 2/12 | +67 pp [+27, +84] | improvement detected |
     | 0 cm (training mark) | 10/12 | 12/12 | — | insufficient evidence |

   - Reading: position improved on both sides of the trained start. Whether nominal performance is maintained is
     undetermined.
   - Off the training position, the old policy's commanded gripper also chatters about 4× more (exploratory,
     pre-specified metric).
   - Caveat: the operator could see that the two policies moved differently, so operator blinding was partial.
     Outcomes come from the automatic judge and the video re-judge, which agree block by block.
   - Sources: [`finetune_position_preregistration.md`](docs/finetune_position_preregistration.md) §14,
     [`ft_analysis.json`](artifacts/reports/ft_analysis.json).

Stress tests were unsealed on 2026-10-13. The stress protocol is
[`docs/stress_test_protocol.md`](docs/stress_test_protocol.md).

## How QuantGate uses NVIDIA models and Nebius

| Component | What runs | Where |
|---|---|---|
| Deployment target | LeRobot ACT policy (51.6M) as **TensorRT** FP32 / FP16 / INT8 engines | **Jetson Orin Nano Super** (TensorRT 10.3) next to a real SO-101 arm |
| Quantization | NVIDIA **TensorRT Model Optimizer** (modelopt) INT8 Q/DQ, 24 calibration variants | NGC PyTorch 25.11 container, local GPU |
| `D4` runtime supervisor | **`nvidia/Cosmos-Reason2-2B`** watches the overhead camera at 2 Hz (CONTINUE / FALLBACK / ABORT, shadow mode) and is asked at trial end whether the task succeeded | **Nebius AI Endpoint** (L40S, vLLM 0.29), about 330 ms round trip from the robot |
| `D3` deployment report agent | **`nvidia/nemotron-3-super-120b-a12b`** writes only the explanation and open questions of a report whose verdicts, numbers and status are all written by code; code rejects digits, verdict labels, approval words and known misreadings in the model text (report v3; v2 kept as history) | **Nebius Token Factory** |
| `D5` errata collector | **Tavily** search for TensorRT / Jetson / INT8 known issues, with queries derived from the real build environment and snapshot-hashed | Tavily API |
| `D5` errata grounding | **Nemotron 3 Super** labels each of the 25 field reports against our measured facts (matches / contrasts / applies but unverified / not applicable) with structured output; code checks that every quote is verbatim, and the report shows only those quotes and our own facts, never the model's numbers ([`errata_grounded.md`](artifacts/reports/errata_grounded.md), [pre-registration](docs/errata_grounding_preregistration.md)) | **Nebius Token Factory** |
| Policy training | LeRobot 0.6.1 ACT, 100k steps | **Nebius Jobs** (L40S, 1 h 57 min) |
| Audit fan-out | 25 cells × bootstrap scoring on 2,000 held-out states | **Nebius Jobs** (CPU) |
| Data and weights | demos, checkpoints, Cosmos weights | **Nebius Object Storage** (S3) |
| Experiment record | 5 experiments, 73 runs (grid, verdicts, real arm, Cosmos judge, Hailo probe), filled from committed artifacts by [`mlflow_publish.py`](scripts/mlflow_publish.py), each run tagged with its source file and commit | **Nebius Managed MLflow** (short-lived; CSV exports in [`artifacts/mlflow/`](artifacts/mlflow/)) |

**Where Token Factory helped.** The report agent needs a large reasoning model for about a minute per report. Token
Factory served Nemotron 3 Super, and the variants we compared, behind one OpenAI-compatible API, so no GPU server had
to stay warm. Comparison: [`d3_model_compare.json`](artifacts/reports/d3_model_compare.json). Final report:
[`d3_report_v3.md`](artifacts/reports/d3_report_v3.md) (history: [`d3_report_v2.md`](artifacts/reports/d3_report_v2.md), whose sentence-level validator let three wrong sentences through, and v1 [`d3_final_report.md`](artifacts/reports/d3_final_report.md)).

**Where Nemotron met Tavily.** Tavily finds field reports and Nemotron reads them against what we measured. Code
keeps only claims it can check.
- Free-text JSON broke in 14 of 25 answers; structured output fixed all of them.
- **With every rule satisfied, 2 of the 6** reference matches and contrasts were recovered. One is an Orin NX report
  of ModelOpt INT8 running slower than FP16, matching our Orin measurement (16.8 vs 11.6 ms).
- Ignoring the validator, the labels agreed on 5 of 6. The six come from five distinct sources, and the reference
  labels were written by us, not by an independent expert.
- Three of those answers were rejected for numbers in their explanations.
  - That number check is weak: swapped or unit-attached values can pass it.
  - So the report never shows model-written numbers. It shows only verbatim quotes, which are strictly checked,
    and our own facts.
- This is an assistant for reviewing field reports, at an early stage.
  ([§9](docs/errata_grounding_preregistration.md))

**Deployment preflight.** [`scripts/deploy_preflight.py`](scripts/deploy_preflight.py) checks a candidate card in order:
the engine hash, the runner's normalization guard, the runner's 200 ms chunk deadline and the code-decided verdict.
A fault-injection demo ([`preflight_demo.json`](artifacts/reports/preflight_demo.json)) shows the nominal FP16 card on
HOLD and five broken cases blocked.

**Tool feedback.** Every problem we hit with TensorRT, Model Optimizer, Nebius AI Cloud and Token Factory is logged
with its cause and a suggested fix in [`docs/tool_feedback.md`](docs/tool_feedback.md).

**Where Managed MLflow helped.** The same results, as standard tracked runs: code-decided verdicts next to their
intervals, and the 25 grid cells comparable in one view. The cluster ran only for publishing and capture
(about $0.48/h), and the publish script refills it from the repository at any time.

![MLflow: deployment verdicts](docs/media/mlflow/deployment_verdicts.png)

## Pipeline

```
SO-101 teleop demos (120) ──► LOCK-1 split 80/20/20 ──► Nebius Jobs: ACT training (FP32, single checkpoint)
                                                                   │
                       modelopt INT8 × 24 calibration variants + FP16 ◄┘
                                                                   │
                      Jetson Orin TensorRT engines (frozen timing cache)
                                                                   │
 offline audit: 5 predictors on 2,000 held-out states (Nebius Jobs) ──► LOCK-2 freeze (rankings hashed)
                                                                   │
 245 blinded, interleaved real-arm trials + Cosmos-Reason2 shadow supervisor ──► LOCK-3 ──► unseal, analyze
                                                                   │
 Nemotron 3 Super deployment report (code decides, model explains)  ·  stress tests (stop rules; see caveats)
```

## Research integrity

The hypotheses, endpoints and analysis code were fixed and hashed **before** any real-arm trial.

- [`docs/preregistration.md`](docs/preregistration.md): hypotheses, endpoints and kill conditions.
- [`docs/decision_log.md`](docs/decision_log.md): every decision, amendment and deviation, append-only.
- [`docs/success_criterion.md`](docs/success_criterion.md): the success rule, locked before the first trial.
- [`docs/aep_physical_registration_v1.md`](docs/aep_physical_registration_v1.md): tolerance-based decisions
  (E1 10 pp, E2 5 px).
- [`docs/stress_test_protocol.md`](docs/stress_test_protocol.md) and
  [`docs/fp16_real_arm_preregistration.md`](docs/fp16_real_arm_preregistration.md): follow-up protocols, each locked
  before its first trial.
- [`artifacts/freeze/`](artifacts/freeze/): the `LOCK-2`, `LOCK-3` and post-run hash records.
- [`docs/sessions/`](docs/sessions/): operator observations, which contain no cell information.
- [`docs/related_work.md`](docs/related_work.md): closest prior work and how this project is positioned.

## Data

- [`chans/quantgate-so101-coaster`](https://huggingface.co/datasets/chans/quantgate-so101-coaster): 120 teleoperated
  demos with the LOCK-1 split manifest (train 80 / val 20 / audit 20) and file hashes.
- [`chans/quantgate-so101-coaster-positions`](https://huggingface.co/datasets/chans/quantgate-so101-coaster-positions):
  50 demos at start offsets −4…+4 cm. The +3 cm position is held out.

Both are LeRobot v3.0 datasets under CC BY 4.0.

## Hardware

- SO-101 leader and follower arms (Feetech STS3215).
- Jetson Orin Nano Super 8 GB: robot host, JetPack R36, TensorRT 10.3, nvpmodel 15 W.
- Logitech C922 overhead camera (640×480, locked exposure and white balance) and OpenMV AE3 wrist camera (320×200).
- Task: pick an unopened 268 g cola can from a marked start spot and stand it on a fixed coaster.
- Setup notes: [`docs/bimanual_setup.md`](docs/bimanual_setup.md), used in the single-arm configuration.

## Setup and reproduction

### 0. Analysis only (no robot, no GPU)

Every reported number can be recomputed from the committed sealed logs:

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest -q                                   # 187 tests
python tests/runner_abort_harness.py                            # runner abort/timeout/manifest harness
.venv/bin/python -m edgeqgate.grid                              # 26-cell grid and hash
.venv/bin/python scripts/g6_analysis.py --sealed-dir artifacts/trials/g6_unsealed --out /tmp/g6.json
.venv/bin/python scripts/g6_supplement.py --sealed-dir artifacts/trials/g6_unsealed \
    --report /tmp/g6.json --out /tmp/g6_sup.json
sha256sum artifacts/trials/g6_unsealed/*.jsonl                   # compare with artifacts/freeze/lock3.json
```

### 1. Credentials

No credential is stored in the repository. Put them in `~/.config/edgeqgate/env` (mode 600). The template is
[`.env.example`](.env.example). It needs `NEBIUS_API_KEY` for Token Factory and `TAVILY_API_KEY`. S3 credentials and
the Cosmos endpoint token are separate files in the same directory.

```bash
.venv/bin/python scripts/check_credentials.py   # reports presence only, never values
```

### 2. GPU workstation: export and quantize

torch, ONNX and TensorRT run in NGC containers ([`Dockerfile`](Dockerfile), [`Dockerfile.lerobot`](Dockerfile.lerobot)):

```bash
docker build -t edgeqgate:25.11 . && docker build -f Dockerfile.lerobot -t edgeqgate-lerobot:25.11 .
# inside edgeqgate-lerobot:25.11
python scripts/export_trained_act.py <ckpt_dir> <dataset_root> <out.onnx>
python scripts/build_grid_lerobot.py <demos> <ckpt>/pretrained_model <out_dir>    # modelopt INT8 x 24 + FP16
python scripts/g4_prepare_states.py <demos> <ckpt>/pretrained_model <g4_dir>     # audit states
```

### 3. Nebius

```bash
# ACT training on Nebius Jobs (L40S); env: CALIB, DS, OUT, STEPS, BATCH, SEED
scripts/job/train_act.sh
# audit fan-out on Nebius Jobs (one job per cell): scripts/job/audit_job_g4.py
# Cosmos-Reason2 endpoint (weights from Object Storage, token auth); stop it between sessions
AWS_CONFIG_FILE=<config with endpoint_url and region> scripts/d4_cosmos_endpoint.sh
```

### 4. Jetson Orin: engines and real-arm trials

```bash
scripts/build_engines_orin.sh <onnx_dir> <out_dir>          # trtexec, frozen timing cache, one place for flags
python scripts/g4_lock2.py <g4_dir>                        # LOCK-2: freeze rankings before any trial
python scripts/g6_schedule.py <out_dir>                    # sealed, interleaved schedule
# per session: light, wrist and coaster checks, then
python scripts/so101_trial.py --blind main                 # operator sees trial numbers only
```

The runner starts a TensorRT policy server (`scripts/trt_policy_server.py`, system Python 3.10 with TensorRT) and
drives the arm at 30 Hz. It uses chunk prefetch and blending, so FP32 and INT8 cells have identical timing. The
OpenMV wrist camera needs the plugin in [`plugins/lerobot_camera_openmv`](plugins/lerobot_camera_openmv).

### 5. Reports

```bash
set -a; . ~/.config/edgeqgate/env; set +a
.venv/bin/python scripts/d3_final_report.py        # Nemotron 3 Super, numbers verified against evidence
.venv/bin/python scripts/d5_errata_collector.py    # Tavily errata snapshot (hashed)
```

## Repository layout

```
src/edgeqgate/   grid, splits and guards, audit buffer, scores, arms, calibration, freeze, supervisor, hashing
scripts/         data, training, quantization, audit, real-arm runner, analyses, reports
plugins/         LeRobot camera plugin for the OpenMV AE3
artifacts/       manifests, freeze records, unsealed trial logs, reports
dashboard/       audit_gate.html (D7)
docs/            pre-registration, decision log, protocols, session notes, related work
tests/           187 unit tests, plus the hardware-free runner harness
```

## Positive control

A deliberately miscalibrated INT8 build, PC-B (calibrated on black frames), was flagged offline. It was caught by a
simple input check, by action MSE and by both audit scores, far outside the 24 normal cells. On the arm, blinded and
interleaved, it went **11/12 against FP32 10/12**. Placement was within tolerance (+1.11 px, CI [−0.74, +3.08]); the
success comparison is insufficient evidence. The offline warning was **not confirmed** in 12 trials, which is read as
unresolved, not as "tolerated" ([`positive_control_analysis.json`](artifacts/reports/positive_control_analysis.json)).
Such builds are still rejected at the input check.

## Portability: does the INT8 verdict transfer to another accelerator?

An offline probe, pre-registered before any quantized output ([`docs/hailo_portability_probe.md`](docs/hailo_portability_probe.md)).
- **Setup**: the same checkpoint and the same calibration frames, deployed on a Raspberry Pi 5 with a Hailo-8.
- **Split**: only the two ResNet backbones compile for Hailo. The transformer runs in FP32 on the Pi CPU.
- **Toolchain**: Hailo DFC 3.34 on a GPU workstation. The error is measured on the Hailo-8 itself.

| Calibration frames | Orin TensorRT INT8 (whole graph) | Hailo-8 device (backbones INT8) |
|---|---|---|
| 16 | 0.054 | 0.048 |
| 1024 | 0.062 | 0.035 |

Error is the mean action error against FP32 on the 2,000 audit states, in normalised units.

- **The calibration-size effect reverses between targets.** A plausible cause, not tested: the Hailo compiler uses
  the frames for quantization-aware fine-tuning, while TensorRT uses them only for activation ranges.
- **The vendor emulator differs from the device** by about half the quantization error (0.020–0.026).
- **Latency on the Pi 5 is 239 ms (p95 264 ms).** The Hailo backbones take 13 ms; the CPU transformer takes the rest. That is over the runner's 200 ms chunk deadline: a new chunk must arrive before blending starts, 6 steps after the request at 30 Hz. The measured median and p95 both exceed that deadline. The arm was not run on this target.
- **Scope**: Hailo quantizes less of the graph, so this is not a claim that it quantizes better. No real-arm result
  follows from it.
- A verdict belongs to a deployment target, not to the label "INT8".

## Next steps

- **On-policy audit**: score candidates on the states the deployed engine visits (385 logged rollouts with both camera
  videos), labelled offline by the FP32 teacher, instead of on demonstration states.
- **On-policy distillation**: quantization-aware fine-tuning on those states (DAgger with FP32 as the expert), to try to
  recover a broken build such as PC-B. It closes the student-teacher gap only; weaknesses the teacher shares, such as
  the start-position shift, need new demonstrations.
- A sealed real-arm block on the Hailo-8 target (FP32 vs Hailo, 12 vs 12), pre-registered separately.
- After the position fine-tune (done, item 5):
  - settle its nominal performance at the training mark (10/12 vs 12/12, undecided);
  - test more positions and objects;
  - check the post hoc observation that INT8 roughly doubles gripper chatter at a similar success rate, as its own
    pre-registered block.

## Limitations

- One task, one checkpoint, one robot, one TensorRT build. The Hailo-8 portability result is offline only.
- The precision results are near the success ceiling.
- The gripper and distribution-shift results are observational. They come from separate sessions, not randomized
  against each other.
- The stress S1 block stopped after 3 trials.
- FP16 was tested on the real arm in one block (19/20 against FP32 10/10); the success comparison is still insufficient evidence.
- Integrity caveats: the main study (G6) was pre-registered and blinded end to end. In the follow-ups the operator stayed blind to cells throughout, but some rules were set after aggregate outcomes were seen and before cells were unsealed: the stress re-judge rules (§9, §11) and the stress v2 design after v1 stopped. S1 was stopped early by the user after 3 trials. All are logged.
