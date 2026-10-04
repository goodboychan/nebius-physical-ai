"""팔로워 관절 하나의 원시값을 실시간 표시하며 최소/최대를 기록한다(읽기 전용).
각도는 현재 캘리브레이션 기준(가운데=0°). 사용: so101_joint_record.py elbow_flex [초]"""
import json, os, sys, time, scservo_sdk as scs
IDS = {"shoulder_pan": 1, "shoulder_lift": 2, "elbow_flex": 3, "wrist_flex": 4, "wrist_roll": 5, "gripper": 6}
joint = sys.argv[1]; secs = float(sys.argv[2]) if len(sys.argv) > 2 else 25
cal = json.load(open(os.path.expanduser("~/.cache/huggingface/lerobot/calibration/robots/so_follower/follower.json")))[joint]
mid = (cal["range_min"] + cal["range_max"]) / 2; deg = lambda r: (r - mid) * 360 / 4095
ph = scs.PortHandler("/dev/so101_follower"); pk = scs.PacketHandler(0)
assert ph.openPort() and ph.setBaudRate(1000000)
pk.write1ByteTxRx(ph, IDS[joint], 40, 0)  # 토크 해제(손으로 움직일 수 있게)
lo, hi = 9999, -1; t0 = time.time(); v = None
while time.time() - t0 < secs:
    r, res, _ = pk.read2ByteTxRx(ph, IDS[joint], 56)
    if res == scs.COMM_SUCCESS:
        v = r; lo, hi = min(lo, v), max(hi, v)
    if v is not None:
        print(f"\r남은 {secs-(time.time()-t0):4.1f}s  현재 {deg(v):+7.1f}°  범위 {deg(lo):+7.1f}° .. {deg(hi):+7.1f}°  (제한 {deg(cal['range_min']):+.1f}..{deg(cal['range_max']):+.1f})  ", end="", flush=True)
    time.sleep(0.05)
ph.closePort()
out = f"{joint} raw min {lo} max {hi}  calib {cal['range_min']}..{cal['range_max']}\ndegrees: {deg(lo):+.1f} .. {deg(hi):+.1f}\n"
open(os.path.expanduser("~/so101_joint_result.txt"), "w").write(out); print("\n" + out)
