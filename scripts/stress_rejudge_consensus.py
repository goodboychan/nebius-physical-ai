"""Stress v2 re-judge, amendment v2-3 (protocol §11): consensus circle tracking. Fixed before any stress v2 cell result
was unsealed, and blind to cells.

Why: under the §9 rule (pick the circle nearest the expected top position in each frame, ≤ 3/15 outliers),
24 of 48 S4 trials fail as "moving". The operator saw all 48 succeed. A bright circle on the coaster rim or logo, near
(399, 365), wins in 4–7 of the 15 frames. With the shorter yellow can the expected top sits close to that spot.

Rule: the same Hough detector, brightness threshold, radius range and offsets as the locked judge, but frames are not
judged one by one.
  1. Collect every candidate circle in the last 15 frames.
  2. The **consensus** position is the candidate with the most frames that have a candidate within 8 px of it. A tie
     goes to the candidate nearest the expected top.
  3. Standing and still: at least 12 of 15 frames have a candidate within 8 px of the consensus (the same ≤ 3/15
     tolerance as §9).
  4. Inside: consensus median + offset is within 35 px of the coaster center.
  5. No candidates at all (fallen or out of view) is a failure, as before.
Usage: python stress_rejudge_consensus.py <trials dir> <out.json> [can_profile.json]"""
import glob, json, os, sys
import av, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from judge_success import COASTER_XY, COASTER_R, CAN_R_RANGE, CAN_TOP_TO_BASE, STILL_PX, LAST_N

def candidates(gray, rr, off):
    cs = cv2.HoughCircles(cv2.medianBlur(gray, 5), cv2.HOUGH_GRADIENT, dp=1.2, minDist=20, param1=100, param2=22, minRadius=rr[0], maxRadius=rr[1])
    if cs is None: return []
    ex, ey = COASTER_XY[0] - off[0], COASTER_XY[1] - off[1]; out = []
    for x, y, r in cs[0]:
        m = np.zeros_like(gray); cv2.circle(m, (int(x), int(y)), int(r * 0.7), 255, -1)
        if float(gray[m > 0].mean()) > 90 and np.hypot(x - ex, y - ey) <= 150: out.append((float(x), float(y)))
    return out

def judge_frames(grays, rr=CAN_R_RANGE, off=CAN_TOP_TO_BASE, max_out=3):
    C = [candidates(g, rr, off) for g in grays]; allc = [p for c in C for p in c]
    if not allc: return {"success_geom": False, "reason": "can_top_not_found(fallen_or_occluded)"}
    ex, ey = COASTER_XY[0] - off[0], COASTER_XY[1] - off[1]
    sup = lambda p: sum(any(np.hypot(q[0] - p[0], q[1] - p[1]) <= STILL_PX for q in c) for c in C)
    best = max(allc, key=lambda p: (sup(p), -np.hypot(p[0] - ex, p[1] - ey)))
    hits = [min(c, key=lambda q: np.hypot(q[0] - best[0], q[1] - best[1])) for c in C
            if c and min(np.hypot(q[0] - best[0], q[1] - best[1]) for q in c) <= STILL_PX]
    n_hit = len(hits)
    if n_hit < len(grays) - max_out:
        return {"success_geom": False, "reason": "moving_or_not_standing", "n_consensus_frames": n_hit}
    med = np.median(np.array(hits), axis=0)
    dist = float(np.hypot(med[0] + off[0] - COASTER_XY[0], med[1] + off[1] - COASTER_XY[1]))
    ok = dist <= COASTER_R
    return {"success_geom": bool(ok), "reason": "ok" if ok else "outside", "base_dist_px": round(dist, 1), "n_consensus_frames": n_hit}

def last_frames(p):
    c = av.open(p); fr = []
    for f in c.decode(c.streams.video[0]):
        fr.append(f); fr = fr[-LAST_N:]
    c.close(); return [cv2.cvtColor(f.to_ndarray(format="rgb24"), cv2.COLOR_RGB2GRAY) for f in fr]

if __name__ == "__main__":
    tdir, outp = sys.argv[1:3]; prof = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
    rr = tuple(prof["r_range"]) if prof else CAN_R_RANGE; off = tuple(prof["top_to_base"]) if prof else CAN_TOP_TO_BASE
    res = {os.path.basename(p)[:-len("_top.mp4")]: judge_frames(last_frames(p), rr, off) for p in sorted(glob.glob(f"{tdir}/**/*_top.mp4", recursive=True))}
    json.dump(res, open(outp, "w"), indent=1)
    print(len(res), "trials;", sum(v["success_geom"] for v in res.values()), "geometric successes")
