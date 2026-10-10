"""팔로워 모터 6개의 온도·전압·부하·전류·상태를 읽는다(읽기 전용, 토크를 건드리지 않는다). 실행기가 포트를 쓰지 않을 때 돌린다."""
import scservo_sdk as scs
NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
ph = scs.PortHandler("/dev/so101_follower"); pk = scs.PacketHandler(0)
assert ph.openPort() and ph.setBaudRate(1000000)
for i, n in enumerate(NAMES, 1):
    t, r1, _ = pk.read1ByteTxRx(ph, i, 63); v, _, _ = pk.read1ByteTxRx(ph, i, 62); st, _, _ = pk.read1ByteTxRx(ph, i, 65)
    ld, _, _ = pk.read2ByteTxRx(ph, i, 60); cu, _, _ = pk.read2ByteTxRx(ph, i, 69); tq, _, _ = pk.read1ByteTxRx(ph, i, 40)
    ok = r1 == scs.COMM_SUCCESS
    print(f"{n:14s} " + (f"temp {t:3d}°C  volt {v/10:4.1f}V  load {ld & 0x3ff:4d}  current {cu*6.5:6.0f}mA  status 0x{st:02x}  torque {tq}" if ok else "응답 없음"))
ph.closePort()
