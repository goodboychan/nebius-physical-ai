# 양팔 SO-101 설치 체크리스트 (`G1`)

## 팔 연결 호스트: Jetson Orin Nano Super (2026-09-27 결정)

수집(`G1`)과 배포(`G6`)를 같은 머신에서 해서 USB 구조·카메라 드라이버·리사이즈 경로를 일치시킨다.
프레임 드롭률(#9)이 허용치를 넘으면 수집만 GX10으로 옮기고 경로 차이를 한계로 기록한다.

**2026-10-01: 단일팔로 확정.** 공급 전압 실측: 리더 4.9 V, 팔로워 11.8–11.9 V.

> **CLI 타입명 정정**: LeRobot 0.6.1의 등록 이름은 `so101_follower` / `so101_leader`다. 아래 절들의 `so_follower` / `so_leader` 표기는 틀렸다.

 아래 4팔 절차 중 1절(포트 고정)·3절(캘리브레이션)은 2개 팔로 축소 적용.

| 장치 | 어댑터 | 시리얼 | 고정 경로 | 모터 |
|---|---|---|---|---|
| 리더 | CH343 `1a86:55d3` | `5A7A016151` | `/dev/so101_leader` | ID 1–6 (STS3215) 설정 완료 |
| 팔로워 | CH343 `1a86:55d3` | `5AA9017076` | `/dev/so101_follower` | ID 1–6 (STS3215) 설정 완료 |

### 오버헤드 카메라 (2026-10-03 고정)

| 항목 | 값 |
|---|---|
| 장비 | Logitech C922 Pro Stream, 시리얼 `876E8BDF` |
| 고정 경로 | `/dev/so101_cam_top` (udev, 캡처 노드 index 0) |
| 스트림 | 640×480 MJPEG 30fps |
| 고정값 | 수동 노출 333, gain 0, WB 5000K, 초점 0(무한대), 전원 60Hz |
| 자동 적용 | udev `RUN+=/usr/local/bin/so101-cam-lock` — 재연결·재부팅 시 다시 고정. OpenCV로 연 뒤에도 유지됨을 확인 |
| 기준 화면 | `docs/setup/2026-10-03_overhead_reference.jpg` |

**운영 규칙** (화면에 남은 정적 물체 때문):
- 화면 위쪽의 **의자를 수집·실기 내내 그 자리에** 둔다. 앉거나 옮기지 않는다
- 바닥, 책장, 왼쪽 허브·장비를 건드리지 않는다
- 오른쪽 마우스패드 위에 물건을 올리지 않는다
- **리더는 아직 화면 밖 위치를 확정하지 않았다** (USB 선 확보 후)

Luxonis OAK(`03e7:2485`)는 UVC가 아니고 LeRobot에 백엔드가 없어 정책 카메라에서 제외. 깊이 계측용 후보.

### 손목 카메라 후보: OpenMV AE3 (2026-10-04)

| 항목 | 값 |
|---|---|
| 장비 | OpenMV AE3, 30×30×9mm, 8g, PAG7936 1MP **글로벌 셔터**. 손목 마운트 이미 제작됨 |
| 고정 경로 | `/dev/so101_cam_wrist_omv` (udev, 시리얼 `085e070000000000`) |
| 펌웨어 | v4.x → **v5.0.1** (protocol 1.0.2) — udoo-bolt에서 `scripts/flash_openmv_ae3.sh`로 기록 |
| 호스트 라이브러리 | `openmv` (Protocol V2), Orin `~/lerobot-env` |
| 노출 고정 | `auto_exposure(False, exposure_us=15000)`, `auto_gain(False, gain_db=6.0)`, `auto_whitebal(False)` 동작 확인 |

전송 실측 (Orin 수신, 10초):

| 설정 | fps |
|---|---|
| VGA 640×400, 펌웨어 기본 JPEG 스트림 | 7.7–8.0 (max_payload 4K–32K 무관) |
| **QVGA 320×200, 기본 JPEG 스트림** | **25.6** |
| raw 640×400 / 320×200 | 1.8 / 6.0–6.9 (전송로 ~0.8 MB/s) |
| 스크립트에서 직접 `compress()` | 2.4–9.1 (더 느림) |

병목은 장치 쪽 JPEG 생성과 프로토콜 왕복이다. 30fps에는 못 미친다.

겪은 문제와 해결:
- 첫 케이블 불량 → `error -71`, `Cannot enable. Maybe the USB cable is bad?` → 케이블 교체로 해결
- Windows IDE 업데이트 실패(XMOS 관련) → udoo-bolt Linux에서 `dfu-util`로 기록
- 부트로더 창(초록불)은 약 1.5초. udoo-bolt의 **fwupd**가 DFU 장치를 먼저 잡아 `LIBUSB_ERROR_BUSY` → fwupd 일시 중지 후 성공, 이후 복원
- Orin의 ModemManager가 시리얼 장치에 AT 명령을 보낼 수 있어 팔 어댑터(1a86:55d3)와 OpenMV(37c5)를 제외 (`/etc/udev/rules.d/70-so101-mm-ignore.rules`)

**LeRobot 플러그인** `plugins/lerobot_camera_openmv` (Orin에 `-e`로 설치, 카메라 타입 `openmv`).
백그라운드 스레드가 최신 프레임을 유지하고, 노출·게인·WB를 장치에서 고정한다.

30Hz 녹화 루프 모의(30초, 오버헤드 C922 + AE3 동시): 루프 29.7Hz, 늦은 반복 0,
오버헤드 프레임 반복 5.2%, **손목 프레임 반복 14.6%**(AE3 25.6fps), Orin CPU 유휴 93%.

화이트밸런스를 자동으로 잡고 고정하면 세션마다 값이 조금씩 달라진다
(R/B dB: 3.96/4.63, 4.00/4.61, 4.03/4.67). **손목 장착 후 작업 장면에서 한 번 잡은 값을
`rgb_gain_db`로 박아 넣어야** 세션 간 재현된다.

### 기존 손목 카메라 (Sonix 0c45:6340) — 예비

UVC 규격 위반으로 USB 대역폭을 최대로 요구해 C922와 동시에는 640×480 불가(320×240만 가능). 노출·WB·초점 제어 없음.
`/dev/so101_cam_wrist`, 허브 3번 포트 고정.

준비 완료 (2026-09-27):
- `chanseok` → `dialout`, `docker` 그룹 추가 (**재로그인 필요**)
- `~/lerobot-env/.venv`: Python 3.12.13, lerobot 0.6.1 + feetech, av 13.1.0(≥14는 `av.option` 없음), opencv 4.13
- torch는 CPU 빌드(`cuda False`) — 텔레옵·수집에는 무관. 추론은 TRT 엔진으로 따로 한다
- 사용: `source ~/lerobot-env/.venv/bin/activate`

작성: 2026-09-16. 근거: LeRobot 0.6.1 소스 확인 (`edgeqgate-lerobot:25.11` 이미지).
하드웨어 없이 확인 가능한 것만 사실로 적었다. 나머지는 **현장 확인**으로 표시했다.

---

## 0. 결론 먼저 — 설치 순서

```
1) 4개 팔 개별로 USB 연결 → 포트 식별 → udev 규칙 고정   ← 여기가 제일 큰 시간 구덩이
2) 모터 ID 설정 (필요 시)
3) 팔 4개 개별 캘리브레이션
4) 카메라 3대 연결 → 인덱스 고정
5) 양팔 텔레옵 1회 성공
6) 지그·조명 고정 → 사진 기록
```

**1번에서 막히면 나머지가 다 밀린다.** 아래 1절을 먼저 읽을 것.

---

## 1. 포트 식별 — 4개 팔의 최대 난관

SO-101은 팔마다 USB-시리얼 어댑터가 하나씩 붙는다. 팔 4개면 `/dev/ttyACM0..3`이
**부팅·연결 순서에 따라 바뀐다.** 어제 왼팔이던 게 오늘 오른팔이 된다.

`BiSOFollowerConfig`는 `left_arm_config.port` / `right_arm_config.port`를 **각각 요구**하므로
(기본값 없음, `REQUIRED`) 포트가 흔들리면 좌우가 뒤바뀐 채로 데이터를 모으게 된다.

### 절차

**한 번에 하나씩 꽂는다.** 4개를 동시에 꽂고 구분하려 하지 말 것.

```bash
lerobot-find-port          # 꽂기 전/후를 비교해 포트를 알려준다
```

포트를 찾으면 **즉시 시리얼 번호를 읽어 udev 규칙으로 고정**한다:

```bash
udevadm info -a -n /dev/ttyACM0 | grep -m1 '{serial}'
```

`/etc/udev/rules.d/99-so101.rules`:

```
SUBSYSTEM=="tty", ATTRS{idVendor}=="__VID__", ATTRS{serial}=="__SN1__", SYMLINK+="so101_follower_left"
SUBSYSTEM=="tty", ATTRS{idVendor}=="__VID__", ATTRS{serial}=="__SN2__", SYMLINK+="so101_follower_right"
SUBSYSTEM=="tty", ATTRS{idVendor}=="__VID__", ATTRS{serial}=="__SN3__", SYMLINK+="so101_leader_left"
SUBSYSTEM=="tty", ATTRS{idVendor}=="__VID__", ATTRS{serial}=="__SN4__", SYMLINK+="so101_leader_right"
```

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
ls -l /dev/so101_*        # 4개가 보이면 성공
```

이후 설정에는 `/dev/ttyACM*`이 아니라 **`/dev/so101_follower_left`** 같은 심볼릭 링크를 쓴다.

> **왜 이걸 미리 하나**: §2.3 재현성 고정 장치는 지그·조명을 고정하라고 요구한다.
> 좌우 팔이 뒤바뀌는 것은 그보다 더 심한 변동이며, 데이터 수집(`G1`)과
> 실기 시행(`G6`, 5주 뒤) 사이에 일어나면 **조용히** 결과를 무효로 만든다.

**어댑터 4개가 같은 모델이면 시리얼 번호가 유일한 구분자다.** 시리얼이 없는 싸구려
어댑터면 `KERNELS=="1-2.3"` 같은 **USB 포트 경로**로 고정해야 하고, 그러면
**항상 같은 물리 포트에 꽂아야 한다.** 그 경우 포트에 라벨을 붙일 것. *(현장 확인)*

---

## 2. 모터 ID *(현장 확인)*

팔마다 STS3215 6개가 데이지체인이고 ID 1–6이 필요하다. 팔마다 버스가 따로이므로
**팔 간 ID 충돌은 없다.**

```bash
lerobot-setup-motors --help
```

대여품이 이미 설정돼 있으면 건너뛴다. 아니면 팔당 6개 × 4팔 = **24회**다.
한 번에 한 모터만 연결해서 돌리는 방식이라 시간이 걸린다. **이게 필요한지 먼저 확인할 것.**

---

## 3. 캘리브레이션 — 4회

```bash
lerobot-calibrate --robot.type=so_follower --robot.port=/dev/so101_follower_left  --robot.id=follower_left
lerobot-calibrate --robot.type=so_follower --robot.port=/dev/so101_follower_right --robot.id=follower_right
lerobot-calibrate --teleop.type=so_leader  --teleop.port=/dev/so101_leader_left   --teleop.id=leader_left
lerobot-calibrate --teleop.type=so_leader  --teleop.port=/dev/so101_leader_right  --teleop.id=leader_right
```

`id`가 캘리브레이션 파일 이름이 된다. **`left`/`right`를 이름에 박아둘 것** —
나중에 어느 파일이 어느 팔인지 헷갈리면 다시 해야 한다.

캘리브레이션 파일을 **리포에 커밋하거나 최소한 백업**할 것. 이것도 §2.3의 고정 장치다.

---

## 4. 카메라 3대 — 키 이름이 정해져 있다

`BiSOFollower._cameras_ft` 소스 확인 결과:

- `BiSOFollowerConfig.cameras`(최상위)의 키는 **접두사 없이** 그대로
- `left_arm_config.cameras`의 키는 **`left_` 접두사**
- `right_arm_config.cameras`의 키는 **`right_` 접두사**

따라서 ALOHA식 3대 배치의 관측 키는:

| 위치 | 설정 위치 | 관측 키 |
|---|---|---|
| 오버헤드 | `cameras={"top": ...}` (최상위) | `top` |
| 왼손목 | `left_arm_config.cameras={"wrist": ...}` | `left_wrist` |
| 오른손목 | `right_arm_config.cameras={"wrist": ...}` | `right_wrist` |

```bash
lerobot-find-cameras          # 인덱스와 지원 포맷 확인
```

### 반드시 확인할 것

- [ ] **MJPEG 지원 여부.** USB 2대가 같은 컨트롤러에 물리면 원본 YUV로는 대역폭이 모자란다
- [ ] **자동 노출·화이트밸런스·오토포커스 전부 수동 고정.** 조명을 고정해도 카메라가
      자동 보정하면 무의미하다. 제일 흔한 조용한 실패다
- [ ] 카메라 인덱스도 포트처럼 흔들린다. udev 또는 `by-id` 경로로 고정할 것
- [ ] **여분 카메라를 같은 모델로 하나씩** 확보. 중간에 하나 죽으면 교체가 아니라
      `K5`급 사건이 된다

> **RealSense는 정책 입력으로 넣지 말 것.** 세 번째 "계측 전용" 카메라로 분리해 두면
> 나중에 위치를 조정하거나 교체해도 **정책 입력 분포가 변하지 않는다.**
> 성공 판정(`IG-6`, `manual_actions` #7) 계측 용도로만 쓴다.

---

## 5. 전원·USB 예산 *(현장 확인)*

| 항목 | 수량 | 확인 |
|---|---|---|
| 팔로워 전원 | 2 | 팔로워는 부하가 크다. 전원 어댑터 2개 필요 |
| 리더 전원 | 2 | 리더는 부하가 작다. USB 급전 가능 여부 확인 |
| USB 시리얼 | 4 | 팔당 1개 |
| USB 카메라 | 2 | 손목 2대 (오버헤드는 CSI 권장) |
| **합계 USB** | **6** | **전원 공급형 허브 필요 가능성 높음** |

셀프 파워 허브 없이 6개를 물리면 팔로워 동작 중 전압 강하로 **시리얼이 끊긴다.**
이건 디버깅하기 아주 고약한 증상이다.

---

## 6. 첫 텔레옵

```bash
lerobot-teleoperate \
  --robot.type=bi_so_follower \
  --robot.left_arm_config.port=/dev/so101_follower_left \
  --robot.right_arm_config.port=/dev/so101_follower_right \
  --teleop.type=bi_so_leader \
  --teleop.left_arm_config.port=/dev/so101_leader_left \
  --teleop.right_arm_config.port=/dev/so101_leader_right
```

*(정확한 플래그 형태는 현장에서 `--help`로 확인. 중첩 dataclass 인자 표기가
버전에 따라 다를 수 있다.)*

먼저 **카메라 없이** 팔만 움직여 볼 것. 카메라를 같이 켜면 문제가 생겼을 때
원인이 팔인지 카메라인지 구분이 안 된다.

---

## 7. 기록해야 하는 것 (§2.3)

설치가 끝나면 **바뀌면 안 되는 것들**을 기록한다. `G6`(~10/25)에 대조한다.

- [ ] 팔 4개 베이스 위치 마킹 + 사진
- [ ] 지그 위치 마킹 + 사진
- [ ] 조명 위치·밝기 설정 + 사진
- [ ] 카메라 3대 위치·각도 + 사진
- [ ] **카메라 수동 설정값**(노출·WB·포커스) 텍스트로
- [ ] udev 규칙 파일
- [ ] 캘리브레이션 파일 4개
- [ ] USB 어떤 포트에 무엇을 꽂았는지 (라벨링)

---

## 8. 태스크 대상물 — 제일 리드타임이 길다

§2.1은 **FP32 성공률 70–90%**를 요구한다. 너무 쉬우면 INT8도 전부 성공해서
스크리닝 대상이 사라지고(`K2`), 너무 어려우면 FP32가 70% 아래로 떨어진다(`K1`).

따라서 **클리어런스를 조절할 수 있는 대상물이 여러 벌** 필요하다.
양손 작업이면 "한 팔이 들고 다른 팔이 끼우는" 형태다.

이게 없으면 마진 튜닝이 불가능하고, 그러면 §11.1 영상의 핵심 장면
("감사가 차단한 셀은 실패, 통과시킨 셀은 성공")이 **찍히지 않는다.**

---

## 9. 내가(에이전트) 병행할 것

- [ ] 3카메라 × 12-DoF ACT의 export → ONNX → TRT INT8 경로 검증 (하드웨어 불필요)
- [ ] `act_model.py`(`n_cameras=2`, 6-DoF)를 쓰는 기존 스크립트 목록화
- [ ] §2.1/§2.2/§3.1/§5.1 사전등록 개정 초안
