"""§4 변형 그리드 — 1단계(GX10): LeRobot ACT 기준 체크포인트에서 셀별 ONNX를 만든다 (`G3`).
2단계(Orin, `scripts/build_engines_orin.sh`)가 이 ONNX를 동결 timing cache 복사본으로 엔진으로 빌드한다.

원칙(기존 build_grid.py와 같다):
  - `IG-3`: 모든 셀이 같은 FP32 체크포인트(G2 100k, sha256 bb5e1850…)에서 나온다. 셀마다 새로 읽는다
  - `IG-1`: 캘리브레이션 프레임은 `edgeqgate.calibration`이 LOCK-1 train에서만 고르고, 결과물도 audit 누출 재검사를 한다
  - 캘리브레이션 시드에는 셀 코드가 없다(2026-10-07): granularity만 다른 두 셀은 같은 프레임을 쓴다. 크기는 중첩 표본
  - 성공 라벨: 데모 120개 모두 성공 → success = 전부 True (approximated=False)
  - 입력은 학습과 같은 정규화(체크포인트 전처리기 통계). 프레임은 원본 데모(AV1 1세대)에서 디코딩한다
  - attempt-003: fused MHA fast path를 끈다. attempt-018: ONNX export는 CPU에서
사용(컨테이너, GPU): python build_grid_lerobot.py <데모 경로> <체크포인트 pretrained_model> <출력 폴더> [셀...]
셀 자리에 WARMUP을 주면 동결 timing cache용 워밍업 ONNX 2개(per-tensor/per-channel)를 만든다. 그리드와 무관한 시드
(`…/timing-cache-warmup`)로 train에서 16프레임을 뽑으며, 어느 셀의 캘리브레이션 세트와도 같지 않다(attempt-025 대응안 1)."""
import copy, glob, gc, hashlib, json, os, sys, time
import av, numpy as np, pandas as pd, torch
sys.path.insert(0, "/repo/src")
torch.backends.mha.set_fastpath_enabled(False)
from edgeqgate.grid import load_grid
from edgeqgate.hashing import hash_obj
from edgeqgate.splits import load_manifest
from edgeqgate.calibration import build_calibration_set, verify_no_audit_leak
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.utils.constants import OBS_IMAGES, OBS_STATE
from safetensors.torch import load_file
import modelopt.torch.quantization as mtq

SEED = "PREREG-SEED-2026-09-14"
root, ck, out = sys.argv[1:4]; only = set(sys.argv[4:])
os.makedirs(out, exist_ok=True)
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
ck_hash = sha(os.path.join(ck, "model.safetensors"))
assert ck_hash.startswith("bb5e1850"), "G2 기준 체크포인트가 아니다 (IG-3)"
m = load_manifest("/repo/artifacts/manifests/lock1_split_manifest.yaml")
assert m.manifest_hash.startswith("acf51781")
cat = lambda pat: pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(pat))], ignore_index=True)
E = cat(f"{root}/meta/episodes/chunk-*/file-*.parquet"); D = cat(f"{root}/data/chunk-*/file-*.parquet")
lengths = {f"ep{int(r.episode_index):03d}": int(r.length) for r in E.itertuples()}
success = {e: True for e in lengths}
WARM = "WARMUP" in only
if WARM:
    from types import SimpleNamespace as NS
    variants = [NS(code=f"WARMUP-{g}", precision="int8", calib_size=16, calib_composition="success-only", granularity=g)
                for g in ("per-tensor", "per-channel")]
else:
    variants = [v for v in load_grid() if v.precision in ("int8", "fp16") and (not only or v.code in only)]
print(f"[grid] 대상 {len(variants)}셀, checkpoint {ck_hash[:16]}, manifest {m.manifest_hash[:16]}", flush=True)

# 셀별 캘리브레이션 세트를 먼저 정하고, 필요한 프레임만 한 번에 디코딩한다
sets = {}
for v in variants:
    if v.precision == "int8":
        cs = build_calibration_set(v.code, v.calib_size, v.calib_composition, m, lengths,
                                   SEED + "/timing-cache-warmup" if WARM else SEED, success)
        verify_no_audit_leak(cs, m); sets[v.code] = cs
