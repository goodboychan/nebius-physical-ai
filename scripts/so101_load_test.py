"""텔레옵하면서 팔로워 모터 전류·온도를 기록한다(무게 시험용). 사용: so101_load_test.py [초]
LeRobot 텔레옵과 같은 경로(리더 get_action → 팔로워 send_action)를 30Hz로 돌리고, 5프레임마다 전류·온도를 읽는다."""
import os, sys, time
from lerobot.robots.so_follower import SO101Follower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader
from lerobot.teleoperators.so_leader.config_so_leader import SO101LeaderConfig
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 40
MA = 6.5  # STS3215 Present_Current 1단위 = 6.5mA
fol = SO101Follower(SO101FollowerConfig(port="/dev/so101_follower", id="follower"))
lead = SO101Leader(SO101LeaderConfig(port="/dev/so101_leader", id="leader"))
fol.connect(); lead.connect()
peak = {}; tmax = {}; t0 = time.time(); k = 0; log = []
try:
    while time.time() - t0 < secs:
        t = time.time()
        fol.send_action(lead.get_action())
        if k % 5 == 0:
            cur = fol.bus.sync_read("Present_Current", normalize=False)
            tmp = fol.bus.sync_read("Present_Temperature", normalize=False)
            for m in cur:
                peak[m] = max(peak.get(m, 0), cur[m] * MA); tmax[m] = max(tmax.get(m, 0), tmp[m])
            log.append((round(t - t0, 2), {m: int(cur[m] * MA) for m in cur}, dict(tmp)))
            print("\r" + f"남은 {secs-(t-t0):4.1f}s  " + "  ".join(f"{m[:5]} {cur[m]*MA:4.0f}mA/{tmp[m]}°C" for m in cur), end="", flush=True)
        k += 1
        time.sleep(max(0, 1 / 30 - (time.time() - t)))
finally:
    fol.disconnect(); lead.disconnect()
out = "joint           peak_mA  max_temp_C\n" + "\n".join(f"{m:15s} {peak[m]:7.0f}  {tmax[m]:5d}" for m in peak) + "\n"
open(os.path.expanduser("~/so101_load_result.txt"), "w").write(out + "\n" + "\n".join(map(str, log)))
print("\n" + out)
