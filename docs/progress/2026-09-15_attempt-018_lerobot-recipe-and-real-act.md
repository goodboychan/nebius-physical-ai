# Nebius LeRobot 레시피 확인, 진짜 ACT의 export 경로 검증

## Scope

Nebius `serverless-ai-cookbook`의 `robotics/lerobot-finetune-job` 레시피가 쓸 만한지,
그리고 **LeRobot의 실제 ACT**가 우리 export·양자화·빌드 경로를 통과하는지 확인했다.

**하지 않은 것**: 실기 없음, 실제 학습 없음(무작위 초기화 ACT로 경로만 검증),
S3 체크포인트 왕복 미검증, Orin 빌드 미수행, 수치 정확도 미측정.

## 왜 이걸 보는가

`scripts/act_model.py`는 **내가 위상만 맞춰 손으로 만든 근사**다. `K4`(그래프/툴체인 리스크)
검증에는 충분했지만 본 실험의 정책으로는 약하다. §9.1이 ACT를 택했다는 것은 **그 ACT**를
뜻하고, 감사가 재는 것은 "배포되는 정책의 양자화 영향"이므로 정책이 진짜가 아니면
다른 것을 재게 된다.

## (a) 레시피는 쓸 수 있다

`cr.eu-north1.nebius.cloud/e00gw2b7v3pxetvpy7/lerobot-finetune:v0.1.0`

익명 매니페스트 조회는 401이지만, **우리 프로젝트의 잡에서는 추가 인증 없이 pull된다.**
짧은 잡으로 확인했다 (`COMPLETED`).

```
lerobot 0.5.1
torch 2.10.0+cu126
```

레시피가 제공하는 것: 데이터셋 다운로드 → ACT/Diffusion 학습 → S3 체크포인트 저장.
`--args "--policy act --dataset <ds> --steps N"`으로 제어한다.
§2.2가 "Nebius AI Cloud — ACT 학습"에 배정한 것과 정확히 일치한다.

### 레시피를 그대로 쓰면 안 되는 지점 둘

1. **퀵스타트가 `gpu-h100-sxm`($3.85/h)이다.** 아래쪽 예제의 `gpu-l40s-a`($1.55/h)를 써야 한다.
   `docs/tool_feedback.md` 4번에 적은 함정이 레시피 예제에도 있다
2. **`--preemptible`을 학습에 쓰면 안 된다.** 레시피 예제는 비용 절감으로 켜두지만,
   `IG-3`가 "모든 셀은 단일 FP32 체크포인트 하나에서 파생"을 요구한다. 중단 후 재실행으로
   체크포인트가 달라지면 그리드 전체의 전제가 깨진다.
   감사 팬아웃(CPU)에는 켜도 되고 학습에는 안 된다

## (b) LeRobot ACT의 export 경로 — 전 구간 통과

| 단계 | 결과 |
|---|---|
| `ACTPolicy` 생성 | **51.6M 파라미터**, chunk 100 |
| forward | `(1, 100, 6)` |
| ONNX export | **성공** 138 MB (2s) |
| modelopt INT8 캘리브레이션 | 성공 |
| Q/DQ 노드 | QuantizeLinear 112 |
| TRT FP16 빌드 | **성공** 47s, 엔진 74 MB |
| **TRT INT8 빌드** | **성공** 57s |

### 걸린 지점 셋 (전부 문서화되지 않은 것들)

**1. PyAV 버전.** LeRobot 0.6.1은 `av`를 하드 의존으로 선언하지 않으면서 import한다.
PyAV ≥ 14에서는 `av.option`이 속성으로 노출되지 않아 `AttributeError`로 깨진다.
`av==13.1.0`이 필요하다. 내 기존 이미지가 18.1.0이라 pip이 교체하지 않았고,
원인을 찾는 데 시간이 들었다.

**2. 배치 키 형식.** 카메라를 `observation.images.up` 같은 개별 키가 아니라
**`observation.images` 하나에 리스트**로 넣어야 한다
(`modeling_act.py`: `batch[OBS_IMAGES][0].shape[0]`). 개별 키로 넣으면
`KeyError: 'observation.environment_state'`가 나는데, 이 메시지는 원인을 가리키지 않는다.

**3. CPU에서 export해야 한다.** CUDA에 올린 채 `torch.onnx.export`를 부르면
constant folding이 실패한다.

```
RuntimeError: Expected all tensors to be on the same device,
but found at least two devices, cuda:0 and cpu!
  at _jit_pass_onnx_constant_fold
```

LeRobot ACT의 사인파 위치 임베딩이 CPU에서 만들어지는 것으로 보인다.
export는 GPU가 필요 없으므로 CPU로 옮기면 해소된다.

`torch.backends.mha.set_fastpath_enabled(False)`(attempt-003 발견)는 여기서도 필요하다.

## 전환하면 무엇이 달라지는가

| | 손으로 만든 `act_model.py` | LeRobot ACT |
|---|---|---|
| 파라미터 | 78.0 M | **51.6 M** |
| FP16 엔진 (GB10) | 158 MB | **74 MB** |
| Q/DQ 노드 | 134 | **112** |

**모델이 실질적으로 다르다.** 따라서 전환은 `G0`의 export 검증과 26셀 빌드를 다시
돌려야 하는 작업이다. 지금까지의 지연·크기 실측값은 전부 손으로 만든 모델의 것이며,
전환하면 다시 재야 한다.

**다만 지금이 바꾸기 가장 싼 시점이다.** 데이터 수집 전이고 `LOCK-2` 동결 전이므로
사전등록 위반 없이 교체할 수 있다. `G1` 이후에 발견했으면 훨씬 비쌌다.

## 버전 스큐

레시피 이미지는 **lerobot 0.5.1**, 내가 로컬에서 검증한 것은 **0.6.1**이다.
체크포인트 형식과 API가 다를 수 있다. 레시피로 학습한 체크포인트를 우리 export 경로에
넣으려면 **같은 버전으로 맞춰야 한다.** 미확인 사항이다.

## Verification

- 무작위 초기화 ACT로 **경로만** 검증했다. 학습된 체크포인트로는 하지 않았다
- **Orin(sm_87) 빌드를 하지 않았다.** GB10에서만 빌드했다
- S3 체크포인트 저장·회수를 검증하지 않았다 (접근 키 미발급, `manual_actions.md` #1)
- "미캘리브레이션 양자화기 42개"를 보고했으나, attempt-009에서 이 진단이 비활성 양자화기를
  과다 계수한다는 것을 확인했다. **이 수치는 신뢰하지 않는다**
- 레시피의 실제 학습을 돌리지 않았다. 이미지가 pull되고 lerobot이 import된다는 것까지다

## 주장하지 않는 것

- LeRobot ACT로 전환해야 한다고 결정하지 않는다. 전환 가능성과 비용을 측정했을 뿐이며,
  정책 교체는 §9.1에 걸린 사안이므로 사람이 결정한다
- 레시피로 학습한 체크포인트가 우리 경로를 통과한다고 말하지 않는다. 버전 스큐가 미확인이다
- 51.6M vs 78M 차이가 실기 성능 차이를 뜻한다고 말하지 않는다
