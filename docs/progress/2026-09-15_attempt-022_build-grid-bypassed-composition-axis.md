# attempt-022 — `build_grid.py`가 `calib_composition` 축을 구현하지 않고 있었다

- 일자: 2026-09-15
- 상태: 수정 완료, 회귀 테스트 추가
- 관련: §4.1(요인 그리드), `IG-1`, `IG-2`, `K3`, `G3`, `LOCK-2`

## 발견

attempt-021에서 Orin 빌드 비용이 7.5배(903s/엔진)로 뛰었다. 26셀에 6.5시간이 든다.
"6.5시간을 태우기 전에 26셀이 실제로 서로 다른지부터 확인하자"는 생각으로
`build_grid.py`의 캘리브레이션 경로를 읽었다. 거기서 나왔다.

`build_grid.py`는 docstring에 이렇게 적혀 있었다:

> `IG-1`: 캘리브레이션은 train 분할에서만 (edgeqgate.calibration이 강제)

**그 모듈을 부르지 않는다.** 실제 코드는 이랬다:

```python
rng = np.random.default_rng(
    int(hashlib.sha256(f"{v.code}|{v.calib_composition}|{size}".encode()
                       ).hexdigest()[:8], 16))
sel = rng.choice(n_frames, size=size, replace=False)
```

`calib_composition`이 등장하는 곳은 **시드 문자열 안이 전부**다. 프레임 풀은 구성으로
필터링되지 않는다. 즉 생산 경로에서 `success-only` / `mixed` / `late-phase-only`는
**같은 균일 풀에서 시드만 바꿔 뽑은 것**이었다.

## 무엇이 깨졌나

### 1. 3축 요인 설계 중 한 축이 순수 노이즈였다

§4.1은 `calib_size`(4) × `calib_composition`(3) × `granularity`(2) = 24 INT8 셀이다.
그대로 빌드했다면 composition으로 갈리는 부분은 전부 시드 재추첨이고, `G4`에서
`K3`("오프라인 점수가 셀 간 분산을 거의 안 보임")가 그 축에 대해 **거의 확정적으로**
발동했을 것이다. 그리고 그 발동은 "구성 축이 중요하지 않다"는 결과로 읽혔을 것이다.
실제로는 구성 축을 구현하지 않은 것인데.

### 2. `IG-1`·`IG-2`·누출 재검사가 전부 우회됐다

`edgeqgate.calibration.build_calibration_set`은 `assert_allowed(..., "calibration")`으로
train 한정을 강제하고, `verify_no_audit_leak()`으로 선정 결과를 재검사하며, 풀이 모자라면
**중복 표본으로 채우지 않고 실패**시킨다. 자체 RNG 경로는 이 셋 모두를 건너뛴다.

실질적 누출은 없었다 — 캐시 자체가 train 에피소드에서만 만들어졌다. 그러나 **보증이
코드로 강제되지 않고 캐시 생성 시점의 우연에 의존**하고 있었다.

### 3. attempt-010의 수치는 생산 경로의 것이 아니다

attempt-010은 "활성화 양자화기 67개가 구성에 따라 중앙 1.2–11.2% 달라진다"를 보고했다.
그 측정은 `scripts/calib_axis_probe.py`가 했고, **그 스크립트는 위상 기반 선택을 제대로
구현했다**(`phase_of`, `late-phase`, `early-phase`). 즉 그 수치는 올바른 구현의 것이고,
당시의 `build_grid.py`가 만들었을 26셀에는 해당되지 않는다.

attempt-010의 결론("두 축은 작동한다")은 **여전히 유효하다.** 잘못된 것은
생산 경로가 그 구현을 쓰지 않았다는 점이다.

## 왜 테스트가 못 잡았나

`tests/test_calibration.py`는 14개 테스트로 라이브러리가 옳게 동작함을 증명한다 —
late-phase가 후반 구간에 갇히는지, success-only가 실패를 배제하는지, 라벨이 없으면
`approximated=True`가 붙는지까지. 전부 통과하고 있었다.

