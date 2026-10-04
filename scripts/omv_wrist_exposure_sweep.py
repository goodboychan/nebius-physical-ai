import faulthandler, time, cv2, numpy as np
faulthandler.dump_traceback_later(240, exit=True)
from lerobot.utils.import_utils import register_third_party_plugins; register_third_party_plugins()
from lerobot_camera_openmv import OpenMVCamera, OpenMVCameraConfig
combos = [(15000, 6), (15000, 12), (15000, 18), (10000, 18), (10000, 24), (6000, 24)]
tiles = []
for exp, g in combos:
    t = time.time()
    cam = OpenMVCamera(OpenMVCameraConfig(fps=30, exposure_us=exp, gain_db=g, warmup_s=1.5)); cam.connect()
    time.sleep(0.5); a = cam.read_latest(max_age_ms=500); cam.disconnect()
    mx = a.max(axis=2)
    print(f"exp {exp/1000:4.1f}ms gain {g:2d}dB  mean {a.mean():5.1f}  saturated {(mx>=250).mean()*100:5.1f}%  dark(<=15) {(mx<=15).mean()*100:5.1f}%  p99 {np.percentile(mx,99):.0f}   (session {time.time()-t:.0f}s)", flush=True)
    tile = cv2.cvtColor(a, cv2.COLOR_RGB2BGR).copy()
    cv2.putText(tile, f"{exp/1000:.0f}ms {g}dB", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    tiles.append(tile)
cv2.imwrite("/tmp/wrist_sweep.jpg", np.vstack([np.hstack(tiles[0:3]), np.hstack(tiles[3:6])]))
print("saved")
