# attempt-029 — `G3` 26셀 빌드 (LeRobot ACT, 동결 timing cache)

## Scope

G2 기준 체크포인트(100k, `bb5e1850…`) 하나에서 INT8 24셀 + FP16 `VC-025`를 만들고 Orin에서 엔진으로 빌드했다.
`VC-000`은 엔진이 아니라 GX10 FP32 torch 레퍼런스다(실기용 Orin FP32 엔진은 G2에서 따로 만들었다).

**하지 않은 것**: 감사 점수 없음, 실기 없음, Orin 25W 모드 재측정 없음(15W 그대로).

## 1단계 — ONNX (GX10, `scripts/build_grid_lerobot.py`)

- NVIDIA TensorRT Model Optimizer(modelopt) `INT8_DEFAULT_CFG`, per-tensor는 모든 양자화기의 axis를 None으로
- 캘리브레이션: `edgeqgate.calibration`이 LOCK-1 train에서 고른다. 시드에 셀 코드 없음, 크기는 중첩 표본(2026-10-07 결정).
  granularity만 다른 두 셀은 같은 프레임(예: VC-001·VC-002 `calib_frames_hash 32ae383f…`)
- 25셀 모두 Q/DQ 112개(INT8), `VC-025` ONNX는 FP32 레퍼런스 ONNX와 해시가 같다(`a78ebec2…`)
- 시험: VC-001/002의 QDQ ONNX(onnxruntime CPU)와 FP32 torch의 상대 L2 = per-tensor 5.6%, per-channel 2.9% (train 프레임 1개)

## 2단계 — 엔진 (Orin, `scripts/build_engines_orin.sh`)

| 항목 | 값 |
|---|---|
| 플래그(셀 간 고정, §4.2) | `--memPoolSize=workspace:4096 --builderOptimizationLevel=3 --skipInference` + INT8 `--int8 --fp16` / FP16 `--fp16` |
| 동결 캐시 | 워밍업(그리드 무관 시드로 만든 per-tensor·per-channel QDQ + FP32 ONNX의 FP16 빌드) → `67fca693…`, 444 |
| 결과 | **25/25 성공** (G3 기준 20 통과). INT8 빌드 188–256초(per-tensor 약 254초, per-channel 약 190초), FP16 162초 |
| 엔진 크기 | 평균 57.7MB |
| 환경 | TensorRT 10.3.0, 15W 모드 |

## 결정성

같은 ONNX(VC-001)를 같은 동결 캐시 복사본으로 두 번 빌드하면 **엔진 파일 해시는 다르지만**(`bf7672…` / `bd2fa30b…`)
train 2,000상태의 출력은 **비트 단위로 같다**(max abs diff 0.0). 9월 attempt-025의 관찰(동결 캐시 → 출력 동일)이 실제 모델에서도
맞다. 따라서 `build.jsonl`의 엔진 해시는 빌드를 식별하지만 동일성 판정에는 쓰지 않는다 — 출력으로 판정한다.

## 관찰 — INT8이 FP16보다 느리다

같은 결정성 시험에서 VC-001(INT8 per-tensor) GPU 시간 중앙값 32.6ms / 31.8ms. G2 시험 모델의 FP16 엔진은 11.6ms였다.
이 모델·이 플래그·15W에서는 INT8이 FP16보다 약 2.7배 느리다. 원인은 재지 않았다(Q/DQ 사이 reformat, attention 경로 추정).
`score_cheap_C`(지연)와 `EX-2`에 그대로 반영된다. 같은 엔진을 두 번 잰 값도 0.8ms 다르므로 지연은 잡음이 크다.

## 주장하지 않는 것

- 엔진 출력의 정확도·태스크 성능에 대해서는 아무것도 주장하지 않는다(G4·G6에서)
- INT8이 느린 원인을 알지 못한다
