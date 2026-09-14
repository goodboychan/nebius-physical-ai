# Nebius Cloud 자격증명 경로 규명 — Studio 키로는 Jobs에 도달 불가

## Scope

`G0`의 미완 항목(Serverless Jobs 더미 팬아웃 20건, Endpoint 콜드스타트)에 필요한
자격증명 경로를 규명했다. **측정은 하지 않았다** — 도달 가능 여부만 확인했다.

## 관측

### Studio 키는 Cloud IAM에 인증되지만 가시성이 없다

대조 실험으로 인증 자체는 확인했다.

| 호출 | 결과 |
|---|---|
| 실제 키 → `api.nebius.cloud/iam/v1/tenants` | `HTTP 200 {}` |
| 가짜 키 → 동일 호출 | `HTTP 401 "Invalid token"` |

401이 아니라 200이 온다는 것은 토큰이 유효하다는 뜻이다. 그런데 반환값이 빈 객체다.

### 모든 리소스 호출이 `parentId`를 요구한다

```
/iam/v1/projects   -> {"code":3, "message":"'' is invalid for parentId"}
/compute/v1/instances -> {"code":3, "message":"parent_id is invalid"}
```

### CLI로도 동일

`nebius` CLI 0.12.276 (linux/arm64)을 설치하고, `--token-file` + `--skip-auth`로
**브라우저 인증 없이** 프로필 `edgeqgate`를 만들었다 (엔드포인트 `api.nebius.cloud`).
프로필 생성은 성공했으나 결과는 REST와 같다.

```
nebius iam v2 tenant list   -> {}
nebius iam v1 project list  -> InvalidArgument: '' is invalid for parentId
nebius iam v2 access-key list -> InvalidArgument: '' is invalid for parentId
```

`nebius iam v2`의 하위 명령은 `access-key` / `project` / `tenant` 셋뿐이고,
신원을 되묻는(whoami 계열) 명령이 없다. 토큰은 불투명 형식(3세그먼트이지만 JWT 아님,
base64 디코드 불가)이라 클레임에서 tenant를 읽을 수도 없다.

### 결론

AI Studio(Token Factory) 키와 Nebius Cloud(Jobs/Endpoint) 접근은 **스코프가 분리되어 있다.**
같은 IAM에 인증되지만 Studio 키에는 클라우드 리소스 가시성이 부여되지 않는다.
따라서 tenant/project ID는 **사람이 브라우저 인증 또는 콘솔 조회로** 가져와야 하며,
자동화로 우회할 수 없다.

## 준비해둔 것

- `nebius` CLI 설치됨 (`~/.nebius/bin/nebius`)
- 프로필 `edgeqgate` 생성·활성화됨. project ID만 확보되면
  `--parent-id` 설정 한 번으로 사용 가능해진다
- 토큰 파일 `~/.config/edgeqgate/nebius_token` (권한 600)
- `~/.config/edgeqgate/env` 권한을 664 -> 600으로 수정 (다른 사용자가 읽을 수 있었다)

## Verification

- tenant 목록이 빈 이유를 **권한 부족과 스코프 분리 중 어느 쪽인지 구분하지 못했다.**
  콘솔에서 실제 tenant를 확인하면 판별된다
- Jobs/Endpoint API의 실제 경로와 스키마는 **아직 확인하지 못했다.** parentId가 생긴 뒤에야
  접근 가능하므로, §5.3 팬아웃 스펙이 실제 API와 맞는지는 여전히 미검증이다
- §12가 리스크로 지목한 "Jobs 동시성/큐 지연"과 "Endpoint 콜드스타트"는 **측정하지 못했다**

## 주장하지 않는 것

- Studio 키에 클라우드 권한을 부여할 수 **없다**고 말하지 않는다. 콘솔에서 권한을 주면
  될 수도 있다. 확인한 것은 현재 상태에서 보이지 않는다는 것뿐이다
- `G0`의 Jobs/Endpoint 항목은 여전히 **미완**이다. 이 시도는 경로를 좁혔을 뿐이다
