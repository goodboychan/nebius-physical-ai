"""두 팔을 같은 자세로 둔 상태에서, LeRobot이 각 관절을 몇 도로 읽는지 비교한다. 읽기 전용.
LeRobot 0.6.1 DEGREES 모드: deg = (raw - (min+max)/2) * 360 / 4095"""
import json, os, scservo_sdk as scs
C = os.path.expanduser("~/.cache/huggingface/lerobot/calibration")
cal = {"leader": json.load(open(f"{C}/teleoperators/so_leader/leader.json")),
       "follower": json.load(open(f"{C}/robots/so_follower/follower.json"))}
ports = {"leader": "/dev/so101_leader", "follower": "/dev/so101_follower"}
names = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
pk = scs.PacketHandler(0)
raw = {}
for k, p in ports.items():
    ph = scs.PortHandler(p)
    assert ph.openPort() and ph.setBaudRate(1000000), p
    raw[k] = {}
    for i, n in enumerate(names, 1):
        vals = sorted(pk.read2ByteTxRx(ph, i, 56)[0] for _ in range(10))
        raw[k][n] = vals[5]
    ph.closePort()

def deg(k, n):
    c = cal[k][n]
    return (raw[k][n] - (c["range_min"] + c["range_max"]) / 2) * 360 / 4095

print("%-14s %9s %10s %8s" % ("joint", "leader", "follower", "diff"))
for n in names:
    d = deg("follower", n) - deg("leader", n)
    mark = "   <--" if abs(d) > 8 else ""
    print("%-14s %8.1f° %9.1f° %7.1f°%s" % (n, deg("leader", n), deg("follower", n), d, mark))
print()
print("raw leader  :", raw["leader"])
print("raw follower:", raw["follower"])
