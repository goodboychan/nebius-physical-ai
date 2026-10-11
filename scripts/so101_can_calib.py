"""스트레스 S4 캔의 판정 값 측정 (docs/stress_test_protocol.md §4). 정책 결과와 무관한, 시험 전 측정이다.
새 캔을 **빈 컵받침 가운데에 똑바로 세우고** 손을 화면 밖으로 뺀 뒤 실행한다.

- 오버헤드 30프레임에서 밝은 원(캔 윗면)을 넓은 범위(10–40px)로 찾는다. 컵받침 원(약 35px)은 컵받침 중심에 있고, 캔 윗면은
  원근 때문에 그보다 화면 위쪽에 보이므로 '컵받침 중심보다 위쪽, 가장 가까운 밝은 원'을 고른다
- 원근 보정 = 컵받침 중심 − 윗면 중심(중앙값). 반지름 범위 = 콜라캔 규칙과 같은 비율:
  콜라캔 윗면 중앙값 20.9px(RETEST 마지막 프레임 30장)에 잠금 범위 17–28 → [0.81r, 1.34r]
- 결과를 판정기로 다시 돌려 '성공·바닥 거리 ≤ 5px'인지 확인하고 stress_can_S4.json에 쓴다
사용: so101_can_calib.py <출력 json>"""
import json, subprocess, sys
import cv2, numpy as np
from judge_success import COASTER_XY, judge

subprocess.run(["/usr/local/bin/so101-cam-lock", "/dev/so101_cam_top"], capture_output=True)
cap = cv2.VideoCapture("/dev/so101_cam_top", cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")); cap.set(3, 640); cap.set(4, 480)
fr = [cap.read()[1] for _ in range(45)][-30:]; cap.release()
grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in fr]
tops = []
for g in grays:
    cs = cv2.HoughCircles(cv2.medianBlur(g, 5), cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=100, param2=22, minRadius=10, maxRadius=40)
    if cs is None: continue
    cand = []
    for x, y, r in cs[0]:
        m = np.zeros_like(g); cv2.circle(m, (int(x), int(y)), int(r * 0.7), 255, -1)
        b = float(g[m > 0].mean()); dy = COASTER_XY[1] - y
        if b > 90 and 5 <= dy <= 80 and abs(x - COASTER_XY[0]) <= 30: cand.append((np.hypot(x - COASTER_XY[0], dy), x, y, r, b))
    if cand: tops.append(min(cand)[1:])
if len(tops) < 20:
    print(f"CAN CALIB: FAIL — 윗면 원을 {len(tops)}/30 프레임에서만 찾았습니다. 캔이 컵받침 가운데에 서 있는지, 손이 빠졌는지 확인"); sys.exit(1)
t = np.array(tops); x, y, r, b = np.median(t, axis=0)
off = [round(float(COASTER_XY[0] - x), 1), round(float(COASTER_XY[1] - y), 1)]
rr = [int(np.floor(0.81 * r)), int(np.ceil(1.34 * r))]
prof = {"can": "yellow 175 ml, 190 g, 50 mm x 10 cm", "r_top_median_px": round(float(r), 1), "r_top_range_seen": [round(float(t[:, 2].min()), 1), round(float(t[:, 2].max()), 1)],
        "top_xy_median": [round(float(x), 1), round(float(y), 1)], "brightness_median": round(float(b)), "n_frames": len(tops),
        "r_range": rr, "top_to_base": off, "rule": "offset = coaster centre - top centre; r_range = [floor(0.81 r), ceil(1.34 r)] (cola-can ratios)"}
j = judge(grays[-15:], 0.0, prof)
prof["self_check"] = j
print(json.dumps(prof, ensure_ascii=False, indent=1))
ok = j["success"] and j["base_dist_px"] <= 5
print("CAN CALIB:", "PASS" if ok else "FAIL — 판정기가 가운데 선 캔을 성공으로 보지 못합니다. 결과를 알려주세요")
if ok: json.dump(prof, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
