"""Simple checks vs audit scores (decision_log 2026-10-13; rules fixed before computing).
Part A (container, GPU not needed): calibration-image input check for the 24 INT8 cells, using their real frames, and
for PC-N / PC-B, using their replacement images in raw pixel space [0, 1].
Part B (host): action MSE on the 2,000 audit states from the payloads, plus the frozen score_mag / score_align.
Usage: (A) python simple_checks.py inputs <demos> <ckpt pretrained_model> <out.json>
       (B) python simple_checks.py table <inputs.json> <g4 payload dir> <pc payload dir> <out.json>"""
import glob, json, os, sys
import numpy as np

def part_a(root, ck, outp):
    import av, pandas as pd, torch
    sys.path.insert(0, "/repo/src")
    from edgeqgate.grid import load_grid
    from edgeqgate.splits import load_manifest
    from edgeqgate.calibration import build_calibration_set
    from edgeqgate.hashing import seed_from
    from safetensors.torch import load_file
    SEED = "PREREG-SEED-2026-09-14"
    m = load_manifest("/repo/artifacts/manifests/lock1_split_manifest.yaml")
    cat = lambda pat: pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(pat))], ignore_index=True)
    E = cat(f"{root}/meta/episodes/chunk-*/file-*.parquet")
    lengths = {f"ep{int(r.episode_index):03d}": int(r.length) for r in E.itertuples()}; success = {e: True for e in lengths}
    cells = [v for v in load_grid() if v.precision == "int8"]
    sets = {v.code: build_calibration_set(v.code, v.calib_size, v.calib_composition, m, lengths, SEED, success).frames for v in cells}
    sets["PC-N"] = sets["PC-B"] = sets["VC-007"]
    need = sorted({f for fs in sets.values() for f in fs}); want = {}
    for ep, i in need:
        r = E[E.episode_index == int(ep[2:])].iloc[0]
        for cam in ("top", "wrist"):
            V = f"videos/observation.images.{cam}"
            want.setdefault((cam, r[V + "/chunk_index"], r[V + "/file_index"]), {})[round(r[V + "/from_timestamp"] + i / 30, 3)] = (ep, i)
    st = {"top": {}, "wrist": {}}
    for (cam, ci, fi), ts in want.items():
        c = av.open(f"{root}/videos/observation.images.{cam}/chunk-{ci:03d}/file-{fi:03d}.mp4"); s = c.streams.video[0]
        for f in c.decode(s):
            k = round(float(f.pts * s.time_base), 3)
            for kk in (k, round(k - 0.001, 3), round(k + 0.001, 3)):
                if kk in ts:
                    x = f.to_ndarray(format="rgb24").astype(np.float32) / 255.0
                    st[cam][ts[kk]] = (float(x.mean()), float(x.std()), 0.0); break
    nm = load_file(os.path.join(ck, "policy_preprocessor_step_3_normalizer_processor.safetensors"))
    shape = {"top": (3, 480, 640), "wrist": (3, 200, 320)}
    def pc(code, cam, f):
        mu, sd = nm[f"observation.images.{cam}.mean"], nm[f"observation.images.{cam}.std"]
        if code == "PC-B": x = torch.zeros(shape[cam])
        else:
            g = torch.Generator().manual_seed(seed_from(SEED, "positive-control", code, cam, f[0], int(f[1])) % (2 ** 63))
            x = torch.randn(shape[cam], generator=g) * sd + mu        # raw pixels the normalized noise stands for
        return (float(x.mean()), float(x.std()), float(((x < 0) | (x > 1)).float().mean()))
    out = {}
    for code, fs in sets.items():
        rows = [pc(code, cam, f) if code.startswith("PC-") else st[cam][f] for f in fs for cam in ("top", "wrist")]
        a = np.array(rows)
        flag = bool(((a[:, 0] < 0.02) | (a[:, 0] > 0.98) | (a[:, 1] < 0.01) | (a[:, 2] > 0.01)).any())
        out[code] = {"n_images": len(rows), "mean_range": [float(a[:, 0].min()), float(a[:, 0].max())], "std_min": float(a[:, 1].min()),
                     "out_of_range_max": float(a[:, 2].max()), "input_check_flag": flag}
    json.dump(out, open(outp, "w"), indent=1); print({k: v["input_check_flag"] for k, v in out.items()})

def part_b(inp, g4p, pcp, outp):
    I = json.load(open(inp)); S = {}
    for f in glob.glob("artifacts/manifests/g4_scores/VC-*.json") + glob.glob("artifacts/positive_control/PC-*.json"):
        d = json.load(open(f)); S[d["cell"]] = d
    mse = {}
    for f in glob.glob(f"{g4p}/VC-*.npz") + glob.glob(f"{pcp}/PC-*.npz"):
        c = os.path.basename(f)[:-4]; mse[c] = float((np.load(f)["mag"] ** 2).mean())
    normal = [c for c in I if c.startswith("VC-")]
    mse_max = max(mse[c] for c in normal); up = {s: max(S[c][s]["ci95"][1] for c in normal) for s in ("score_mag", "score_align")}
    tab = {}
    for c in normal + ["PC-N", "PC-B"]:
        tab[c] = {"input_check": I[c]["input_check_flag"], "action_mse": mse[c], "action_mse_flag": mse[c] > mse_max,
                  **{s: S[c][s]["point"] for s in up}, **{s + "_flag": S[c][s]["ci95"][0] > up[s] for s in up}}
    summary = {k: {c: tab[c][k] for c in ("PC-N", "PC-B")} | {"normal_cells_flagged": sum(tab[c][k] for c in normal)}
               for k in ("input_check", "action_mse_flag", "score_mag_flag", "score_align_flag")}
    json.dump({"thresholds": {"action_mse_max_normal": mse_max, **{s + "_ci_upper_max_normal": v for s, v in up.items()}},
               "summary": summary, "cells": tab}, open(outp, "w"), indent=1)
    print(json.dumps(summary, indent=1)); print({c: round(tab[c]["action_mse"], 5) for c in ("PC-N", "PC-B")}, "normal max", round(mse_max, 5))

if __name__ == "__main__":
    if sys.argv[1] == "inputs": part_a(*sys.argv[2:5])
    else: part_b(*sys.argv[2:6])
