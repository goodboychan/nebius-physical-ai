"""리더 관절의 0점(기록 범위 가운데)을 옮겨, 같은 자세에서 리더와 팔로워가 같은 각도로 읽히게 한다."""
import json, os, sys
f = os.path.expanduser("~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/leader.json")
d = json.load(open(f))
# joint: (정렬 자세의 리더 원시값, 팔로워 원시값, 팔로워 기록 범위 가운데)
fix = {
    "shoulder_lift": (2186, 3155, (2045 + 3837) / 2),
    "elbow_flex":    (2003, 1399, (459 + 2165) / 2),
}
for j, (lr, fr, fmid) in fix.items():
    w = d[j]
    old = (w["range_min"], w["range_max"])
    mid = lr - (fr - fmid)
    half = max(mid - old[0], old[1] - mid)      # 실측 범위를 모두 포함
    w["range_min"], w["range_max"] = int(round(mid - half)), int(round(mid + half))
    assert 0 <= w["range_min"] and w["range_max"] <= 4095, (j, w)
    newmid = (w["range_min"] + w["range_max"]) / 2
    print("%-14s %s -> (%d, %d)  mid %.1f -> %.1f  | 정렬 자세: leader %.1f deg, follower %.1f deg" % (
        j, old, w["range_min"], w["range_max"], sum(old) / 2, newmid,
        (lr - newmid) * 360 / 4095, (fr - fmid) * 360 / 4095))
json.dump(d, open(f, "w"), indent=4)
