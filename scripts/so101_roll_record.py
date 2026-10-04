"""팔로워 wrist_roll 원시값을 실시간 표시하며 기록한다(읽기 전용). 결과는 ~/so101_roll_result.txt에도 저장."""
import time, sys, os, scservo_sdk as scs
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 25
ph = scs.PortHandler("/dev/so101_follower"); pk = scs.PacketHandler(0)
assert ph.openPort() and ph.setBaudRate(1000000)
lo, hi = 9999, -1; t0 = time.time(); v = 0
while time.time() - t0 < secs:
    r, res, _ = pk.read2ByteTxRx(ph, 5, 56)
    if res == scs.COMM_SUCCESS:
        v = r; lo, hi = min(lo, v), max(hi, v)
    left = secs - (time.time() - t0)
    print(f"\r남은 {left:4.1f}s  현재 {(v-2047.5)*360/4095:+7.1f}°   범위 {(lo-2047.5)*360/4095:+7.1f}° .. {(hi-2047.5)*360/4095:+7.1f}°   ", end="", flush=True)
    time.sleep(0.05)
ph.closePort()
out = f"wrist_roll raw min {lo} max {hi}\ndegrees from mid: {(lo-2047.5)*360/4095:+.1f} .. {(hi-2047.5)*360/4095:+.1f}\n"
open(os.path.expanduser("~/so101_roll_result.txt"), "w").write(out); print("\n" + out)
