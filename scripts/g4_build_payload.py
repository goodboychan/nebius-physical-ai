"""`G4` 1단계(GX10, 컨테이너): 셀별 엔진 출력과 GX10 FP32 레퍼런스에서 상태별 점수 벡터를 만든다 (decision_log 2026-10-07 정의).
- 오차 e[n,k] = a_cell[n,k] − a_ref[n,k] (정규화 단위, k = 0..99)
- 진행도 회귀기 g(s, a): LOCK-1 train 에피소드의 (정규화 상태, 정규화 action) → 위상 진행도 (`IG-2`, edgeqgate.progress)
- 민감 방향 u[n,k] = (s_n, a_ref[n,k])에서 ∂g/∂a 단위 벡터 — 셀과 무관하므로 한 번만 계산
- mag[n] = sqrt(mean_k ‖e‖²), align[n] = sqrt(mean_k (u·e)²): 감사 2,000상태 → Jobs가 CVaR@90과 부트스트랩을 낸다
- cheap_B = train 2,000상태의 mean_n mean_k ‖e‖², cheap_C = Orin GPU 지연 중앙값(감사 상태 추론에서)
출력: <out>/payload/<cell>.npz, <out>/g4_payload_index.json
사용: python g4_build_payload.py <데모> <체크포인트> <g4 폴더> <엔진 출력 폴더>"""
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/repo/src")
from edgeqgate.splits import load_manifest
from edgeqgate.progress import fit_from_episodes
from edgeqgate.hashing import hash_obj
from safetensors.torch import load_file

SEED = "PREREG-SEED-2026-09-14"
root, ck, g4, outs = sys.argv[1:5]
m = load_manifest("/repo/artifacts/manifests/lock1_split_manifest.yaml"); assert m.manifest_hash.startswith("acf51781")
idx = json.load(open(f"{g4}/g4_states_index.json")); assert idx["audit_buffer_hash"].startswith("d9a52977")
nm = load_file(os.path.join(ck, "policy_preprocessor_step_3_normalizer_processor.safetensors"))
s_mu, s_sd = nm["observation.state.mean"].numpy(), nm["observation.state.std"].numpy()
a_mu, a_sd = nm["action.mean"].numpy(), nm["action.std"].numpy()
cat = lambda pat: pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(pat))], ignore_index=True)
D = cat(f"{root}/data/chunk-*/file-*.parquet")
def load_ep(eid):
    g = D[D.episode_index == int(eid[2:])]
    return (np.stack(g["observation.state"].to_numpy()) - s_mu) / s_sd, (np.stack(g["action"].to_numpy()) - a_mu) / a_sd
g = fit_from_episodes(m, m.ids("train"), load_ep, SEED)
print("g model_hash", g.model_hash[:16], "n", g.n_train_samples, flush=True)

refA = np.load(f"{g4}/audit_ref_fp32.npz")["actions_norm"].astype(np.float64)
refT = np.load(f"{g4}/train_ref_fp32.npz")["actions_norm"].astype(np.float64)
sA = (np.load(f"{g4}/audit_npy/state.npy") - s_mu) / s_sd
N, K, A = refA.shape
u, gn = g.sensitivity_directions(np.repeat(sA, K, axis=0), refA.reshape(N * K, A))
u = u.reshape(N, K, A); print("directions", u.shape, "zero-norm fraction %.4f" % float((gn < 1e-12).mean()), flush=True)

os.makedirs(f"{g4}/payload", exist_ok=True); index = {}
for f in sorted(glob.glob(f"{outs}/*_audit.npz")):
    cell = os.path.basename(f).replace("_audit.npz", "")
    oa = np.load(f); ot = np.load(f"{outs}/{cell}_train.npz")
    eA = oa["actions_norm"].astype(np.float64) - refA; eT = ot["actions_norm"].astype(np.float64) - refT
    mag = np.sqrt((eA ** 2).sum(-1).mean(-1)); align = np.sqrt((np.einsum("nka,nka->nk", eA, u) ** 2).mean(-1))
    cheapB = float((eT ** 2).sum(-1).mean()); cheapC = float(np.median(oa["gpu_ms"]))
    np.savez(f"{g4}/payload/{cell}.npz", mag=mag, align=align)
    index[cell] = {"cheap_B": cheapB, "cheap_C_ms": cheapC, "mag_mean": float(mag.mean()), "align_mean": float(align.mean()),
                   "payload_sha": hash_obj([np.round(mag, 12).tolist(), np.round(align, 12).tolist()])}
    print(cell, "mag_mean %.4f align_mean %.4f cheapB %.5f cheapC %.2fms" % (mag.mean(), align.mean(), cheapB, cheapC), flush=True)
json.dump({"g_model_hash": g.model_hash, "audit_buffer_hash": idx["audit_buffer_hash"], "cells": index},
          open(f"{g4}/g4_payload_index.json", "w"), indent=1)
