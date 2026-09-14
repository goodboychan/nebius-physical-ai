# `G0` 클라우드 경로 검증 — `D4` 모델 전제 붕괴, 2Hz 예산 초과

## Scope

자격증명(`NEBIUS_API_KEY`, `TAVILY_API_KEY`)이 제공되어 `G0`의 클라우드 항목을 확인했다.
Token Factory, Tavily, GR00T 접근, 그리고 §6 `D3`/`D4`의 모델 전제 검증이 대상이다.

**하지 않은 것**: Nebius Serverless Jobs 더미 팬아웃 미착수, Endpoint 콜드스타트 미측정
(둘 다 `NEBIUS_PROJECT_ID`/`TENANT_ID`/서비스계정 키 필요). 공개 SO-101 데이터셋 미사용,
ACT 실제 학습 없음, 실기 없음.

## 자격증명 상태

`HF_TOKEN`은 **별도로 받을 필요가 없었다** — `huggingface-cli login`이 남긴
`~/.cache/huggingface/token`(프로필 `[gx10]`)이 이미 있고 유효하다 (계정 `chans`, 권한 `read`).
`scripts/check_credentials.py`가 이를 자동으로 줍도록 했다. 값은 출력하지 않고 길이와 앞 2글자만 찍는다.

`~/.config/edgeqgate/env`의 권한이 `664`였다 — 같은 머신의 다른 사용자가 읽을 수 있는 상태.
`600`으로 변경했다.

미설정 5개: `NEBIUS_BASE_URL`(아래에서 발견), `NEBIUS_PROJECT_ID`, `NEBIUS_TENANT_ID`,
`NEBIUS_SERVICE_ACCOUNT_KEY_FILE`, `NEBIUS_REGION`.

## 관측

### Token Factory

Base URL은 `https://api.studio.nebius.com/v1`로 확인됐다 (모델 24개).

**`D3`(배포 리포트 에이전트) — 문제없음.** `nvidia/nemotron-3-super-120b-a12b` 존재하고 동작한다.
단 **추론 모델이다**: `max_tokens=32`로 호출하면 32토큰을 전부 thinking에 쓰고 빈 문자열을 반환한다.
`max_tokens=512`에서 23토큰으로 정상 출력(1.6s). `D3` 구현 시 토큰 예산을 넉넉히 잡아야 한다.

**`D4`(런타임 감독자) — 사전등록의 모델 전제가 깨졌다.**

§6은 `D4`의 모델로 "Nemotron 3 Nano Omni"를 지정했다. **Token Factory 목록에 그런 모델이 없다.**
가장 가까운 `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`에 이미지를 넣으면:

```
HTTP 400: {"detail":"This model does not support image input"}
```

`D4`는 오버헤드 프레임을 봐야 하므로 비전이 필수다. 목록에서 비전을 지원하는 대안은 둘이다:

| 모델 | 32x32 테스트 | 640x480 프레임 지연(3회 중앙값) |
|---|---|---|
| `openbmb/MiniCPM-V-4_5` | 지원 | **1000ms** (1132/1000/992) |
| `google/gemma-3-27b-it` | 지원 (정답 "Two") | 측정 실패 — 읽기 타임아웃 |

### `D4`의 2Hz 예산은 현재 구성으로 불가능하다

2Hz = 요청당 500ms 예산인데 MiniCPM-V 중앙값이 **1000ms, 예산의 2.0배**다.
gemma는 3회 시도 중 타임아웃이 나서 중앙값을 못 냈다 — 안전 판정 경로에서는 중앙값보다
**꼬리 지연**이 중요한데, 타임아웃이 나온다는 것 자체가 나쁜 신호다.

이건 `D4` 사양의 문제이지 구현 문제가 아니다. 선택지는 셋이다.

1. **주기를 낮춘다** — 1Hz 또는 0.5Hz. 사양 변경이므로 §6 개정 필요
2. **비동기로 돌린다** — 감독자는 가능한 속도로 돌고 제어 루프는 가장 최근 판정을 쓴다.
   이 경우 "2Hz"는 판정 지연이 아니라 **프레임 샘플링 주기**를 뜻하게 되며,
   판정은 항상 1프레임 이상 과거 정보에 기반한다. `EX-3`(개입 지연)에 반드시 명시해야 한다
