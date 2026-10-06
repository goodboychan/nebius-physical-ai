"""저장된 ACT 체크포인트 중 하나를 `val` 분할로 고른다 (§3.2: val은 조기종료·하이퍼파라미터 용도). 실기 없음, 오프라인.
지표: val 에피소드에서 10프레임마다 관측 → 예측 action chunk(100스텝)와 실제 이후 action(팔로워 한계로 자른 값)의
정규화 L1. 에피소드 끝을 넘는 스텝은 제외. 가장 낮은 체크포인트를 고르되, 고른 뒤에는 바꾸지 않는다(IG-3).
사용(컨테이너, GPU): python val_select.py <원본 데모> <체크포인트 루트> <출력 json>"""
import glob, json, os, sys
import av, numpy as np, pandas as pd, torch
sys.path.insert(0, "/repo/src")
from edgeqgate.splits import load_manifest, assert_allowed
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.utils.constants import OBS_IMAGES, OBS_STATE
from safetensors.torch import load_file
torch.backends.mha.set_fastpath_enabled(False)

root, ck_root, out = sys.argv[1:4]
m = load_manifest("/repo/artifacts/manifests/lock1_split_manifest.yaml")
assert m.manifest_hash == "acf51781c3940f89e94b8573cff618818deeb128940f57aa00de6c654806401c"
val = [int(e[2:]) for e in assert_allowed(m, m.ids("val"), "policy_training")]
cal = json.load(open("/repo/configs/calibration/follower.json"))
names = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
lo = np.array([0.0 if n == "gripper" else (cal[n]["range_min"] - (cal[n]["range_min"] + cal[n]["range_max"]) / 2) * 360 / 4095 for n in names])
hi = np.array([100.0 if n == "gripper" else (cal[n]["range_max"] - (cal[n]["range_min"] + cal[n]["range_max"]) / 2) * 360 / 4095 for n in names])

cat = lambda pat: pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(pat))], ignore_index=True)
E = cat(f"{root}/meta/episodes/chunk-*/file-*.parquet"); D = cat(f"{root}/data/chunk-*/file-*.parquet")
cams = ["top", "wrist"]; samples = []  # (state, {cam: img uint8}, future actions, mask)
frames = {c: {} for c in cams}
for c in cams:
    V = f"videos/observation.images.{c}"
    for vf, grp in E[E.episode_index.isin(val)].groupby([f"{V}/chunk_index", f"{V}/file_index"]):
        cont = av.open(f"{root}/{V}/chunk-{vf[0]:03d}/file-{vf[1]:03d}.mp4"); st = cont.streams.video[0]
        want = {}
        for _, r in grp.iterrows():
            n = int(r["length"])
            for i in range(0, n, 10): want[round(r[f"{V}/from_timestamp"] + i / 30, 3)] = (int(r["episode_index"]), i)
        for f in cont.decode(st):
            k = round(float(f.pts * st.time_base), 3)
            for kk in (k, round(k - 0.001, 3), round(k + 0.001, 3)):
                if kk in want: frames[c][want[kk]] = f.to_ndarray(format="rgb24"); break
for ep in val:
    g = D[D.episode_index == ep]; s = np.stack(g["observation.state"].to_numpy()); a = np.clip(np.stack(g["action"].to_numpy()), lo, hi)
    for i in range(0, len(g), 10):
        if all((ep, i) in frames[c] for c in cams):
            fut = np.zeros((100, 6)); msk = np.zeros(100, bool); k = min(100, len(g) - i)
            fut[:k] = a[i:i + k]; msk[:k] = True
            samples.append((s[i], {c: frames[c][(ep, i)] for c in cams}, fut, msk))
print(f"val episodes {len(val)}, samples {len(samples)}")

res = {}
for ck in sorted(glob.glob(f"{ck_root}/*/pretrained_model")):
    step = os.path.basename(os.path.dirname(ck))
    pol = ACTPolicy.from_pretrained(ck).eval().cuda()
    nm = load_file(os.path.join(ck, "policy_preprocessor_step_3_normalizer_processor.safetensors"))
    a_mean, a_std = nm["action.mean"].numpy(), nm["action.std"].numpy()
    errs = []
    with torch.no_grad():
        for b in range(0, len(samples), 16):
            B = samples[b:b + 16]
            st = (torch.tensor(np.stack([x[0] for x in B]), dtype=torch.float32) - nm["observation.state.mean"]) / nm["observation.state.std"]
            imgs = []
            for c in cams:
                x = torch.from_numpy(np.stack([x[1][c] for x in B])).permute(0, 3, 1, 2).float() / 255.0
                imgs.append(((x - nm[f"observation.images.{c}.mean"]) / nm[f"observation.images.{c}.std"]).cuda())
            r = pol.model({OBS_STATE: st.cuda(), OBS_IMAGES: imgs}); pred = (r[0] if isinstance(r, (tuple, list)) else r).cpu().numpy()
            gt = (np.stack([x[2] for x in B]) - a_mean) / a_std; mk = np.stack([x[3] for x in B])
            errs.append(np.abs(pred - gt)[mk].mean(axis=-1))
    e = np.concatenate(errs)
    res[step] = {"val_l1_norm": float(e.mean()), "n_steps": int(e.size)}
    print(step, f"val L1 (normalized) {e.mean():.4f}")
best = min(res, key=lambda k: res[k]["val_l1_norm"])
json.dump({"manifest_hash": m.manifest_hash, "val_episodes": len(val), "samples": len(samples), "results": res, "selected": best}, open(out, "w"), indent=1)
print("selected", best)
