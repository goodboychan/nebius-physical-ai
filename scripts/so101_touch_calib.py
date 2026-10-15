"""Touch calibration for the Isaac Sim twin (sim/README.md, phase 1). Run on the Orin, with the robot idle (no block).
The leader drives the follower at 30 Hz, as in lerobot-teleoperate. For each point, bring the closed gripper's tip down
until it just touches the point on the table, then press Enter: the follower state is averaged over 0.5 s and saved.
Points (the order is printed as you go):
  G1..G9   a 3x3 grid of dots 5 cm apart on a taped-down A4 sheet (G1 top-left as seen from the robot, row by row)
  B1F..B9K the cola can stood on corner dot 1, 3, 7, 9: touch the centre of its top twice, wrist tilted forward (F), then back (K)
  START    the centre of the training start mark      COASTER  the centre of the coaster
At the end the arm goes back to rest and one overhead frame is saved (the grid, start mark and coaster must be visible).
Output: ~/edgeqgate/touch_calib/<time>/touch.json and overhead.png
Usage: ~/lerobot-env/.venv/bin/python so101_touch_calib.py"""
import json, os, select, subprocess, sys, time
import cv2, numpy as np
from lerobot.robots.so_follower import SO101Follower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader
from lerobot.teleoperators.so_leader.config_so_leader import SO101LeaderConfig

POINTS = [f"G{i}" for i in range(1, 10)] + [f"B{i}{w}" for i in (1, 3, 7, 9) for w in "FK"] + ["START", "COASTER"]
CAN_H = 0.115   # unopened cola can height, m
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
out = os.path.expanduser(f"~/edgeqgate/touch_calib/{time.strftime('%m%d_%H%M%S')}"); os.makedirs(out, exist_ok=True)
fol = SO101Follower(SO101FollowerConfig(port="/dev/so101_follower", id="follower"))
lead = SO101Leader(SO101LeaderConfig(port="/dev/so101_leader", id="leader"))
fol.connect(); lead.connect()
rec, i, buf = [], 0, []
print(f"리더로 집게 끝을 [{POINTS[0]}]에 살짝 닿게 한 뒤 Enter (건너뛰기: s Enter, 끝내기: q Enter)", flush=True)
try:
    while i < len(POINTS):
        t = time.time(); fol.send_action(lead.get_action())
        obs = fol.get_observation(); buf.append([obs[f"{j}.pos"] for j in J]); buf = buf[-15:]
        if select.select([sys.stdin], [], [], 0)[0]:
            k = sys.stdin.readline().strip().lower()
            if k == "q": break
            if k != "s":
                q = np.array(buf); rec.append({"point": POINTS[i], "state_deg_mean": q.mean(0).round(3).tolist(), "state_deg_std": q.std(0).round(3).tolist(), "t": time.time()})
                print(f"  {POINTS[i]} 기록: " + " ".join(f"{v:.1f}" for v in q.mean(0)), flush=True)
            i += 1
            if i < len(POINTS): print(f"다음: [{POINTS[i]}]", flush=True)
        time.sleep(max(0, 1 / 30 - (time.time() - t)))
    print("팔을 쉬는 자세로 돌려놓고 Enter (오버헤드 사진을 찍는다)", flush=True)
    while not select.select([sys.stdin], [], [], 0)[0]:
        t = time.time(); fol.send_action(lead.get_action()); time.sleep(max(0, 1 / 30 - (time.time() - t)))
    sys.stdin.readline()
finally:
    json.dump({"points": rec, "units": "LeRobot degrees; gripper 0-100", "grid_spacing_m": float(os.environ.get("GRID_M", "0.03")), "block_height_m": CAN_H}, open(f"{out}/touch.json", "w"), indent=1)
    for dev in (fol, lead):
        try: dev.disconnect()
        except Exception as e: print("disconnect:", type(e).__name__)
subprocess.run(["/usr/local/bin/so101-cam-lock", "/dev/so101_cam_top"], capture_output=True)
cap = cv2.VideoCapture("/dev/so101_cam_top"); cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
for _ in range(30): ok, f = cap.read()
if ok: cv2.imwrite(f"{out}/overhead.png", f)
cap.release(); print("저장:", out, "| 점", len(rec), "| 사진", "ok" if ok else "실패")