3. **로컬 추론** — Jetson/GB10에서 작은 VLM을 직접 돌린다. 클라우드 왕복이 사라지지만
   Jetson 자원을 정책 추론과 나눠 쓰게 되어 `EX-2`(추론 지연)를 교란한다

### 부수 발견 — 트랙 적합성

`D4`를 MiniCPM-V나 gemma로 바꾸면 **`D4`가 더 이상 NVIDIA 모델이 아니다.**
`D2`가 "Token Factory·NVIDIA 모델 사용 설명 오디오"를 요구하는데, `D3`가 Nemotron Super를
쓰므로 NVIDIA 모델 사용 자체는 충족된다. 다만 §6의 에이전트 레이어 중 절반이 비-NVIDIA가
되는 것은 트랙 적합성 서사에 영향이 있다. 판단이 필요한 항목이다.

### Tavily

호출 성공 (1.7s, 결과 5건). TRT INT8 / Jetson Orin / 트랜스포머 어텐션 질의에서
NVIDIA 개발자 포럼, squeezebits 블로그, ViT 컴파일 디버깅 글 등이 나왔다 — `D5`의 errata
수집 용도로 쓸 만한 품질이다.

**재현성**: 동일 질의 2회에서 URL **집합과 순서가 모두 동일**했다.
제안 중인 `score_folklore`의 동결 설계에 유리한 신호다.

### GR00T 접근

`nvidia/GR00T-N1.5-3B`, `nvidia/GR00T-N1-2B` 모두 HTTP 200, `gated=False`.
**`G0`의 "GR00T 접근 권한 확인" 항목 충족.**

## `G0` 진행 상황 (§10.2)

| 항목 | 상태 |
|---|---|
| 리포 + Apache 2.0 | 완료 (attempt-001) |
| ACT→ONNX→TRT INT8 경로 검증 | 완료 (attempt-003) |
| GR00T 접근 권한 확인 | 완료 |
| Token Factory 1회 호출 | 완료 |
| Tavily 1회 호출 | 완료 |
| Endpoint 1회 호출 | **미완** — 자격증명 부족 |
| Jobs 더미 팬아웃 20건 | **미완** — 자격증명 부족 |
| 공개 SO-101 데이터셋 → ACT 학습 | **미완** |

통과 기준("TRT INT8 빌드가 한 번이라도 성공")은 attempt-003에서 충족했으나,
산출물 3건이 남아 있어 `G0` 전체는 미완이다.

## Verification

- Tavily 재현성은 **같은 분 안에 2회 호출한 결과**다. 일 단위·주 단위 드리프트는 측정하지 않았다.
  `score_folklore`를 채택한다면 `LOCK-2`까지의 기간에 걸친 재측정이 필요하다
- `D4` 지연은 **합성 프레임**(640x480 절차생성 PNG, base64 10KB) 기준이다.
  실제 카메라 프레임은 JPEG 압축률과 내용이 달라 토큰 수가 달라질 수 있다
- 지연 측정은 3회뿐이라 꼬리 지연을 말할 수 없다. 안전 판정 경로에는 p95가 필요하다
- gemma의 타임아웃 원인은 규명하지 않았다 (콜드스타트/큐 지연/일시 장애 구분 불가)

## 주장하지 않는 것

- `D3`가 감사 아티팩트로부터 쓸 만한 go/no-go 근거를 **서술할 수 있는지**는 확인하지 않았다.
  "OK"를 반환한다는 것만 보였다
- `D4` 후보들이 실제 슬롯 삽입 장면에서 abort 판단을 **정확히** 하는지는 전혀 확인하지 않았다.
  측정한 것은 지연뿐이다
- Tavily 결과의 **내용 품질**을 평가하지 않았다. URL이 그럴듯하다는 인상일 뿐이다
