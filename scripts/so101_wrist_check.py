"""손목 카메라 장착 위치 점검. 집게 끝이 화면의 같은 자리에 보이는지를 세션마다 확인한다.
준비: 팔로워 집게를 손으로 끝까지 닫고, 손목 카메라가 검은 책상 매트를 15cm 이상 위에서 내려다보게 한다
(캔·종이 등 밝은 물체는 치운다). 판정은 화면 아래쪽 가운데(집게 끝 영역)만 본다.
사용: so101_wrist_check.py --save-ref   (기준 저장, 장착을 바꿨을 때만)
      so101_wrist_check.py              (세션 점검)
밝은(흰) 집게 영역을 마스크로 뽑아 기준과 겹침(IoU)과 중심 이동(px)을 본다. IoU ≥ 0.80, 이동 ≤ 6px이면 PASS."""
import os, sys, time, cv2, numpy as np, scservo_sdk as scs
from lerobot.utils.import_utils import register_third_party_plugins; register_third_party_plugins()
from lerobot_camera_openmv import OpenMVCamera, OpenMVCameraConfig
D = os.path.expanduser("~/so101_ref"); os.makedirs(D, exist_ok=True)
ph = scs.PortHandler("/dev/so101_follower"); pk = scs.PacketHandler(0)
assert ph.openPort() and ph.setBaudRate(1000000)
grip, res, _ = pk.read2ByteTxRx(ph, 6, 56); ph.closePort(); assert res == scs.COMM_SUCCESS
cam = OpenMVCamera(OpenMVCameraConfig(fps=30)); cam.connect(); time.sleep(0.5)
img = np.median(np.stack([cam.read_latest(max_age_ms=500) for _ in range(5) if not time.sleep(0.1)]), axis=0).astype(np.uint8)
cam.disconnect()
gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
_, mask = cv2.threshold(cv2.GaussianBlur(gray, (5, 5), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
H, W = mask.shape; roi = np.zeros_like(mask); roi[int(H * 0.70):, int(W * 0.60):] = True
mask &= roi  # 닫힌 집게의 흰 몸체가 보이는 오른쪽 아래만 본다. 가운데는 매트의 조명 반사가 들어온다(2026-10-07)
assert mask.sum() > 50, "집게 영역이 안 보입니다. 집게를 끝까지 닫고 다시 실행하세요"
cy, cx = [float(v.mean()) for v in np.nonzero(mask)]
GRIP_CLOSED_MAX = 2080  # 팔로워 집게 캘리브레이션 range_min 2030 근처 = 끝까지 닫힘 (데모 시작 자세의 집게 1.3–1.6%)
if grip > GRIP_CLOSED_MAX:
    print(f"집게 원시값 {grip}: 닫혀 있지 않습니다(닫힘 ≤ {GRIP_CLOSED_MAX}). 집게를 끝까지 닫고 다시 실행하세요"); sys.exit(1)
if "--save-ref" in sys.argv:
    np.savez(f"{D}/wrist_ref.npz", mask=mask, grip=grip, img=img)
    cv2.imwrite(f"{D}/wrist_ref.jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    print(f"기준 저장: 집게 원시값 {grip}, 밝은 영역 {mask.mean()*100:.1f}%, 중심 ({cx:.1f}, {cy:.1f}) -> {D}/wrist_ref.npz")
    sys.exit()
R = np.load(f"{D}/wrist_ref.npz"); rm = R["mask"]
ry, rx = [float(v.mean()) for v in np.nonzero(rm)]
iou = (mask & rm).sum() / max((mask | rm).sum(), 1); shift = float(np.hypot(cx - rx, cy - ry))
over = img.copy(); over[rm & ~mask] = (255, 0, 0); over[mask & ~rm] = (0, 255, 0)
cv2.imwrite(f"{D}/wrist_check_{time.strftime('%m%d_%H%M')}.jpg", cv2.cvtColor(np.hstack([R["img"], img, over]), cv2.COLOR_RGB2BGR))
grip_ok = int(grip) <= GRIP_CLOSED_MAX
ok = iou >= 0.80 and shift <= 6 and grip_ok
print(f"집게 원시값 {grip} (기준 {int(R['grip'])}{'' if grip_ok else ' — 집게를 끝까지 닫으세요'})  IoU {iou:.2f}  중심 이동 {shift:.1f}px  "
      f"(dx {cx-rx:+.1f}, dy {cy-ry:+.1f})")
print("WRIST CHECK:", "PASS" if ok else "FAIL — 카메라 장착이 틀어졌거나 준비 자세가 다릅니다 (빨강=기준에만, 초록=지금만)")
