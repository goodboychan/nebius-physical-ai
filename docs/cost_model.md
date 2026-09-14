# 비용 모델

측정일 2026-09-15. 출처는 **`nebius billing v1alpha1 calculator estimate`의 공식 응답**이며,
웹 검색이나 추정이 아니다. 리전은 eu-north1(GPU) / eu-west1(CPU) 기준.

> 재현: `nebius billing v1alpha1 calculator estimate --resource-spec-compute-instance-spec-parent-id <PROJECT> --resource-spec-compute-instance-spec-resources-platform <PLATFORM> --resource-spec-compute-instance-spec-resources-preset <PRESET> --format json`

## 두 크레딧은 섞이지 않는다

| | 범위 | 확인 방법 |
|---|---|---|
| **Token Factory** (`NEBIUS_API_KEY`) | `api.studio.nebius.com` 추론만 — `D3`, `D4`, `D5` | Cloud API 호출 시 `PermissionDenied` (attempt-006) |
| **Nebius Cloud** (브라우저 인증) | Jobs, Endpoint, GPU 학습 | — |

Token Factory 키로 Jobs를 돌릴 수 없고, 그 반대도 마찬가지다.
**예산을 두 통으로 따로 관리해야 한다.**

## 컴퓨트 단가

| 플랫폼 | preset | 시간당 | 비고 |
|---|---|---|---|
| `gpu-l40s-a` | 1gpu-8vcpu-32gb | **$1.55** | L40S Intel, 48GB. **최저가 GPU 진입점** |
| `gpu-l40s-d` | 1gpu-16vcpu-96gb | $1.82 | L40S AMD, 48GB |
| `gpu-h100-sxm` | 1gpu-16vcpu-200gb | **$3.85** | **`--platform` 기본값** |
| `gpu-h200-sxm` | 1gpu-16vcpu-200gb | $4.50 | |
| `cpu-d3` | 2vcpu-8gb | $0.0496 | 감사 팬아웃용 |

### 함정: `--platform`을 생략하면 H100이다

`nebius ai job create`의 `--platform` 기본값이 eu-north1에서 `gpu-h100-sxm`이다.
명시하지 않으면 **L40S 대비 2.5배**를 지불한다. 학습 10시간 기준 $15.48 vs $38.50.

### 리전 제약이 비용 구조를 가른다

`compute.instance.gpu.l40s` 쿼터는 **eu-north1 전용**인데, 그 리전의
`compute.instance.non-gpu.vcpu` 쿼터는 **0**이다 (attempt-007).
따라서 GPU 학습(eu-north1)과 CPU 팬아웃(eu-west1 등)이 리전을 넘게 되고,
아티팩트 이동 비용·복잡도가 §5.3 설계에 얹힌다.

## Token Factory 소비 — `D4`가 지배적이지만 작다

실측(attempt-008 후속): `openbmb/MiniCPM-V-4_5`에 640×480 프레임 1장 =
**prompt 224토큰 + completion 3토큰**.

| 해상도 | 프레임당 prompt 토큰 |
|---|---|
| 640×480 | 224 |
| 320×240 | 92 |
| 160×120 | 92 |

§7.1의 실기 225 trial × 최대 60초 × 2Hz = **27,000 요청**:

| 해상도 | 총 토큰 | 단가 $0.06/1M | 단가 $1.00/1M |
|---|---|---|---|
| 640×480 | 6.1 M | $0.37 | $6.13 |
| 320×240 | 2.6 M | $0.16 | $2.60 |

리허설·재시행 2배를 감안해도 **$13을 넘지 않는다.**
`D3`(Nemotron Super)는 셀당 리포트 1건 수준이라 무시할 만하다.

**결론: $125 Token Factory 크레딧은 §6 에이전트 레이어 전체를 덮고도 10배 이상 남는다.**
해상도를 낮춰 토큰을 아끼는 최적화는 의미가 없다 — 320×240이 절반이지만 절대액이 이미 작다.
해상도는 **비용이 아니라 판정 정확도 기준으로** 정해야 한다.

## Cloud 예산 시나리오 (L40S 기준)

| 항목 | 시간 | 비용 |
|---|---|---|
| ACT 학습 | 10h | $15.48 |
| GR00T LoRA 파인튜닝 | 10h | $15.48 |
| `D6` 엔드포인트 웜 유지 | 20h | $30.97 |
| 감사 팬아웃 (CPU 26잡) | ~0.5h | $0.02 |
| **소계** | | **$61.96** |
| 리허설·재시행 2배 가정 | | **$123.92** |

### 절감 지점

1. **`--platform gpu-l40s-a` 명시** — 가장 큰 단일 절감 (2.5배)
2. **`D6` 엔드포인트를 실기 세션 중에만 가동** — GR00T는 Token Factory 모델 목록(24개)에
   **없으므로** Cloud에 자체 호스팅해야 한다. 24시간 상시 가동 시 3일이면 $110을 넘는다.
   §12가 실기를 3일에 분산하고 실제 세션은 약 9.5시간이므로, 세션 중에만 띄우면 $15 수준
3. **감사 팬아웃을 셀 단위로 묶기** — §5.3 원안(5,200잡)은 시간(약 35시간)뿐 아니라
   비용에서도 불리하다. 26잡이면 $0.02

## 미측정

- GR00T 파인튜닝의 실제 소요 시간 (위 10h는 가정)
- ACT 학습의 실제 소요 시간 (위 10h는 가정)
- GR00T를 올린 엔드포인트의 콜드스타트 — attempt-008의 119s는 **연산 0인 컨테이너** 기준이며
  실제로는 훨씬 길다
- 스토리지·네트워크 이그레스 비용
- preemptible 할인율
