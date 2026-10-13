# 도구 피드백 (`D8`)

Nebius / NVIDIA 도구를 쓰면서 **실제로 시간을 잃은 지점**만 기록한다.
각 항목은 재현 가능한 관찰이며, 해당 progress note에 원 기록이 있다.

---

## 1. modelopt: fused MHA fast path가 양자화기를 조용히 무력화한다

**증상**: `mtq.quantize()` 후 ONNX export가 실패한다.

```
AssertionError: Quantizer has not been calibrated.
ONNX export requires the quantizer to be calibrated.
```

**원인**: PyTorch의 fused multi-head attention fast path가 `nn.MultiheadAttention`의
`out_proj`를 모듈로 호출하지 않는다. modelopt가 모듈 단위로 삽입한 양자화기가
캘리브레이션 데이터를 한 번도 보지 못해 `amax`가 빈 채 남는다.

**해결**: `torch.backends.mha.set_fastpath_enabled(False)` +
`TransformerEncoder(..., enable_nested_tensor=False)`.

**개선 제안**: 에러 메시지가 fast path를 전혀 가리키지 않는다. 어텐션 모듈이 있고
미캘리브레이션 양자화기가 그 안에 있으면 "fast path를 끄십시오"를 힌트로 주면
추적 시간이 크게 줄어든다. 트랜스포머 정책 양자화에서 보편적으로 걸릴 지점이다.

출처: `docs/progress/2026-09-14_attempt-003_g0-trt-int8-path.md`

---

## 2. trtexec: `--int8` 단독 빌드가 조용히 느려진다

**증상**: INT8 엔진이 FP16보다 **1.46배 느렸다** (28.57ms vs 19.35ms). 엔진은 더 작은데.

**원인**: `--int8`만 켜면 INT8 커널이 없는 레이어가 FP32로 폴백하고 그 사이마다
reformat 노드가 붙는다. `--int8 --fp16`으로 빌드하니 16.22ms로 바뀌었다.

| 빌드 | 중앙 지연 | 레이어 | 엔진 |
|---|---|---|---|
| `--int8` | 28.57 ms | 274 | 139 MB |
| `--int8 --fp16` | **16.22 ms** | 236 | **101 MB** |

