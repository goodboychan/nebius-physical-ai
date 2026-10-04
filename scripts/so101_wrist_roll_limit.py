"""팔로워 wrist_roll을 케이블 안전 범위로 제한한다.
LeRobot은 같은 range로 모터 제한과 각도 0점(가운데)을 함께 정하므로, 팔로워 가운데가 옮겨지는 만큼
리더 가운데도 같은 원시값만큼 옮겨 두 팔의 각도 대응을 그대로 유지한다."""
import json, os
C = os.path.expanduser("~/.cache/huggingface/lerobot/calibration")
fp, lp = f"{C}/robots/so_follower/follower.json", f"{C}/teleoperators/so_leader/leader.json"
F, L = json.load(open(fp)), json.load(open(lp))
safe_lo, safe_hi = 818, 2849            # 2026-10-04 실측: 케이블이 팽팽해지기 직전
margin = round(10 * 4095 / 360)         # 양쪽 10° 안쪽으로
f_old = (F["wrist_roll"]["range_min"], F["wrist_roll"]["range_max"]); l_old = (L["wrist_roll"]["range_min"], L["wrist_roll"]["range_max"])
F["wrist_roll"]["range_min"], F["wrist_roll"]["range_max"] = safe_lo + margin, safe_hi - margin
shift = (F["wrist_roll"]["range_min"] + F["wrist_roll"]["range_max"]) / 2 - sum(f_old) / 2
l_mid = sum(l_old) / 2 + shift
half = min(l_mid, 4095 - l_mid)
L["wrist_roll"]["range_min"], L["wrist_roll"]["range_max"] = int(round(l_mid - half)), int(round(l_mid + half))
assert abs((L["wrist_roll"]["range_min"] + L["wrist_roll"]["range_max"]) / 2 - l_mid) <= 0.5
json.dump(F, open(fp, "w"), indent=4); json.dump(L, open(lp, "w"), indent=4)
deg = lambda t: t * 360 / 4095
fm = (F["wrist_roll"]["range_min"] + F["wrist_roll"]["range_max"]) / 2
print(f"follower wrist_roll {f_old} -> ({F['wrist_roll']['range_min']}, {F['wrist_roll']['range_max']})  "
      f"= {deg(F['wrist_roll']['range_min'] - fm):+.1f}..{deg(F['wrist_roll']['range_max'] - fm):+.1f} deg around new zero")
print(f"leader   wrist_roll {l_old} -> ({L['wrist_roll']['range_min']}, {L['wrist_roll']['range_max']})  mid shift {deg(shift):+.1f} deg (same as follower)")
