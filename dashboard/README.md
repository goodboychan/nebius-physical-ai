# `D7` 감사 대시보드

배포본: https://claude.ai/artifact/2tUAoJHBeT8uLU96BmgPNK

`audit_gate.html`은 아티팩트로 배포되는 단일 페이지다. 빌드 단계가 없다 —
외부 스크립트 의존이 없고 차트는 인라인 SVG다.

## 무엇을 싣는가

지금까지 **실제로 측정된 것만** 싣는다. 실기 trial이 0건이므로 성공률·순위·
`EP-1` 같은 결과 지표는 존재하지 않고, 대시보드는 그 사실을 첫 화면에 명시한다.

| 패널 | 출처 |
|---|---|
| 순서 잠금 (`LOCK-1`–`4`) | `edgeqgate.freeze.lock2_status()` |
| 변형 그리드 26셀 | `artifacts/g0/grid_v2/grid_manifest.json` |
| 배포 대상 지연 | `artifacts/g0/orin_latency.json` |
| 감사 점수 + CI | `artifacts/jobs/*.json` (Nebius Jobs 산출) |
| 캘리브레이션 표면적 | `artifacts/g0/calib_axis_probe.json` |
| 에이전트 레이어 | `d4_runtime.json`, `d4_tail_latency.json`, `d6_groot_coldstart.json`, `retrieval/errata.json` |

## 설계 근거

- **계기판 은유**: 내용물이 해시·잠금 상태·밀리초다. 대시보드가 아니라 교정 성적서에 가깝게 갔다
- **IBM Plex 슈퍼패밀리**: Mono가 수치와 해시를 담는다 — 여기서 해시는 장식이 아니라 내용물이다
- **팔레트 검증**: 카테고리 2색을 `dataviz`의 검증기로 light/dark 양쪽에서 통과시켰다
  (CVD ΔE 16.8, normal 25.7). 콜드스타트 단계는 순서가 있으므로 카테고리가 아니라
  시퀀셜 램프(L 0.894→0.436, 단조 감소)를 썼다
- **`LOCK-2` 미동결을 최상단에 둔다**: 이 판이 말하는 가장 중요한 사실은
  "아직 실기를 돌릴 수 없다"이다

## 갱신

수치는 현재 HTML에 인라인되어 있다. 아티팩트가 정적 페이지이고 아티팩트 자체가
실행 환경이라 빌드 파이프라인을 두지 않았다. `G4` 이후 실제 점수가 생기면
`scripts/`에 생성기를 추가해 아티팩트 데이터를 갱신한다.
