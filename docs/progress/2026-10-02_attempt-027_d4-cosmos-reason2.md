# attempt-027 — `D4`를 NVIDIA 모델로: Cosmos-Reason2-2B 지연 실측

- 일자: 2026-10-02
- 관련: §6 `D4`, attempt-004/008(MiniCPM-V 381ms)

## 왜

`D4`는 사전등록상 "Nemotron 3 Nano Omni"인데 Token Factory에 없어 `openbmb/MiniCPM-V-4_5`로 구현돼 있었다.
2026-10-02 재확인: Token Factory의 NVIDIA 모델 4종(Nemotron 3 Nano/Super/Ultra, 3.5 Lightning) 모두
`This model does not support image input`. 해커톤은 NVIDIA 모델 사용을 요구한다.

## 측정

- 모델 `nvidia/Cosmos-Reason2-2B` (Qwen3-VL 구조, gated — 사용자 라이선스 수락 후)
- GX10(GB10) 로컬 vLLM 0.23.0, `--gpu-memory-utilization 0.25`
- 입력: 실제 SO-101 train 프레임 640×480 JPEG + 한 단어 판정 프롬프트, `max_tokens=8`, keep-alive
- 32회, 앞 2회 워밍업 제외

| | 값 |
|---|---|
| median | **80 ms** |
| p95 | 81 ms |
| 500 ms 예산 이내 | **30/30** |
| prompt tokens | 356 |
| 출력 | `CONTINUE` 한 단어로 파싱 가능 |

MiniCPM-V(Token Factory, 381 ms)의 약 1/5.

## 한계

- **판정 품질은 재지 않았다.** 정상 프레임 하나에 `CONTINUE`가 나온 것뿐이다. 멈춤·이탈 프레임에서
  `FALLBACK`/`ABORT`를 내는지는 실제 데모가 생긴 뒤 확인해야 한다
- **GX10 로컬 수치다.** Nebius 엔드포인트에 올리면 왕복 지연이 더해진다. attempt-008/017에서 엔드포인트
  왕복은 854–948 ms(무연산)로 측정돼 **500 ms 예산을 단독으로 넘는다.** 따라서 `D4`는 GX10 로컬 실행이 기본안이다
- 서버는 측정 후 내렸다(GB10 통합 메모리 ~27 GB 점유)

## 다음

- 사용자 확인 후 `decision_log.md`: `D4` 모델을 MiniCPM-V → Cosmos-Reason2-2B, 실행 위치 Token Factory → GX10 로컬
