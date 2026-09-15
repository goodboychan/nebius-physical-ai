# 엣지 양자화 정책 배포 게이트

**License: [Apache 2.0](LICENSE)**

엣지 NPU로 내려보낼 로봇 조작 정책의 INT8 변형들을, **실기 실행 없이 오프라인에서만**
심사하여 배포 불가 변형을 사전에 걸러낼 수 있는가.

Nebius x NVIDIA Global AI Hackathon, Physical AI Track 출품작.

> **문서 상태**: 진행 중. 데이터 수집 전, 실기 시행 전.
> 이 저장소의 어떤 수치도 아직 실기 관측이 아니다.

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
| `G0` 드라이런 | TRT INT8 빌드 통과. Jobs/Endpoint 측정 진행 중 |
| `G1` 데이터 수집 | 미착수 — 로봇 팔 대기 |
| 이후 | 미착수 |

자세한 내용은 [`docs/progress/`](docs/progress/)의 최신 노트 참조.
