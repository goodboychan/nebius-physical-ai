"""오버헤드 노출·WB를 흰 종이 기준으로 고정한다(장면 밝기에 따라 바뀌는 자동 노출과 무관하게)."""
import cv2, subprocess, time, numpy as np
DEV = "/dev/so101_cam_top"; ROI = (slice(320, 430), slice(260, 440))   # 흰 종이 안쪽
def ctl(**kv): subprocess.run(["v4l2-ctl", "-d", DEV, "-c", ",".join(f"{k}={v}" for k, v in kv.items())], check=True)
cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")); cap.set(3, 640); cap.set(4, 480); cap.set(5, 30)
def grab(n=8):
    for _ in range(n): ok, f = cap.read()
    return f
ctl(auto_exposure=1, gain=0, white_balance_automatic=0, white_balance_temperature=5000, focus_automatic_continuous=0, focus_absolute=0)
best = None
for e in (80, 100, 130, 160, 200, 250, 300, 333, 400):
    ctl(exposure_time_absolute=e); f = grab(); p = f[ROI]
    mx = p.max(axis=2); m = float(mx.mean()); clip = float((mx >= 250).mean() * 100)
    print(f"exposure {e:4d}: paper max-channel mean {m:5.1f}, clipped {clip:4.1f}%, whole-frame mean {f.mean():5.1f}")
    if clip < 0.5 and (best is None or abs(m - 205) < abs(best[1] - 205)): best = (e, m)
ctl(exposure_time_absolute=best[0]); print(f"-> exposure {best[0]} (paper {best[1]:.0f})")
bw = None
for wb in range(3000, 6501, 250):
    ctl(white_balance_temperature=wb); f = grab(); b, g, r = [float(c.mean()) for c in cv2.split(f[ROI])]
    d = abs(r / g - 1) + abs(b / g - 1)
    if bw is None or d < bw[1]: bw = (wb, d, r / g, b / g)
ctl(white_balance_temperature=bw[0]); f = grab()
print(f"-> white balance {bw[0]}K (paper R/G {bw[2]:.3f}, B/G {bw[3]:.3f})")
cv2.imwrite("/tmp/top_whiteref.jpg", f); print(f"LOCK exposure_time_absolute={best[0]} white_balance_temperature={bw[0]}")
cap.release()
