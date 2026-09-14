# `G0` TRT INT8 경로 — 통과 기준 충족, §4.3 툴체인 확인 3건

## Scope

`G0`(§10.2)의 최대 리스크 항목인 **ACT 그래프의 TRT INT8 빌드**와, §4.3이 요구한
**캘리브레이션 동작의 소스/API 레벨 직접 확인**만 다룬다.

**하지 않은 것**: 공개 SO-101 데이터셋 미사용, ACT 실제 학습 없음, 실기 없음,
Nebius Jobs 더미 팬아웃 없음, Token Factory·Endpoint·Tavily 호출 없음, Jetson Orin 빌드 없음.
`G0`의 나머지 산출물은 미완이다.

가중치와 캘리브레이션 데이터가 **모두 무작위**다. `K4`가 묻는 것은 "ACT export에서 TRT INT8
빌드가 실패하는가"이고 그것은 가중치가 아니라 그래프의 성질이므로, 그래프 위상만 충실하게
재현하고 값은 무작위로 두었다. 이 시도는 정책에 대해 아무것도 말하지 않는다.

## 환경

| 항목 | 값 |
|---|---|
| 호스트 | GB10 (aarch64), driver 580.173.02 |
| 컨테이너 | `nvcr.io/nvidia/pytorch:25.11-py3` |
| TensorRT | 10.14.1.48 |
| torch | 2.10.0a0 / CUDA 13.0 / compute capability (12, 1) |
| modelopt | 0.37.0 |
| 모델 | ACT 추론 위상, 78.0M 파라미터, 2카메라 480x640, chunk 100, 출력 (1, 100, 6) |

## §4.3 확인 결과 — 문서가 아니라 API를 찍어서 확인한 것

### (1) `IInt8Calibrator`가 TRT 10.1에서 deprecated

`trt.IInt8Calibrator.__doc__` 원문: *"[DEPRECATED] Deprecated in TensorRT 10.1.
Superseded by explicit quantization."*

`IInt8EntropyCalibrator2` 등 구현체와 `IBuilderConfig.int8_calibrator`는 아직 존재하지만
경로 전체가 deprecated다. 사전등록 §4.1의 `calib_size`/`calib_composition` 축은 암묵적으로
이 경로를 전제하고 있었다.

### (2) `granularity` 축은 캘리브레이터 경로에서 제어 불가

per-channel 제어 지점은 `IQuantizeLayer.axis`인데, 이는 explicit Q/DQ 경로에만 존재한다.
캘리브레이터 경로에는 activation 스케일을 per-channel로 만드는 API가 없다.

**따라서 §4.1의 3축 설계는 단일 경로에서 실현되지 않는다.** 캘리브레이터 경로를 고수하면
`granularity` 축이 죽고, explicit 경로로 가면 3축이 모두 산다. explicit 경로를 택했다.

이때 **캘리브레이션의 제어 지점이 TRT 빌더에서 PyTorch(modelopt)로 이동**한다.
§4.2의 "TRT 빌드 옵션은 셀 간 동일하게 고정"은 그대로 유효하지만, `calib_size`와
`calib_composition`은 이제 TRT가 아니라 modelopt의 forward loop이 결정한다.

### (3) fused MHA fast path가 양자화기를 조용히 무력화한다

첫 실행이 `AssertionError: Quantizer has not been calibrated`로 실패했다.

원인: PyTorch의 fused multi-head attention fast path가 `nn.MultiheadAttention`의
`out_proj`를 모듈로 호출하지 않고 융합 커널로 처리한다. modelopt가 모듈 단위로 삽입한
양자화기가 캘리브레이션 데이터를 한 번도 보지 못해 amax가 비고, ONNX export가 거기서 실패한다.

조치: `torch.backends.mha.set_fastpath_enabled(False)` + `TransformerEncoder(enable_nested_tensor=False)`.

이건 어텐션 기반 정책을 modelopt로 양자화할 때 **조용히 터지는 지점**이다. 에러 메시지가
fast path를 가리키지 않아 원인 추적에 시간이 든다. `D8`(도구 피드백) 후보로 기록한다.

## 관측

### `G0` 통과 기준

| 빌드 | 결과 | 시간 |
|---|---|---|
| FP16 (기준) | `PASSED` | 13.7s |
| INT8 per-channel | `PASSED` | 17.3s |
| INT8 per-tensor | `PASSED` | 27.3s |

**§10.2 `G0` 통과 기준("TRT INT8 빌드가 한 번이라도 성공") 충족.**
Q/DQ 노드는 양쪽 모두 QuantizeLinear 134 / DequantizeLinear 134.

### `granularity` 축이 실제로 다른 양자화를 만드는가

Q/DQ 노드 **수가 같다는 것만으로는 축이 실재한다고 말할 수 없다.** 스케일 텐서의 모양을 확인했다.

| 설정 | 벡터(per-axis) 스케일 | 스칼라 스케일 |
|---|---|---|
| per-channel | **66** (512, 3200, 64, 128, 256 — 레이어 출력 채널 수와 일치) | 68 |
| per-tensor | **0** | 134 |

축은 이름뿐이 아니라 실제로 다른 양자화를 만든다. §4.1의 `granularity` 축은 유효하다.

## Verification

- 위 빌드는 전부 `--skipInference`다. **엔진이 빌드된다는 것만 확인했고 수치 정확도는 보지 않았다.**
  INT8 출력이 FP32와 얼마나 다른지는 측정하지 않았다
- 엔진은 sm_121(GB10)용이다. **배포 대상인 Jetson Orin Nano(sm_87)에서의 빌드는 검증되지 않았다.**
  TRT 엔진은 아키텍처 고정이므로 이 엔진은 Orin에서 동작하지 않는다. §2.2가 GX10에 배정한
  역할이 "export·빌드 리허설"이므로 범위 내이지만, `G3`의 Orin 빌드는 여전히 미검증 리스크다
- `uncalibrated_quantizers: 201`은 대부분 modelopt가 기본 비활성화하는 output/input quantizer이며
  정상이다. 진단 코드가 활성/비활성을 구분하지 않아 과다 계수한다 — 다음 시도에서 고칠 것
- pytest 스위트는 여전히 없다

## 주장하지 않는 것

- 무작위 가중치·무작위 캘리브레이션 데이터이므로, **양자화 품질·정책 성능·수치 정확도에 대해
  아무것도 주장하지 않는다.** 그래프가 툴체인을 통과한다는 것만 보였다
- `K4`가 해소되었다고 말하지 않는다. `K4`의 판정 시점은 `G3` 종료이고, 판정 대상은
  **실제 학습된 ACT 체크포인트의 Orin 빌드**다. 이 시도가 낮춘 것은 그 리스크의 일부다
- per-channel/per-tensor 엔진의 빌드 시간 차이(17.3s vs 27.3s)는 1회 측정이며
  성능 주장이 아니다
