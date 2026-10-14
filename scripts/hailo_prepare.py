"""Hailo portability probe (docs/hailo_portability_probe.md), step 1, local.
- Calibration frames for HL-16 / HL-1024: edgeqgate.calibration with the LOCK-1 seed, success-only, so the frames are
  the ones VC-002 / VC-020 used. Saved as uint8 NHWC RGB (normalisation is folded into the HEF).
- The CPU tail: the ONNX graph cut at the two input_proj Conv outputs (+ state) -> actions.
- Norm constants for the HEF's normalisation layer.
Usage: python hailo_prepare.py <demo root> <G2 onnx> <norm_stats.npz> <out dir>"""
import glob, json, os, sys
import av, numpy as np, pandas as pd, onnx
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from edgeqgate.splits import load_manifest
from edgeqgate.calibration import build_calibration_set, verify_no_audit_leak
from edgeqgate.hashing import hash_obj

SEED = "PREREG-SEED-2026-09-14"
END = ["/m/encoder_img_feat_input_proj/Conv", "/m/encoder_img_feat_input_proj_1/Conv"]
root, onnx_path, ns_path, out = sys.argv[1:5]; os.makedirs(out, exist_ok=True)
m = load_manifest(os.path.join(os.path.dirname(__file__), "..", "artifacts/manifests/lock1_split_manifest.yaml"))
assert m.manifest_hash.startswith("acf51781")
cat = lambda pat: pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(pat))], ignore_index=True)
E = cat(f"{root}/meta/episodes/chunk-*/file-*.parquet")
lengths = {f"ep{int(r.episode_index):03d}": int(r.length) for r in E.itertuples()}
success = {e: True for e in lengths}

info = {}
sets = {}
for code, n, twin in (("HL-16", 16, "VC-002"), ("HL-1024", 1024, "VC-020")):
    cs = build_calibration_set(twin, n, "success-only", m, lengths, SEED, success); verify_no_audit_leak(cs, m)
    sets[code] = cs; info[code] = {"twin": twin, "calib_set_hash": cs.set_hash, "calib_frames_hash": hash_obj(cs.frames), "n": cs.actual}
assert set(sets["HL-16"].frames) <= set(sets["HL-1024"].frames)
need = sorted(set(sets["HL-1024"].frames))
want = {}
for ep, i in need:
    r = E[E.episode_index == int(ep[2:])].iloc[0]
    for cam in ("top", "wrist"):
        V = f"videos/observation.images.{cam}"
        want.setdefault((cam, r[V + "/chunk_index"], r[V + "/file_index"]), {})[round(r[V + "/from_timestamp"] + i / 30, 3)] = (ep, i)
img = {"top": {}, "wrist": {}}
for (cam, ci, fi), ts in want.items():
    c = av.open(f"{root}/videos/observation.images.{cam}/chunk-{ci:03d}/file-{fi:03d}.mp4"); st = c.streams.video[0]
    for f in c.decode(st):
        k = round(float(f.pts * st.time_base), 3)
        for kk in (k, round(k - 0.001, 3), round(k + 0.001, 3)):
            if kk in ts: img[cam][ts[kk]] = f.to_ndarray(format="rgb24"); break
    c.close()
miss = [f for f in need if f not in img["top"] or f not in img["wrist"]]
assert not miss, f"missing {len(miss)} frames, e.g. {miss[:3]}"
for code, cs in sets.items():
    np.savez(f"{out}/{code}_calib.npz", top=np.stack([img["top"][f] for f in cs.frames]), wrist=np.stack([img["wrist"][f] for f in cs.frames]))

ns = np.load(ns_path)
np.savez(f"{out}/norm.npz", **{k: ns[k].reshape(-1).astype(np.float32) for k in ("observation_images_top_mean", "observation_images_top_std",
                                                                                 "observation_images_wrist_mean", "observation_images_wrist_std",
                                                                                 "observation_state_mean", "observation_state_std")})
g = onnx.load(onnx_path)
conv_out = {n.name: n.output[0] for n in g.graph.node if n.name in END}
assert len(conv_out) == 2, conv_out
info["tail_inputs"] = {"state": "state", "top_feat": conv_out[END[0]], "wrist_feat": conv_out[END[1]]}
onnx.utils.extract_model(onnx_path, f"{out}/tail.onnx", ["state", conv_out[END[0]], conv_out[END[1]]], ["actions"])
json.dump(info, open(f"{out}/prepare.json", "w"), indent=1)
print(json.dumps(info, indent=1))
