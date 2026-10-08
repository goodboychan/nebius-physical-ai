<p align="center"><img src="docs/assets/quantgate_logo.png" alt="QuantGate" width="420"></p>

# QuantGate

**Audit quantized robot policies before they touch the robot.**

> QuantGate screens INT8 robot policies offline on Nebius, gating which ones reach a Jetson-powered arm. Cosmos-Reason2 watches every real run.

**License: [Apache 2.0](LICENSE)**

(내부 코드명 `edgeqgate` — 엣지 양자화 정책 배포 게이트)

로고: Q 모양은 QuantGate와 양자화(Quantization)를 함께 나타낸다. 오른쪽 아래의 열린 통로는 선별된 정책이 실제 로봇으로
넘어가는 게이트이고, 통로 밖의 작은 사각형은 검증을 통과해 배포되는 INT8 정책 하나다.

엣지 NPU로 내려보낼 로봇 조작 정책의 INT8 변형들을, **실기 실행 없이 오프라인에서만**
심사하여 배포 불가 변형을 사전에 걸러낼 수 있는가.

Nebius x NVIDIA Global AI Hackathon, Physical AI Track 출품작.

> **문서 상태**: 진행 중 (2026-10-07). 데모 120개 수집과 분할 확정(`LOCK-1`), FP32 정책 학습 완료. 실기 trial 전.
> 이 저장소의 어떤 수치도 아직 정책의 실기 성공률이 아니다.

## 이 프로젝트의 차별점 — 사전등록

실험을 **시작하기 전에** 가설·엔드포인트·분석 방법을 문서로 고정하고 해시를 커밋한다.
결과를 본 뒤에 분석을 고르는 경로를 구조적으로 차단한다.

- [`docs/preregistration.md`](docs/preregistration.md) — 사전등록 문서 (가설, 엔드포인트, 킬 조건)
- [`docs/decision_log.md`](docs/decision_log.md) — 모든 결정과 개정. **원 계획을 덮어쓰지 않는다**
- [`docs/progress/`](docs/progress/) — 시도별 기록. 각 노트에 "주장하지 않는 것" 섹션 필수
- [`docs/success_criterion.md`](docs/success_criterion.md) — 성공 판정 규칙 (실기 전 잠금)
- [`docs/manual_actions.md`](docs/manual_actions.md) — **사람이 해야 하는 항목** (결정·자격증명·물리 작업)
- [`docs/tool_feedback.md`](docs/tool_feedback.md) — 도구 피드백 (`D8`)
- [`docs/cost_model.md`](docs/cost_model.md) — 공식 단가 기반 비용 모델

핵심 잠금은 `LOCK-2`다: **감사 점수를 전량 산출·동결·해시 커밋한 뒤에야 최초 실기 trial을
실행한다.** 이 순서가 깨지면 연구 전체의 신뢰성이 사라진다.

## Why this matters

Quantizing a robot policy for an edge device usually leaves open-loop metrics looking fine, yet the closed-loop
behaviour can change. Checking every quantized variant on the real robot is slow, costly and sometimes unsafe, so
QuantGate tries to screen variants **offline, before** they reach the robot, and tests that screen against
pre-registered real-arm trials.

The motivation is strongest in **precision-critical settings such as medical, lab-automation or pharmacy robotics**,
where a policy that only *barely* places an object inside the target is already a failure. That is why the audit scores
use tail statistics (CVaR@90) instead of averages, and why placement accuracy is recorded on every trial alongside
binary success.

Scope note: the experiment here is a cola can on a coaster. It makes **no claim** about medical or clinical use.
The runtime supervisor is also deliberately non-intervening when its verdict is stale, so that network delay cannot
contaminate the measured success rate. A safety-critical deployment would need the opposite default (stop when unsure).

## How QuantGate uses NVIDIA models and Nebius

| Component | What runs | Where |
|---|---|---|
| Deployment target | LeRobot ACT policy (51.6M) as **TensorRT** FP32 / FP16 / INT8 engines | **Jetson Orin Nano Super** next to a real SO-101 arm |
| `D4` runtime supervisor | **`nvidia/Cosmos-Reason2-2B`** — watches the overhead camera, answers CONTINUE / FALLBACK / ABORT | **Nebius AI Cloud endpoint** (L40S, vLLM 0.29). 328 ms median round trip from the robot |
| `D3` deployment report agent | **`nvidia/nemotron-3-super-120b-a12b`** — writes per-cell go / no-go reports from audit artifacts; every number is checked against the evidence | **Nebius Token Factory** |
| `D5` errata collector | **Tavily** search for TensorRT / Jetson / INT8 known issues, queries derived from the real build environment, snapshot-hashed | Tavily API at report time |
| Policy training | LeRobot 0.6.1 ACT, 100k steps | **Nebius Jobs** (L40S, 1h57m) |
| Audit fan-out | 25 cells × bootstrap scoring | **Nebius Jobs** |
| Data and weights | demos, checkpoints, Cosmos weights | **Nebius Object Storage** (S3) |
| Quantization | NVIDIA **TensorRT Model Optimizer** (modelopt) INT8 Q/DQ, 24 calibration variants | GX10 (local) |

