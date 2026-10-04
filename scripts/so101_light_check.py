"""세션 시작 전 조명 점검. 흰 종이를 책상 기준 위치에 두고, 손목 카메라가 종이를 내려다보게 한 뒤 실행.
기준값은 2026-10-04 고정 당시 측정값. 밝기 ±10%, 색 비율 ±0.05를 벗어나면 FAIL."""
import cv2, numpy as np, subprocess, time
from lerobot.utils.import_utils import register_third_party_plugins; register_third_party_plugins()
from lerobot_camera_openmv import OpenMVCamera, OpenMVCameraConfig
REF = {"top": (211.5, 0.992, 1.001), "wrist": (204.0, 0.991, 0.983)}
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
p = f[320:430, 260:440]; b, g, r = [float(c.mean()) for c in cv2.split(p)]
ok1 = judge("top", float(p.max(axis=2).mean()), r / g, b / g)
cam = OpenMVCamera(OpenMVCameraConfig(fps=30)); cam.connect(); time.sleep(0.5); a = cam.read_latest(max_age_ms=500); cam.disconnect()
mx = a.max(axis=2); m = mx > np.percentile(mx, 60)
r, g, b = [float(a[..., i][m].mean()) for i in range(3)]
ok2 = judge("wrist", g, r / g, b / g)
print("LIGHT CHECK:", "PASS" if ok1 and ok2 else "FAIL — 블라인드·조명 상태를 확인하세요")
