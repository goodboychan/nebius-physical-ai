# Nebius 클라우드 접근 — tenant 확보, 전 프로젝트 SUSPENDED로 `G0` Jobs 항목 차단

## Scope

브라우저 인증 완료 후 tenant/project를 확보하고, `G0`의 Jobs/Endpoint 항목 착수를 시도했다.
**측정은 하지 못했다** — 아래 차단 사유 때문이다.

## 관측

### tenant 확보

| 항목 | 값 |
|---|---|
| tenant | `tenant-e00t3trd27d1e08fpq` (`jade-caribou-tenant-3ta`) |
| 상태 | `ACTIVE` |
| 생성 | 2026-09-14T14:55:40Z |

### Studio 키의 스코프 문제가 확정됐다

attempt-005에서 "권한 부족인지 스코프 분리인지 구분하지 못했다"고 남긴 항목이 해소됐다.
동일한 호출을 두 프로필로 대조했다.

| 프로필 | 자격증명 | `iam v1 project list --parent-id <tenant>` |
|---|---|---|
| `mycloud` | 브라우저 인증(사용자 계정) | 성공 — 프로젝트 6개 반환 |
| `edgeqgate` | `NEBIUS_API_KEY` (AI Studio) | **`PermissionDenied: No permission`** |

`InvalidArgument`가 아니라 `PermissionDenied`다. **AI Studio 키로는 클라우드 리소스에
접근할 수 없다**는 것이 확정이다. Token Factory(`D3`/`D4`)와 Cloud(Jobs/Endpoint)는
자격증명을 분리해서 다뤄야 한다.

### 전 프로젝트가 SUSPENDED

| PROJECT ID | REGION | SUSPENSION |
|---|---|---|
| `project-e00dkv33pr00a5476qtybq` | eu-north1 | SUSPENDED |
| `project-e01f64hqpa00n30sz1jybm` | eu-west1 | SUSPENDED |
| `project-e03cey9rlc00cy42hy4ay5` | uk-south1 | SUSPENDED |
| `project-e05ad1gxln0057snzh3dy5` | uk-south2 | SUSPENDED |
| `project-u00sfcy9kc00x2my5g9955` | us-central1 | SUSPENDED |
| `project-i00jjf4amd00evxx5j3rn9` | me-west1 | SUSPENDED |

`container_state`는 ACTIVE이지만 `suspension_state`가 전부 SUSPENDED다.
기본 프로젝트만 있고 사용자가 만든 프로젝트는 없다 (tenant 생성이 어제다).

### 잡 생성 차단 확인

`--dry-run`으로 과금 없이 확인했다.

```
nebius ai job create --parent-id project-e00dkv33pr00a5476qtybq \
  --image ubuntu:24.04 --container-command "echo hello" --dry-run
-> PermissionDenied: you do not have permission to access the requested object
```

브라우저 인증 프로필로도 막힌다. IAM 읽기는 되는데 리소스 생성이 안 되므로,
역할 문제가 아니라 **프로젝트 중단 상태 때문**으로 판단한다.

### CLI에 결제 조회가 없다

`nebius billing v1alpha1`의 하위 명령은 `calculator`와 `one-time-export` 둘뿐이다.
결제 계정 상태 조회·활성화는 **웹 콘솔에서만** 가능하다.

## `G0`에 대한 함의

`G0`의 남은 산출물 중 둘이 이 차단에 묶여 있다.

- Jobs 더미 팬아웃 20건 — §12가 "Jobs 동시성/큐 지연이 예상보다 큼"을 `G4` 지연 리스크로 지목
- Endpoint 콜드스타트 측정 — §12가 "`D6` 서사 붕괴" 리스크로 지목

둘 다 **사람이 콘솔에서 계정을 활성화해야** 진행된다. 코드로 우회할 수 없다.

## 부수 확인 — VM은 필요 없다

`nebius ai job create`는 `--image` / `--platform` / `--preset`을 받는 컨테이너 잡이다.
VM 프로비저닝 개념이 없다. `nebius ai endpoint`도 마찬가지다.
따라서 §2.2의 학습·감사·폴백 셋 다 VM 생성 없이 구성된다.

`--platform` 기본값이 `gpu-h100-sxm`(eu-north1)이라 **명시하지 않으면 가장 비싼 것으로 잡힌다.**
L40S를 쓰려면 `--platform gpu-l40s-d`를 명시해야 한다.

`--preemptible`은 감사 팬아웃에 적합하다. `audit_buffer.bootstrap_indices()`가
replicate 번호에서 결정적으로 인덱스를 만들므로, 중단 후 재실행해도 동일 결과가 나온다.
반대로 **학습 잡에는 쓰면 안 된다** — `IG-3`이 단일 FP32 체크포인트를 요구하는데
재실행으로 체크포인트가 달라지면 그리드 전체의 전제가 깨진다.

## Verification

- 차단 원인을 **SUSPENDED로 추정**했을 뿐, 결제 상태를 직접 확인하지는 못했다.
  CLI에 조회 수단이 없고 콘솔 접근이 필요하다. 역할(IAM role) 부족일 가능성을 완전히
  배제하지 못했다
- `--dry-run`이 스키마 검증까지 갔는지 권한 검사에서 바로 끊겼는지 구분하지 못했다.
  따라서 **§5.3 팬아웃 스펙이 실제 Jobs API와 맞는지는 여전히 미검증**이다
- 잡 preset·플랫폼의 실제 가용 목록을 조회하지 못했다 (같은 권한 문제)

## 주장하지 않는 것

- 계정을 활성화하면 잡이 돌 것이라고 단언하지 않는다. 활성화 후 재시도해야 안다
- 해커톤 크레딧이 이 tenant에 적용되는지 확인하지 않았다
