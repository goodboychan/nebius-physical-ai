<p align="center"><img src="docs/assets/quantgate_logo.png" alt="QuantGate" width="420"></p>

# QuantGate

**Evidence before deployment.** QuantGate helps robot developers decide which precision of a policy to ship on an
edge device. It shows the engine's measured cost, its real-arm behavior and how strong the evidence is.

> QuantGate screens INT8 robot policies offline on Nebius and gates which ones reach a Jetson-powered SO-101 arm.
> Cosmos-Reason2 watched the real runs (215 live, 245 retrospectively) and Nemotron writes the deployment report. The whole real-arm study was
> pre-registered, operator-blinded and hash-sealed.

**License: [Apache 2.0](LICENSE)** · Nebius × NVIDIA Global AI Hackathon, Physical AI track · internal code name
`edgeqgate`

The logo's Q stands for QuantGate and quantization. The open passage at the lower right is the gate, and the small
square leaving it is the one INT8 policy that passed.

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
     start spot. Position changes need more validation; the cause was not isolated.
   - An unseen yellow can: 48/48, all four engines 12/12. Placement was within the 5 px tolerance of FP32 for every
     INT8 cell ([`stress_v2_analysis.json`](artifacts/reports/stress_v2_analysis.json)).
   - Source: [`stress_operator_notes.md`](docs/sessions/stress_operator_notes.md).
4. **The AI judge needs validation before use.**
   - Shown the final frame of all 245 trials, Cosmos-Reason2 answered "Yes" every time and caught 0 of 7 failures.
   - Source: [`d4_retro_judge_g6.json`](artifacts/reports/d4_retro_judge_g6.json).

Stress tests were unsealed on 2026-10-13. The stress protocol is
[`docs/stress_test_protocol.md`](docs/stress_test_protocol.md).

## How QuantGate uses NVIDIA models and Nebius

| Component | What runs | Where |
|---|---|---|
| Deployment target | LeRobot ACT policy (51.6M) as **TensorRT** FP32 / FP16 / INT8 engines | **Jetson Orin Nano Super** (TensorRT 10.3) next to a real SO-101 arm |
| Quantization | NVIDIA **TensorRT Model Optimizer** (modelopt) INT8 Q/DQ, 24 calibration variants | NGC PyTorch 25.11 container, local GPU |
| `D4` runtime supervisor | **`nvidia/Cosmos-Reason2-2B`** watches the overhead camera at 2 Hz (CONTINUE / FALLBACK / ABORT, shadow mode) and is asked at trial end whether the task succeeded | **Nebius AI Endpoint** (L40S, vLLM 0.29), about 330 ms round trip from the robot |
| `D3` deployment report agent | **`nvidia/nemotron-3-super-120b-a12b`** writes go / no-go reports from frozen evidence; every number is machine-checked | **Nebius Token Factory** |
| `D5` errata collector | **Tavily** search for TensorRT / Jetson / INT8 known issues, with queries derived from the real build environment and snapshot-hashed | Tavily API |
| Policy training | LeRobot 0.6.1 ACT, 100k steps | **Nebius Jobs** (L40S, 1 h 57 min) |
| Audit fan-out | 25 cells × bootstrap scoring on 2,000 held-out states | **Nebius Jobs** (CPU) |
| Data and weights | demos, checkpoints, Cosmos weights | **Nebius Object Storage** (S3) |

**Where Token Factory helped.** The report agent needs a large reasoning model for about a minute per report. Token
Factory served Nemotron 3 Super, and the variants we compared, behind one OpenAI-compatible API, so no GPU server had
to stay warm. Comparison: [`d3_model_compare.json`](artifacts/reports/d3_model_compare.json). Final report:
[`d3_final_report.md`](artifacts/reports/d3_final_report.md).

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
 Nemotron 3 Super deployment report (numbers verified)  ·  stress tests (pre-registered stop rules)
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
.venv/bin/python -m pytest -q                                   # 167 tests
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
tests/           167 unit tests
```

## Limitations

- One task, one checkpoint, one robot, one TensorRT build.
- The precision results are near the success ceiling.
- The gripper and distribution-shift results are observational. They come from separate sessions, not randomized
  against each other.
- The stress S1 block stopped after 3 trials.
- FP16 has no real-arm evidence yet.
