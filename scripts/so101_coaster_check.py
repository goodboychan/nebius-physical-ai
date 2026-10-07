"""세션 시작 전 컵받침·카메라 위치 점검 (`docs/success_criterion.md` §3). 컵받침을 비우고(캔 없음) 실행한다.
빈 컵받침 원을 검출해 잠금 좌표 (395, 377) r 35와 비교한다. 중심 ±3px, 반지름 ±2px 안이면 PASS. 벗어나면 그 세션은 trial을 하지 않는다."""
import subprocess, cv2, numpy as np
REF = (395.0, 377.0, 35.0)
subprocess.run(["/usr/local/bin/so101-cam-lock", "/dev/so101_cam_top"], capture_output=True)
cap = cv2.VideoCapture("/dev/so101_cam_top", cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")); cap.set(3, 640); cap.set(4, 480)
fr = [cap.read()[1] for _ in range(20)][-5:]; cap.release()
found = []
for f in fr:
    g = cv2.medianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), 5)
    cs = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=40, param1=100, param2=30, minRadius=25, maxRadius=60)
    if cs is not None:
        best = min(cs[0], key=lambda c: np.hypot(c[0] - REF[0], c[1] - REF[1]))
        if np.hypot(best[0] - REF[0], best[1] - REF[1]) < 40: found.append(best)
if not found:
    print("COASTER CHECK: FAIL — 컵받침 원을 찾지 못했습니다(캔을 치웠는지 확인)"); raise SystemExit(1)
x, y, r = np.median(np.array(found), axis=0)
ok = np.hypot(x - REF[0], y - REF[1]) <= 3 and abs(r - REF[2]) <= 2
print(f"컵받침 중심 ({x:.1f}, {y:.1f}) r {r:.1f}  (기준 {REF[:2]} r {REF[2]})  이동 {np.hypot(x-REF[0], y-REF[1]):.1f}px")
print("COASTER CHECK:", "PASS" if ok else "FAIL — 컵받침이나 카메라가 움직였습니다. 오늘은 trial을 하지 마세요")
