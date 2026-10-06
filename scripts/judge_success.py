"""성공 판정기 (`docs/success_criterion.md` §3, 2026-10-07 잠금 값). 오버헤드 영상의 마지막 0.5초(15프레임)와 마지막 관절 상태로 판정한다.

기하 기준(오버헤드 640×480, 고정 카메라):
- 컵받침(목표 영역): 중심 COASTER_XY, 반지름 COASTER_R px — 빈 컵받침 프레임에서 원 검출로 잰 값
- 캔 윗면 원(반지름 CAN_R_RANGE px)을 찾고, 원근 보정(CAN_TOP_TO_BASE: 윗면 중심 → 바닥 중심, 캔 높이 때문에 생김)을 더해
  바닥 중심을 구한다. 바닥 중심이 목표 영역 안이면 '안'
- 서 있음: 윗면 원이 검출됨(누우면 윗면이 원으로 보이지 않는다)
- 정지: 마지막 15프레임 동안 윗면 중심 이동 ≤ STILL_PX
- 놓음은 자동 판정하지 않는다: 집게 값만으로는 '활짝 연 채 떠남'(데모 ep000: 52.8)과 '쥐고 있음'을 가를 수 없다.
  블라인드 판정자가 마지막 프레임에서 집게가 캔에 닿아 있는지 본다(§3)
사용(컨테이너): python judge_success.py <데이터셋> [에피소드...]  → 에피소드별 판정"""
import glob, json, sys
import av, cv2, numpy as np, pandas as pd

COASTER_XY = (395.0, 377.0); COASTER_R = 35.0
CAN_R_RANGE = (17, 28); CAN_TOP_TO_BASE = (0.0, 32.0)
STILL_PX = 8.0; LAST_N = 15

def can_top(gray):
    g = cv2.medianBlur(gray, 5)
    cs = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=100, param2=22,
                          minRadius=CAN_R_RANGE[0], maxRadius=CAN_R_RANGE[1])
    if cs is None: return None
    # 밝은(알루미늄) 원 중 '컵받침 가운데에 선 캔의 윗면 위치'에 가장 가까운 것. 가장 밝은 원을 고르면 흰 집게를 잡는다
    ex, ey = COASTER_XY[0] - CAN_TOP_TO_BASE[0], COASTER_XY[1] - CAN_TOP_TO_BASE[1]
    best = None
    for x, y, r in cs[0]:
        m = np.zeros_like(gray); cv2.circle(m, (int(x), int(y)), int(r * 0.7), 255, -1)
        b = float(gray[m > 0].mean()); dist = float(np.hypot(x - ex, y - ey))
        if b > 90 and dist <= 150 and (best is None or dist < best[3]): best = (float(x), float(y), float(r), dist)
    return best

def judge(frames_gray, grip_last):
    tops = [can_top(g) for g in frames_gray]
    if any(t is None for t in tops):
        return {"success": False, "reason": "can_top_not_found(fallen_or_occluded)"}
    xy = np.array([(t[0], t[1]) for t in tops]); med = np.median(xy, axis=0); move = float(np.linalg.norm(xy - med, axis=1).max())  # 원 검출 흔들림(3–6px)을 감안해 중앙값 기준
    bx, by = med[0] + CAN_TOP_TO_BASE[0], med[1] + CAN_TOP_TO_BASE[1]
    dist = float(np.hypot(bx - COASTER_XY[0], by - COASTER_XY[1]))
    inside, still = dist <= COASTER_R, move <= STILL_PX
    ok = inside and still
    reason = "ok" if ok else ",".join(n for n, v in [("outside", inside), ("moving", still)] if not v)
    return {"success": ok, "reason": reason, "base_dist_px": round(dist, 1), "move_px": round(move, 1), "grip": round(float(grip_last), 1)}

if __name__ == "__main__":
    args = sys.argv[1:]; at_start = "--at-start" in args  # 음성 대조: 캔이 시작 표시에 있는 첫 0.5초는 실패여야 한다
    args = [a for a in args if a != "--at-start"]; root = args[0]
    cat = lambda pat: pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(pat))], ignore_index=True)
    e = cat(f"{root}/meta/episodes/chunk-*/file-*.parquet"); d = cat(f"{root}/data/chunk-*/file-*.parquet")
    eps = [int(x) for x in args[1:]] or sorted(e.episode_index)
    V = "videos/observation.images.top"; res = {}
    for vf, grp in e[e.episode_index.isin(eps)].groupby([f"{V}/chunk_index", f"{V}/file_index"]):
        c = av.open(f"{root}/{V}/chunk-{vf[0]:03d}/file-{vf[1]:03d}.mp4"); st = c.streams.video[0]
        allf = [(float(f.pts * st.time_base), f) for f in c.decode(st)]
        for _, r in grp.iterrows():
            b = r[f"{V}/to_timestamp"]
            if at_start:
                a0 = r[f"{V}/from_timestamp"]
                last = [f.to_ndarray(format="gray") for t, f in allf if a0 - 1e-3 <= t < a0 + (LAST_N - 0.5) / 30]
            else:
                last = [f.to_ndarray(format="gray") for t, f in allf if b - (LAST_N + 0.5) / 30 <= t < b - 1e-3][-LAST_N:]
            g = np.stack(d[d.episode_index == r["episode_index"]]["observation.state"].to_numpy())[-1, 5]
            res[int(r["episode_index"])] = judge(last, g)
    n = sum(v["success"] for v in res.values())
    print(f"success {n}/{len(res)}")
    for k, v in sorted(res.items()):
        if v["success"] != (not at_start): print(k, v)
    print("base_dist_px max", max(v.get("base_dist_px", -1) for v in res.values()))
    json.dump(res, open("/tmp/judge.json", "w"))
