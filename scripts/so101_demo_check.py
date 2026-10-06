"""데모 묶음 점검: 에피소드별 길이·프레임 간격·끝 자세와, 시작/끝 오버헤드 프레임 모음(/tmp/demo_sheet.jpg).
사용: so101_demo_check.py <데이터셋 경로> [시작 에피소드]"""
import sys, json, os, av, numpy as np, pandas as pd
from PIL import Image, ImageDraw
root = os.path.expanduser(sys.argv[1]); first = int(sys.argv[2]) if len(sys.argv) > 2 else 0
import glob
cat = lambda pat: pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(pat))], ignore_index=True)
e = cat(f"{root}/meta/episodes/chunk-*/file-*.parquet"); d = cat(f"{root}/data/chunk-*/file-*.parquet")
F = json.load(open(os.path.expanduser("~/.cache/huggingface/lerobot/calibration/robots/so_follower/follower.json")))
el = F["elbow_flex"]; m = (el["range_min"] + el["range_max"]) / 2; el_hi = (el["range_max"] - m) * 360 / 4095
sel = e[e["episode_index"] >= first]
print(f"episodes {first}..{e['episode_index'].max()}  (total {len(e)}, frames {len(d)})")
print(" ep  len    sec  dt_max_ms  grip_end  elbow_pinned%")
for _, r in sel.iterrows():
    g = d[d["episode_index"] == r["episode_index"]]
    s = np.stack(g["observation.state"].to_numpy()); a = np.stack(g["action"].to_numpy())
    dt = np.diff(g["timestamp"].to_numpy()).max() * 1000
    pinned = ((a[:, 2] > el_hi + 0.5).mean()) * 100
    print(f"{r['episode_index']:3d} {r['length']:4d} {r['length']/30:6.1f} {dt:9.2f} {s[-1,5]:9.1f} {pinned:13.1f}")
V = "videos/observation.images.top"
fr = {}  # (ep, "s"|"e") -> image
for vf, grp in sel.groupby([f"{V}/chunk_index", f"{V}/file_index"]):
    targets = []
    for _, r in grp.iterrows():
        targets += [(r[f"{V}/from_timestamp"], (r["episode_index"], "s")), (r[f"{V}/to_timestamp"] - 1 / 30, (r["episode_index"], "e"))]
    c = av.open(f"{root}/{V}/chunk-{vf[0]:03d}/file-{vf[1]:03d}.mp4"); st = c.streams.video[0]
    for f in c.decode(st):
        t = float(f.pts * st.time_base)
        for tt, key in targets:
            if key not in fr and abs(t - tt) < 0.5 / 30:
                fr[key] = f.to_image().crop((80, 180, 480, 480)).resize((200, 150))
starts = list(sel["episode_index"])
cols = 6; rows = (len(starts) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 400, rows * 150), "white"); dr = ImageDraw.Draw(sheet)
for k, ep in enumerate(starts):
    x, y = (k % cols) * 400, (k // cols) * 150
    for j, w in enumerate("se"):
        if (ep, w) in fr: sheet.paste(fr[(ep, w)], (x + 200 * j, y))
    dr.text((x + 4, y + 2), f"ep{ep}", fill=(255, 255, 0))
sheet.save("/tmp/demo_sheet.jpg", quality=85); print("sheet: /tmp/demo_sheet.jpg (each cell: start | end)")
