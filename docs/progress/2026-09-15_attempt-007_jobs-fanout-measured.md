# Nebius Jobs 팬아웃 실측 — §5.3 원안은 일정 안에 끝나지 않는다

## Scope

크레딧 적용으로 프로젝트 중단이 풀린 뒤 `G0`의 Jobs 항목을 측정했다.
더미 잡 20건으로 제출 지연·프로비저닝 대기·종료까지의 시간을 쟀다.

**하지 않은 것**: Endpoint 콜드스타트 미측정, 실제 감사 연산 미실행(더미는 `echo; sleep 30`),
GPU 잡 미실행, 학습 미착수.

## 선행 조건 해소

전 프로젝트가 `SUSPENSION: NONE` / `CONTAINER: ACTIVE`로 전환됐다 (attempt-006의 차단 해소).

## 쿼터 지도 — 리전 분리가 강제된다

| 자원 | 가용 리전 | 한도 |
|---|---|---|
| `compute.instance.gpu.l40s` | **eu-north1 전용** | 32 |
| `compute.instance.gpu.rtx6000` | eu-south1, uk-south2, us-central1 | 32 |
| `compute.instance.gpu.h100` | eu-north1 | 32 |
| `compute.instance.gpu.h200` | eu-north1, eu-west1, us-central1 | 32 |
| `compute.instance.non-gpu.vcpu` | eu-west1, uk-south1/2, me-west1, us-north1, eu-south1, eu-west2 | 200 |
| `compute.instance.count` | 전 리전 | **12** |
| `compute.instance.preemptible.count` | 전 리전 | 8 |

**L40S가 있는 eu-north1에는 CPU vCPU 쿼터가 0이다.** eu-north1에서 CPU 잡을 만들면
`ResourceExhausted: compute.instance.non-gpu.vcpu (limit 0, requested 2)`로 거부된다.

따라서 학습(GPU, eu-north1)과 감사 팬아웃(CPU, eu-west1 등)은 **리전을 분리해야 한다.**
아티팩트가 리전을 넘어 이동하므로 §5.3의 "불변 스토리지" 설계에 영향이 있다.

플랫폼 이름도 확인했다. `gpu-l40s-a`가 "NVIDIA L40S Intel"(최소 preset `1gpu-8vcpu-32gb`),
`gpu-l40s-d`가 "NVIDIA L40S AMD"(최소 `1gpu-16vcpu-96gb`). 둘 다 48GB.
CLI 도움말이 예시로 드는 `gpu-l40s-d`가 최소 구성이 더 크므로, 최저가는 `gpu-l40s-a`다.

## 측정 결과 (더미 20건, cpu-d3 / 2vcpu-8gb, 작업 `sleep 30`)

| 지표 | 값 |
|---|---|
| 제출 성공 | 20 / 20 |
| 제출 벽시계 (동시 10워커) | 17.7s |
| 제출 지연 (중앙값 / 최소 / 최대) | 8.1s / 6.8s / 10.0s |
| 제출→종료 (중앙값) | **291s** |
| 제출→종료 (최대) | **484s** |
| 잡당 순수 오버헤드 (중앙값) | **261s** (291 − 실제 작업 30) |

상태 전이는 `PROVISIONING -> STARTING -> IMAGE_PULLING -> COMPLETED`였다.

## §5.3에 대한 함의 — 원안은 불가능하다

`compute.instance.count` 한도 12를 동시 실행 상한으로 두고 계산하면:

| 구성 | 잡 수 | 웨이브 | 총 소요 |
|---|---|---|---|
| §5.3 원안 (26셀 × 200 replicate) | 5,200 | 434 | **약 35시간** |
| 셀당 1잡으로 묶음 | 26 | 3 | 약 0.2시간 |

`G4`가 ~10/11이고 그 뒤 `LOCK-2` 해시 커밋이 이어지는 일정에서 35시간은 현실적이지 않다.
게다가 이 추정은 **큐 대기가 늘지 않는다는 낙관적 가정** 위에 있다 — 실측에서 20건만으로도
프로비저닝이 웨이브로 갈렸다.

부트스트랩 replicate는 **같은 오차 벡터 위의 재표집**이므로 셀당 추론은 1회면 된다.
replicate 200배는 2,000개 스칼라에 대한 CPU 연산이며 잡 경계를 나눌 이유가 없다.
따라서 작업 단위를 `(cell) × (replicate)`가 아니라 **`(cell)`** 로 묶고, 한 잡 안에서
200 replicate를 도는 구조가 맞다. 결정성은 유지된다 —
`bootstrap_indices(n, replicate, seed)`가 replicate 번호에서 인덱스를 만들기 때문에
묶든 나누든 같은 값이 나온다.

## Verification

- **동시성 지표를 얻지 못했다.** 스크립트가 `RUNNING` 상태를 셌는데 이 플랫폼에는
  그 상태가 나타나지 않는다. `max_observed_concurrency: 0`은 측정 실패이지 관측값이 아니다.
  `ACTIVE_STATES = {STARTING, IMAGE_PULLING, RUNNING}`로 고쳤으나 **재측정하지 않았다**
- 위 35시간 추정은 동시성을 쿼터 한도 12로 **가정**한 값이다. 실제 달성 동시성은 미측정이므로
  더 나쁠 수도 더 나을 수도 있다
- 더미 잡은 `ubuntu:24.04`에 `echo; sleep 30`이다. 실제 감사 잡은 더 큰 이미지를 끌어오므로
  `IMAGE_PULLING` 구간이 길어진다. **261s는 오버헤드의 하한으로 봐야 한다**
- preemptible로 돌렸을 때의 중단율은 측정하지 않았다

## 주장하지 않는 것

- 묶은 구성(26잡)이 0.2시간에 끝난다고 말하지 않는다. 그 구성으로 **실행해보지 않았다**.
  같은 오버헤드 모델을 적용한 산술일 뿐이다
- 실제 감사 연산(TRT 추론 + 점수 산출)의 소요 시간은 전혀 모른다. 여기서 잰 것은
  플랫폼 오버헤드뿐이다