Where Token Factory helped: the report agent needs a large reasoning model only for a minute per report. Token Factory gave us
Nemotron 3 Super (and Nano / Ultra for comparison) behind one OpenAI-compatible API, so there was no GPU server to keep warm for it.

## Pipeline

```
SO-101 teleop demos (120)  ──►  LOCK-1 split 80/20/20  ──►  Nebius Jobs: ACT training
        │                                                        │
        │                                       FP32 checkpoint (single source, IG-3)
        ▼                                                        ▼
  audit buffer (2,000 audit states)          modelopt INT8 × 24 calibration variants + FP16
        │                                                        │
        │                                Jetson Orin TensorRT engines (frozen timing cache)
        ▼                                                        ▼
  offline audit scores (5 predictors, Nebius Jobs) ──► LOCK-2 freeze ──► real-arm trials (blinded)
                                                                         + Cosmos-Reason2 supervisor
                                                                         + Nemotron deployment report
```

## Hardware

- SO-101 leader + follower arm, Feetech STS3215 servos
- Jetson Orin Nano Super (robot host, TensorRT 10.3, JetPack R36)
- Logitech C922 overhead camera (640×480, locked exposure / white balance), OpenMV AE3 wrist camera (320×200)
- Task: pick an unopened 268 g cola can from a marked start spot and stand it on a fixed coaster

Setup notes for the arm, cameras and lighting: [`docs/bimanual_setup.md`](docs/bimanual_setup.md) (single-arm configuration).

## 구조

```
src/edgeqgate/
  grid.py          변형 그리드 26셀 (§4) — yaml과 정준 생성기를 대조 검증
  splits.py        시드→SHA 분할 + 용도별 접근 가드 (IG-1, IG-2)
  audit_buffer.py  감사 상태 버퍼 2,000 + 결정적 부트스트랩 (§3.3)
  progress.py      진행도 회귀기 g(s,a), 해석적 기울기 (§5.1)
  scores.py        감사 점수 5종 (§5.1, §5.1b)
  arms.py          실기 arm 구성 + 커버리지 점검 (§7.1, IG-7)
  hashing.py       정준 해시 (플랫폼 간 재현 가능)
scripts/
  g0_export_build.py   ACT → ONNX → TRT INT8 빌드
  trt_calib_probe.py   TRT 캘리브레이션 동작을 API 레벨에서 직접 확인 (§4.3)
  g0_jobs_fanout.py    Nebius Jobs 동시성·큐 지연 측정
  check_credentials.py 자격증명 존재 확인 (값은 출력하지 않음)
```

## 설치

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m edgeqgate.grid          # 26셀 그리드와 해시 확인
```

torch/TensorRT 경로는 호스트에 설치하지 않는다. NGC 컨테이너에서 실행한다:

```bash
docker run --rm --gpus all --ipc=host \
  -v "$PWD/scripts:/w" -v "$PWD/artifacts/g0:/out" \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  python /w/g0_export_build.py --calib-size 64 --granularity per-channel
```

## 자격증명

값은 저장소에 두지 않는다. `~/.config/edgeqgate/env` (권한 600)에 둔다.
템플릿은 [`.env.example`](.env.example) 참조.

```bash
.venv/bin/python scripts/check_credentials.py   # 존재 여부만 보고, 값은 출력하지 않음
```

## 현재 상태

| 게이트 | 상태 |
|---|---|
| `G0` 드라이런 | 완료 |
| `G1` 데모 120, `LOCK-1` | 완료 (2026-10-07) |
| `G2` 학습, FP32 기준선 | 학습 완료(Nebius Jobs). 실기 20 trial 대기 |
| `G3` 26셀 빌드 | 진행 중 (Orin, 동결 timing cache) |
| `G4` 감사 점수, `LOCK-2` | 입력 준비 완료 |
| `G6` 실기 | 미착수 |

자세한 내용은 [`docs/progress/`](docs/progress/)의 최신 노트 참조.
