"""접은 자세(기계적 정지점) 기준으로 리더 0점을 팔로워에 맞춘다. 범위는 실측값을 모두 포함하도록 넓힌다."""
import json, os
f = os.path.expanduser("~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/leader.json")
F = json.load(open(os.path.expanduser("~/.cache/huggingface/lerobot/calibration/robots/so_follower/follower.json")))
d = json.load(open(f))
meas = {"shoulder_lift": (667, 785), "elbow_flex": (3043, 3554)}   # (리더 raw, 팔로워 raw) — 접은 자세
for j, (lr, fr) in meas.items():
    fmid = (F[j]["range_min"] + F[j]["range_max"]) / 2
    w = d[j]; old = (w["range_min"], w["range_max"])
    mid = lr - (fr - fmid)
    lo, hi = min(old[0], lr), max(old[1], lr)
    half = max(mid - lo, hi - mid)
    w["range_min"], w["range_max"] = int(round(mid - half)), int(round(mid + half))
    assert 0 <= w["range_min"] and w["range_max"] <= 4095, (j, w)
    nm = (w["range_min"] + w["range_max"]) / 2
    print("%-14s %s -> (%d, %d)  mid %.1f -> %.1f  shift %+.1f deg | folded: leader %.1f, follower %.1f deg" % (
        j, old, w["range_min"], w["range_max"], sum(old)/2, nm, (nm - sum(old)/2) * 360 / 4095,
        (lr - nm) * 360 / 4095, (fr - fmid) * 360 / 4095))
json.dump(d, open(f, "w"), indent=4)