**라이브러리가 옳은 것과 생산 경로가 그것을 호출하는 것은 다른 명제다.**
테스트는 전자만 증명했다.

## 수정

`scripts/build_grid.py`:

- `build_calibration_set()` + `verify_no_audit_leak()`를 실제로 호출
- 평탄한 프레임 캐시를 `(에피소드, 에피소드 내 순번)` 좌표로 되돌리는
  `calibration_index()` 추가. 구성 축과 누출 검사가 에피소드 단위로 돌기 때문에 필요하다
- 분할 manifest를 `determine_splits`로 재구성하고 `manifest_hash`를 로그에 남겨
  `g0_real_data_pipeline.py`와 대조 가능하게 했다
- 풀 부족은 `CalibrationUnavailable`로 셀 실패 처리 (중복 패딩 금지)
- 셀 레코드에 `calib_set_hash`, `calib_approximated` 추가

`tests/test_build_grid_wiring.py` (신규 5건): 소스 수준으로 생산 경로를 검사한다.
`build_grid`를 import하려면 torch·modelopt·GPU가 필요해 CI에서 못 돌린다.

- 캘리브레이션 빌더를 호출하는가
- 누출 검증기를 호출하는가
- `default_rng`가 파일에 없는가
- `calib_composition`이 f-string 시드 재료로만 쓰이고 있지 않은가 (이 버그의 정확한 형태)
- `calib_approximated`를 기록하는가

164 테스트 통과 (기존 159 + 5).

## 범위 확인

생산 경로에서 자체 RNG로 캘리브레이션 프레임을 뽑는 곳이 더 있는지 전수 확인했다.

| 스크립트 | 자체 RNG | 판정 |
|---|---|---|
| `build_grid.py` | 있었음 | **수정함** |
| `calib_axis_probe.py` | 있음 | 프로브. 위상 선택을 제대로 구현했고 생산 경로가 아니다 |
| `es_coverage_cost.py` | 있음 | 순수 합성 시뮬레이션. 데이터 미접촉 |
| `dimension_dilution_probe.py` | 있음 | 순수 합성 시뮬레이션. 데이터 미접촉 |
| `g0_real_data_pipeline.py` | 없음 (`torch.linspace`) | 단일 셀 `G0` 드라이런. 구성 축이 적용되지 않는 지점 |

## 타이밍

`LOCK-2` 전이고 `G3` 전이다. 26셀은 아직 하나도 빌드하지 않았다.
사전등록을 바꾸는 것이 아니라 **사전등록대로 구현하는 것**이므로 개정 대상이 아니다.
`decision_log.md`에 남길 성격도 아니다 — 설계 변경이 아니라 버그 수정이다.

`G4`에서 `K3`를 판정할 때, "구성 축의 분산이 작다"는 관측이 나오면 이 수정 이후의
코드로 빌드된 것인지 확인해야 한다. 그래서 여기 적어둔다.

## 주장하지 않는 것

- 수정 후 구성 축이 **충분히 큰** 셀 간 분산을 만든다고 주장하지 않는다.
  attempt-010이 잰 활성화 1.2–11.2%가 클로즈드루프 성공률 차이를 만드는지는
  **이 연구의 질문 그 자체**다
- attempt-010의 수치에 **노이즈 바닥이 없다**. 같은 구성을 다른 시드로 재추첨했을 때
  활성화 스케일이 얼마나 움직이는지는 아직 측정하지 않았다. 그것 없이는 2.07%(256/late-phase)가
  축 효과인지 표본 노이즈인지 구분되지 않는다. 다음 순번
- 실제 누출이 있었다고 주장하지 않는다. 캐시가 train 전용이라 결과적으로는 없었다

## 다음

- [ ] 캘리브레이션 축의 **노이즈 바닥** 측정 — 동일 구성 × 다른 시드의 활성화 스케일 산포
- [ ] timing cache 효과 (진행 중) → `G3` 일정 확정
- [ ] 4팔 가용 여부 회신 후 #11/#12 확정
