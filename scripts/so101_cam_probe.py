"""오버헤드 카메라: 자동 상태 기준 밝기를 잰 뒤, 수동 노출·초점 후보를 훑어 고정값을 고른다."""
import cv2, subprocess, time, numpy as np, sys
DEV = "/dev/so101_cam_top"
def ctl(**kv):
    subprocess.run(["v4l2-ctl", "-d", DEV, "-c", ",".join(f"{k}={v}" for k, v in kv.items())], check=True)
cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480); cap.set(cv2.CAP_PROP_FPS, 30)
def grab(n=8):
    f = None
    for _ in range(n): ok, f = cap.read()
    return f
def bright(f): return float(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean())
def sharp(f): return float(cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
fourcc = int(cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode()
print(f"stream: {int(cap.get(3))}x{int(cap.get(4))} @ {cap.get(5):.0f}fps {fourcc}")
# 1) 자동 상태: 노출이 수렴하도록 2초 흘린다
ctl(auto_exposure=3, white_balance_automatic=1, focus_automatic_continuous=1)
t = time.time()
while time.time() - t < 2.5: cap.read()
fa = grab(); b_auto = bright(fa); s_auto = sharp(fa)
cv2.imwrite("/tmp/cam_auto.jpg", fa)
print(f"auto: brightness {b_auto:.1f}, sharpness {s_auto:.0f}")
# 2) 수동 노출 훑기 (자동 밝기에 가장 가까운 값)
ctl(auto_exposure=1, gain=0)
best = None
for e in (50, 80, 120, 160, 200, 250, 333, 400, 500, 650, 800):
    ctl(exposure_time_absolute=e); fr = grab(); b = bright(fr)
    d = abs(b - b_auto)
    if best is None or d < best[1]: best = (e, d, b)
print(f"exposure pick: {best[0]} (brightness {best[2]:.1f} vs auto {b_auto:.1f})")
ctl(exposure_time_absolute=best[0])
# 3) 화이트밸런스: 자동 상태에서 고정 → 현재 온도값 그대로 쓰지 못하므로 4000K 기준으로 회색 균형이 가장 가까운 값
fa_b, fa_g, fa_r = [float(c.mean()) for c in cv2.split(fa)]
ctl(white_balance_automatic=0); bestw = None
for wb in range(3000, 6501, 500):
    ctl(white_balance_temperature=wb); fr = grab()
    b_, g_, r_ = [float(c.mean()) for c in cv2.split(fr)]
    d = abs((r_ / max(g_, 1)) - (fa_r / max(fa_g, 1))) + abs((b_ / max(g_, 1)) - (fa_b / max(fa_g, 1)))
    if bestw is None or d < bestw[1]: bestw = (wb, d)
print(f"white balance pick: {bestw[0]}K")
ctl(white_balance_temperature=bestw[0])
# 4) 초점: 선명도 최대
ctl(focus_automatic_continuous=0); bestf = None
for fv in range(0, 251, 25):
    ctl(focus_absolute=fv); time.sleep(0.3); fr = grab(); s = sharp(fr)
    if bestf is None or s > bestf[1]: bestf = (fv, s)
print(f"focus pick: {bestf[0]} (sharpness {bestf[1]:.0f} vs auto {s_auto:.0f})")
ctl(focus_absolute=bestf[0]); time.sleep(0.3)
fl = grab(); cv2.imwrite("/tmp/cam_locked.jpg", fl)
print(f"locked: brightness {bright(fl):.1f}, sharpness {sharp(fl):.0f}")
print(f"LOCK exposure_time_absolute={best[0]} white_balance_temperature={bestw[0]} focus_absolute={bestf[0]}")
cap.release()
