"""`G4` 입력 준비 (GX10, 컨테이너). 감사 버퍼 2,000상태(§3.3, audit만)와 `score_cheap_B`용 train 2,000상태(§5.1b)를
정하고, 프레임을 원본 데모에서 디코딩해 저장한다. 같은 상태에서 GX10 FP32(torch) 레퍼런스 출력(`VC-000`, §4.1)도 낸다.
- 감사 버퍼: edgeqgate.audit_buffer.build_buffer (에피소드당 100, 시간축 균등 격자, 양 끝 포함)
- train 상태: 같은 균등 격자를 train 80 에피소드에 25개씩
- 출력: <out>/{audit,train}_states.npz (state, top, wrist uint8), <out>/{audit,train}_ref_fp32.npz (actions 정규화·도 단위),
  <out>/g4_states_index.json (좌표·해시)
사용: python g4_prepare_states.py <데모> <체크포인트 pretrained_model> <출력>"""
import glob, json, os, sys
import av, numpy as np, pandas as pd, torch
sys.path.insert(0, "/repo/src")
torch.backends.mha.set_fastpath_enabled(False)
from edgeqgate.splits import load_manifest, assert_allowed
from edgeqgate.audit_buffer import build_buffer
from edgeqgate.hashing import hash_obj
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.utils.constants import OBS_IMAGES, OBS_STATE
from safetensors.torch import load_file

SEED = "PREREG-SEED-2026-09-14"
root, ck, out = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
m = load_manifest("/repo/artifacts/manifests/lock1_split_manifest.yaml"); assert m.manifest_hash.startswith("acf51781")
cat = lambda pat: pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(pat))], ignore_index=True)
E = cat(f"{root}/meta/episodes/chunk-*/file-*.parquet"); D = cat(f"{root}/data/chunk-*/file-*.parquet")
lengths = {f"ep{int(r.episode_index):03d}": int(r.length) for r in E.itertuples()}

buf = build_buffer(m, lengths, SEED)
audit_pairs = buf.pairs()
train_eps = assert_allowed(m, m.ids("train"), "cheap_B_train_states")
train_pairs = [(ep, int(i)) for ep in train_eps for i in np.unique(np.rint(np.linspace(0, lengths[ep] - 1, 25)).astype(int))]
assert len(audit_pairs) == 2000 and len(train_pairs) == 2000, (len(audit_pairs), len(train_pairs))
index = {"seed": SEED, "manifest_hash": m.manifest_hash, "audit_buffer_hash": buf.buffer_hash,
         "audit_pairs_hash": hash_obj(audit_pairs), "train_pairs_hash": hash_obj(train_pairs),
         "audit_pairs": audit_pairs, "train_pairs": train_pairs}
json.dump(index, open(f"{out}/g4_states_index.json", "w"))
print("audit_buffer_hash", buf.buffer_hash, flush=True)

def decode(pairs):
    want = {}
    for k, (ep, i) in enumerate(pairs):
        r = E[E.episode_index == int(ep[2:])].iloc[0]
        for cam in ("top", "wrist"):
            V = f"videos/observation.images.{cam}"
            want.setdefault((cam, r[V + "/chunk_index"], r[V + "/file_index"]), {})[round(r[V + "/from_timestamp"] + i / 30, 3)] = k
    arr = {"top": np.zeros((len(pairs), 480, 640, 3), np.uint8), "wrist": np.zeros((len(pairs), 200, 320, 3), np.uint8)}
    got = {"top": set(), "wrist": set()}
    for (cam, ci, fi), ts in want.items():
        c = av.open(f"{root}/videos/observation.images.{cam}/chunk-{ci:03d}/file-{fi:03d}.mp4"); st = c.streams.video[0]
        for f in c.decode(st):
            t = round(float(f.pts * st.time_base), 3)
            for tt in (t, round(t - 0.001, 3), round(t + 0.001, 3)):
                if tt in ts: arr[cam][ts[tt]] = f.to_ndarray(format="rgb24"); got[cam].add(ts[tt]); break
    assert all(len(got[c]) == len(pairs) for c in got), {c: len(got[c]) for c in got}
    st = np.stack([np.stack(D[D.episode_index == int(ep[2:])]["observation.state"].to_numpy())[i] for ep, i in pairs]).astype(np.float32)
    return st, arr["top"], arr["wrist"]

pol = ACTPolicy.from_pretrained(ck).eval().cuda()
nm = load_file(os.path.join(ck, "policy_preprocessor_step_3_normalizer_processor.safetensors"))
pm = load_file(os.path.join(ck, "policy_postprocessor_step_0_unnormalizer_processor.safetensors"))
for name, pairs in (("audit", audit_pairs), ("train", train_pairs)):
    st, top, wr = decode(pairs)
    np.savez(f"{out}/{name}_states.npz", state=st, top=top, wrist=wr)
    outs = []
    with torch.no_grad():
        for k in range(0, len(pairs), 16):
            s = (torch.from_numpy(st[k:k + 16]) - nm["observation.state.mean"]) / nm["observation.state.std"]
            ims = [((torch.from_numpy(a[k:k + 16]).permute(0, 3, 1, 2).float() / 255.0 - nm[f"observation.images.{c}.mean"]) / nm[f"observation.images.{c}.std"]).cuda()
                   for c, a in (("top", top), ("wrist", wr))]
            r = pol.model({OBS_STATE: s.cuda(), OBS_IMAGES: ims}); outs.append((r[0] if isinstance(r, (tuple, list)) else r).cpu().numpy())
    a_norm = np.concatenate(outs); a_deg = a_norm * pm["action.std"].numpy() + pm["action.mean"].numpy()
    np.savez(f"{out}/{name}_ref_fp32.npz", actions_norm=a_norm, actions=a_deg)
    print(name, st.shape, a_norm.shape, flush=True)
