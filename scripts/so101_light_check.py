"""세션 시작 전 조명 점검. 흰 종이(A4)를 팔 앞 책상 위에 두고, 손목 카메라가 종이를 내려다보게 한 뒤 실행.
기준값: 손목은 2026-10-04 고정 당시, 오버헤드는 2026-10-06 종이 위치 표시 후 측정값. 밝기 ±10%, 색 비율 ±0.05를 벗어나면 FAIL."""
import cv2, numpy as np, subprocess, time
from lerobot.utils.import_utils import register_third_party_plugins; register_third_party_plugins()
from lerobot_camera_openmv import OpenMVCamera, OpenMVCameraConfig
# top: 2026-10-06 종이 위치(팔 앞, 컵받침 왼쪽 위; 모서리 테이프 표시)에서 다시 잰 값. 같은 조명에서 손목은 10/4 기준과 +1.5%로 일치
REF = {"top": (191.7, 0.997, 1.003), "wrist": (204.0, 0.991, 0.983)}
def judge(name, level, rg, bg):
    L, R, B = REF[name]
    ok = abs(level / L - 1) <= 0.10 and abs(rg - R) <= 0.05 and abs(bg - B) <= 0.05
    print(f"{name:5s} paper level {level:6.1f} (ref {L:.0f}, {100*(level/L-1):+.1f}%)  R/G {rg:.3f} (ref {R})  B/G {bg:.3f} (ref {B})  -> {'PASS' if ok else 'FAIL'}")
    return ok
subprocess.run(["/usr/local/bin/so101-cam-lock", "/dev/so101_cam_top"], check=True, capture_output=True)
cap = cv2.VideoCapture("/dev/so101_cam_top", cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")); cap.set(3, 640); cap.set(4, 480); cap.set(5, 30)
for _ in range(15): ok, f = cap.read()
cap.release()
# 종이 위치가 세션마다 조금씩 달라도 되도록, 가장 큰 밝은 영역(종이)을 찾아 안쪽만 잰다
gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
_, bw = cv2.threshold(cv2.GaussianBlur(gray, (7, 7), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
bw[:200, :] = 0; bw[:, :180] = 0  # 책상 영역만 본다(왼쪽 벽·위쪽 선반 제외)
n, lab, st, _ = cv2.connectedComponentsWithStats(bw)
k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
paper = cv2.erode((lab == k).astype(np.uint8), np.ones((25, 25), np.uint8)) > 0
assert paper.sum() > 3000, "오버헤드 화면에서 흰 종이를 찾지 못했습니다"
b, g, r = [float(f[..., i][paper].mean()) for i in range(3)]
ok1 = judge("top", float(f.max(axis=2)[paper].mean()), r / g, b / g)
cam = OpenMVCamera(OpenMVCameraConfig(fps=30)); cam.connect(); time.sleep(0.5); a = cam.read_latest(max_age_ms=500); cam.disconnect()
mx = a.max(axis=2); m = mx > np.percentile(mx, 60)
r, g, b = [float(a[..., i][m].mean()) for i in range(3)]
ok2 = judge("wrist", g, r / g, b / g)
print("LIGHT CHECK:", "PASS" if ok1 and ok2 else "FAIL — 블라인드·조명 상태를 확인하세요")
