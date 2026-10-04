"""AE3 스트리밍 시험: 수동 노출로 촬영, Protocol V2 스트림으로 Orin에서 받기."""
import time, sys, numpy as np
from openmv import Camera
CAM_SCRIPT = r'''
import csi, time
c = csi.CSI()
c.reset()
c.pixformat(csi.RGB565)
c.framesize(csi.VGA)
c.snapshot(time=1500)
c.auto_gain(False)
c.auto_whitebal(False)
c.auto_exposure(False, exposure_us=%d)
c.snapshot(time=500)
print("exposure_us", c.exposure_us(), "gain_db", c.gain_db(), "size", c.width(), c.height())
clock = time.clock()
n = 0
while True:
    clock.tick()
    c.snapshot()
    n += 1
    if n %% 60 == 0:
        print("cam_fps", clock.fps())
'''
exp = int(sys.argv[1]) if len(sys.argv) > 1 else 15000
cam = Camera("/dev/so101_cam_wrist_omv", timeout=2.0)
cam.connect()
print("version:", cam.version())
cam.exec(CAM_SCRIPT % exp)
time.sleep(2.5)
cam.streaming(True)
t0 = time.time(); n = 0; last = None; ts = []
while time.time() - t0 < 15:
    f = cam.read_frame()
    if f is not None:
        n += 1; last = f; ts.append(time.time())
out = cam.read_stdout()
cam.streaming(False); cam.stop(); cam.disconnect()
print("stdout:", (out or "").strip().replace("\n", " | ")[-300:])
gaps = np.diff(ts) * 1000 if len(ts) > 1 else [0]
print(f"host frames {n} in 15s -> {n/15:.1f} fps, gap median {np.median(gaps):.0f} ms max {np.max(gaps):.0f} ms")
print("frame type:", type(last), (getattr(last, 'shape', None) or (len(last) if last is not None else None)))
if isinstance(last, dict):
    print("keys:", list(last.keys()))
import pickle; pickle.dump(last, open("/tmp/omv_last.pkl", "wb"))
