"""AE3 → Orin 전송 속도 조정 시험: 패킷 크기와 원시(raw) 스트림 비교."""
import time, sys
from openmv import Camera
SCRIPT = r'''
import csi
c = csi.CSI()
c.reset(); c.pixformat(csi.RGB565); c.framesize(csi.VGA); c.snapshot(time=1000)
c.auto_gain(False, gain_db=6.0); c.auto_whitebal(False); c.auto_exposure(False, exposure_us=15000)
while True:
    c.snapshot()
'''
def trial(label, max_payload, raw=False, res=None, secs=10):
    cam = Camera("/dev/so101_cam_wrist_omv", timeout=2.0, max_payload=max_payload)
    cam.connect()
    try:
        cam.update_capabilities(max_payload=max_payload)
    except Exception as e:
        pass
    cam.exec(SCRIPT); time.sleep(2.0)
    cam.streaming(True, raw=raw, resolution=res)
    n = 0; nbytes = 0; t0 = time.time(); shape = None
    while time.time() - t0 < secs:
        f = cam.read_frame()
        if f is not None:
            n += 1; nbytes += f.get("raw_size") or 0; shape = (f["width"], f["height"], f["format"])
    cam.streaming(False); cam.stop(); cam.disconnect(); time.sleep(0.5)
    print(f"{label:28s} {n/secs:5.1f} fps  frame={shape}  avg_wire={nbytes/max(n,1)/1024:6.1f} KB")
for mp in (4096, 16384, 32768):
    trial(f"jpeg max_payload={mp}", mp)
trial("raw 640x400 mp=32768", 32768, raw=True, res=(640, 400))
trial("raw 320x200 mp=32768", 32768, raw=True, res=(320, 200))