**개선 제안**: 문서화는 되어 있으나 놓치기 쉽고, 틀렸을 때 **조용히 느려질 뿐 에러가 없다.**
`--int8`만 주면 빌드 로그에 경고 한 줄("INT8 커널이 없는 레이어 N개가 FP32로 폴백함.
`--fp16`을 함께 지정하는 것을 권장")을 내주면 좋겠다. 폴백 레이어 수는 빌더가 이미 안다.

출처: `docs/progress/2026-09-15_attempt-013_int8-latency-retraction-and-d3.md`

---

## 3. `nebius ai job --inject-file`: 문서는 파일당 한도, 실제는 합계 한도

**문서**: *"the file is read-only inside the container and limited to 64 KiB"* — 파일당으로 읽힌다.

**실제**: 주입 파일 **전체 합계**에 걸린다. 그리고 base64 인코딩 팽창(4/3배)이
한도 계산에 포함되므로 실효 원시 용량은 약 48 KiB다.

```
Error: rpc error: code = InvalidArgument desc = plaintext must not exceed 65536 bytes
caused by service error: Bad Request BadRequest: service kms-dpl, violations:
    plaintext: plaintext must not exceed 65536 bytes
```

**개선 제안**: 도움말 문구를 "모든 주입 파일의 합계, base64 인코딩 후 64 KiB"로 고치면
된다. 에러가 `kms-dpl` 서비스 이름으로 나와 `--inject-file`과의 연결도 바로 보이지 않는다.

---

## 4. `nebius ai job --platform` 기본값이 가장 비싼 GPU다

`--platform` 생략 시 eu-north1에서 `gpu-h100-sxm`($3.85/h)로 잡힌다.
`gpu-l40s-a`는 $1.55/h이므로 **2.5배** 차이다. CPU 잡을 만들려다 GPU 요금이 나갈 수 있다.

**개선 제안**: 기본값을 두는 대신 `--platform` 미지정 시 확인 프롬프트를 띄우거나,
`--dry-run`에 시간당 예상 비용을 표시하면 사고를 막는다.

---

## 5. AI Studio 키와 Cloud 접근이 분리되어 있다는 것이 드러나지 않는다

AI Studio(Token Factory) API 키로 `api.nebius.cloud`를 호출하면 **인증은 통과**한다
(401이 아니다). 그런데 tenant 목록이 `{}`로 비어 오고, 리소스 호출은 `PermissionDenied`다.

```
실제 키 -> HTTP 200 {}          (인증됨, 그러나 아무것도 안 보임)
가짜 키 -> HTTP 401 Invalid token
```

처음에는 권한 부족인지 스코프 분리인지 구분할 수 없어 시간을 썼다.

**개선 제안**: Studio 키로 Cloud 리소스 API를 부르면 "이 키는 AI Studio 전용입니다"라는
명시적 메시지를 주면 좋겠다. 빈 목록은 "권한이 없다"와 "자원이 없다"를 구분해주지 않는다.

---

## 6. CLI에 `nebius init`이 없다

공식 문서 검색 결과와 CLI 힌트 모두 `nebius init`을 안내하지만
(`Check auth/profile/project setup with \`nebius auth login\``), 설치된 CLI
0.12.276에는 `init`도 `auth`도 없다. 실제 명령은 `nebius profile create`다.

**개선 제안**: 에러 힌트 문구를 설치된 버전의 실제 명령으로 맞추면 된다.

---

## 7. Jobs 오버헤드가 소규모 작업을 지배한다

더미 20건 실측: 제출→종료 중앙 **291초**, 그중 실제 작업은 30초.
**잡당 순수 오버헤드 261초**다.

그리고 실제 감사 잡의 **연산 시간은 셀당 0.059초**였다 (부트스트랩 200회 포함).
오버헤드가 연산의 **약 4,400배**다.

이것 자체는 결함이 아니라 특성이지만, 짧은 잡을 대량으로 던지는 설계를
**사전에 단념시키는 문서**가 있으면 좋겠다. "잡당 약 4–5분의 고정 비용을 가정하고
작업을 묶으라"는 안내 한 줄이면 설계 단계에서 방향이 바뀐다.

`compute.instance.count` 쿼터가 12라 동시성도 12로 묶이는데, 이 둘을 함께 보여주는
계산기가 있으면 팬아웃 규모를 정하기 쉬울 것이다.

---

## 8. 리전별 쿼터 조합이 자명하지 않다

`compute.instance.gpu.l40s` 쿼터는 **eu-north1 전용**인데, 같은 리전의
`compute.instance.non-gpu.vcpu` 쿼터는 **0**이다. GPU 학습과 CPU 팬아웃을
같은 리전에 둘 수 없다.

CPU 잡을 eu-north1에 만들려다 받은 메시지:

```
ResourceExhausted: Quota limit exceeded ... compute.instance.non-gpu.vcpu (limit 0, requested 2)
```

**개선 제안**: 프로젝트 생성 시 "이 리전에서 사용 가능한 자원" 요약을 보여주거나,
쿼터 0인 자원을 콘솔에서 눈에 띄게 표시하면 된다.

## 2026-10-13 — Nebius AI Cloud: capacity visibility (user's suggestion)

- **Observed**: `nebius ai endpoint start` stayed in PROVISIONING for over 20 minutes, with the compute instance
  STOPPED. It then went to ERROR `NotEnoughResources` ("VM schedule timeout, most likely due to insufficient hardware
  resources"; eu-north1, gpu-l40s-a 1gpu-8vcpu-32gb). A second start request returned "operation conflict" while the
  first was pending. About an hour later, a Job on the same platform and region got a GPU at once.
- **Impact**: the live Cosmos supervisor was dropped from the positive-control block and replaced by an offline replay,
  and the session plan had to change on the spot.
- **Suggestions**:
  1. Show live availability per region and platform (console and CLI).
  2. Fail fast, or give an estimated wait.
  3. Suggest fallback regions or platforms, or offer an opt-in automatic fallback.
  4. Notify the user, or queue the start, when capacity frees up.
  The goal is fewer blind retries and fewer VMs started in the wrong region.
