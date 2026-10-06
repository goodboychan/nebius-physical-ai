"""G1 산출물(#9): 데모 영상의 프레임 반복률. 팔이 움직이는 동안(관절 변화 > 1°/프레임) 직전 프레임과 사실상 같은
프레임(변화 픽셀 < 0.05%)의 비율을 카메라·에피소드별로 잰다. 카메라가 녹화 루프(30Hz)보다 늦게 새 프레임을 내면 이 값이 오른다.
LeRobot 타임스탬프는 frame_index/fps로 찍혀 실제 지연을 드러내지 않으므로 영상 내용으로 잰다.
사용(컨테이너): python frame_repeat_rate.py <데이터셋> <출력 json>"""
import glob, json, sys
import av, numpy as np, pandas as pd
root, out = sys.argv[1:3]
cat = lambda pat: pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(pat))], ignore_index=True)
e = cat(f"{root}/meta/episodes/chunk-*/file-*.parquet"); d = cat(f"{root}/data/chunk-*/file-*.parquet")
res = {}
for cam in ("top", "wrist"):
    V = f"videos/observation.images.{cam}"; per = {}
    for vf, grp in e.groupby([f"{V}/chunk_index", f"{V}/file_index"]):
        c = av.open(f"{root}/{V}/chunk-{vf[0]:03d}/file-{vf[1]:03d}.mp4"); st = c.streams.video[0]
        frames = [(float(f.pts * st.time_base), f.to_ndarray(format="gray")[::2, ::2].astype(np.int16)) for f in c.decode(st)]
        ts = np.array([t for t, _ in frames])
        for _, r in grp.iterrows():
            a, b = r[f"{V}/from_timestamp"], r[f"{V}/to_timestamp"]
            sel = [g for t, g in frames if a - 1e-3 <= t < b - 1e-3]
            ep = int(r["episode_index"]); s = np.stack(d[d.episode_index == ep]["observation.state"].to_numpy())
            n = min(len(sel), len(s)); fr = np.stack(sel[:n])
            changed = (np.abs(np.diff(fr, axis=0)) > 12).mean(axis=(1, 2))
            moving = np.abs(np.diff(s[:n, :5], axis=0)).max(axis=1) > 1.0
            rep = (changed < 0.0005) & moving
            per[ep] = {"moving_steps": int(moving.sum()), "repeat_while_moving": int(rep.sum()),
                       "rate": float(rep.sum() / max(moving.sum(), 1)), "frames_video": len(sel), "frames_data": len(s)}
    rates = np.array([v["rate"] for v in per.values()])
    res[cam] = {"episodes": per, "rate_mean": float(rates.mean()), "rate_p50": float(np.median(rates)),
                "rate_max": float(rates.max()), "frame_count_mismatch": int(sum(v["frames_video"] != v["frames_data"] for v in per.values()))}
    print(f"{cam}: repeat-while-moving mean {rates.mean()*100:.1f}%  median {np.median(rates)*100:.1f}%  max {rates.max()*100:.1f}%  "
          f"video/data frame mismatch {res[cam]['frame_count_mismatch']} episodes")
json.dump(res, open(out, "w"), indent=1)