need = sorted({f for cs in sets.values() for f in cs.frames})
print(f"[grid] 디코딩할 캘리브레이션 프레임 {len(need)}개", flush=True)
nm = load_file(os.path.join(ck, "policy_preprocessor_step_3_normalizer_processor.safetensors"))
want = {}  # (cam, chunk, file) -> {ts: key}
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
            if kk in ts:
                x = torch.from_numpy(f.to_ndarray(format="rgb24")).permute(2, 0, 1).float() / 255.0
                img[cam][ts[kk]] = (x - nm[f"observation.images.{cam}.mean"]) / nm[f"observation.images.{cam}.std"]
                break
state = {}
for ep, i in need:
    s = np.stack(D[D.episode_index == int(ep[2:])]["observation.state"].to_numpy())[i]
    state[(ep, i)] = (torch.tensor(s, dtype=torch.float32) - nm["observation.state.mean"]) / nm["observation.state.std"]
miss = [f for f in need if f not in img["top"] or f not in img["wrist"]]
assert not miss, f"디코딩 누락 {len(miss)}개 (예: {miss[:3]})"

class Wrap(torch.nn.Module):
    def __init__(self, mm): super().__init__(); self.m = mm
    def forward(self, state, top, wrist):
        r = self.m({OBS_STATE: state, OBS_IMAGES: [top, wrist]})
        return r[0] if isinstance(r, (tuple, list)) else r

f0 = need[0]
ex_cpu = (state[f0][None], img["top"][f0][None], img["wrist"][f0][None])
res_path = f"{out}/{'warmup' if WARM else 'onnx'}_results.json"; results = json.load(open(res_path)) if os.path.exists(res_path) else {}
for v in variants:
    if results.get(v.code, {}).get("ok"): print(f"[grid] {v.code}: 이미 있음"); continue
    t0 = time.time()
    rec = {"code": v.code, "precision": v.precision, "calib_size": v.calib_size, "calib_composition": v.calib_composition,
           "granularity": v.granularity, "checkpoint_sha256": ck_hash}
    w = Wrap(ACTPolicy.from_pretrained(ck).model).eval()
    if v.precision == "int8":
        cs = sets[v.code]; rec.update(calib_set_hash=cs.set_hash, calib_frames_hash=hash_obj(cs.frames), calib_actual=cs.actual)
        cfg = copy.deepcopy(mtq.INT8_DEFAULT_CFG)
        if v.granularity == "per-tensor":
            for q in cfg["quant_cfg"].values():
                if isinstance(q, dict) and "axis" in q: q["axis"] = None
        w = w.cuda()
        def loop(mod, frames=cs.frames):
            with torch.no_grad():
                for k in range(0, len(frames), 16):
                    B = frames[k:k + 16]
                    mod(torch.stack([state[f] for f in B]).cuda(), torch.stack([img["top"][f] for f in B]).cuda(), torch.stack([img["wrist"][f] for f in B]).cuda())
        w = mtq.quantize(w, cfg, loop)
        w = w.cpu()
    p = f"{out}/{v.code}.onnx"
    with torch.no_grad():
        torch.onnx.export(w, ex_cpu, p, input_names=["state", "top", "wrist"], output_names=["actions"],
                          opset_version=17, do_constant_folding=True, dynamo=False)
    rec.update(ok=True, onnx_sha256=sha(p), onnx_bytes=os.path.getsize(p), sec=round(time.time() - t0, 1))
    try:
        import onnx
        g = onnx.load(p).graph; rec["n_quantize"] = sum(n.op_type == "QuantizeLinear" for n in g.node)
    except Exception as e:
        rec["onnx_inspect_error"] = str(e)[:200]
    results[v.code] = rec; json.dump(results, open(res_path, "w"), indent=1)
    print(f"[grid] {v.code}: ONNX {rec['onnx_bytes']/1e6:.0f}MB, Q {rec.get('n_quantize')}, {rec['sec']}s", flush=True)
    del w; gc.collect(); torch.cuda.empty_cache()
print("[grid] done", len(results))
