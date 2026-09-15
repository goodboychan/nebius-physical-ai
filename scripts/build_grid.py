"""§4 변형 그리드 26셀 빌드 (`G3`).

원칙:
  - `IG-3`: 모든 셀이 **동일한 FP32 체크포인트 하나**에서 파생된다. 재학습 없음.
    체크포인트 해시를 기록하고, 셀마다 deepcopy로 복원한다
  - §4.2: TRT 빌드 옵션은 셀 간 **고정**한다. `TRT_BUILD_FLAGS` 한 곳에서만 정의한다
  - `IG-1`: 캘리브레이션은 train 분할에서만. **`edgeqgate.calibration`을 실제로 호출한다.**
    attempt-022 이전에는 이 파일이 자체 RNG로 프레임을 뽑았고 `calib_composition`이
    시드 문자열에만 들어갔다 — 즉 구성 축이 **시드 변경과 구별되지 않았다**
  - attempt-009: trtexec 실행 전 GPU 메모리를 반납한다. 안 하면 workspace 할당이 실패한다

산출물(§5.3): 셀별 엔진·ONNX 해시, Q/DQ 노드 수, 스케일 통계, 환경 메타데이터.
중단 후 재실행하면 이미 성공한 셀은 건너뛴다 — 26셀 빌드는 길고 중간에 죽을 수 있다.

통과 기준(§10.2 `G3`): 최소 20셀 빌드 성공. 미만이면 `K4`.
"""
import argparse, copy, gc, hashlib, json, os, subprocess, sys, time
import numpy as np
import torch

sys.path.insert(0, "/src")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
torch.backends.mha.set_fastpath_enabled(False)

from act_model import ACTInference
from edgeqgate.grid import load_grid
from edgeqgate.hashing import hash_obj
from edgeqgate.calibration import (CalibrationUnavailable, build_calibration_set,
                                   verify_no_audit_leak)
from edgeqgate.splits import determine_splits

# §3.2 분할 시드·크기. `g0_real_data_pipeline.py`와 **같은 값이어야** manifest 해시가
# 일치한다. 두 곳에 흩어져 있으므로 빌드 시작 시 해시를 기록해 대조한다.
SEED = "PREREG-SEED-2026-09-14"
SPLIT_SIZES = {"train": 34, "val": 8, "audit": 8}
DATASET_ROOT = "/data/so101_pickplace"

# §4.2: 셀 간 동일하게 고정되는 빌드 옵션. 여기 말고 다른 데서 바꾸면 통제가 깨진다.
TRT_BUILD_FLAGS = [
    "--memPoolSize=workspace:4096",
    "--skipInference",
    "--builderOptimizationLevel=3",
]
TRTEXEC = "/opt/tensorrt/bin/trtexec"


def log(m):
    print(f"[grid] {m}", flush=True)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def env_metadata():
    """§5.3이 요구하는 환경 메타데이터."""
    import tensorrt as trt
    drv = subprocess.run(["nvidia-smi", "--query-gpu=driver_version,name",
                          "--format=csv,noheader"], capture_output=True, text=True)
    return {
        "tensorrt": trt.__version__,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "device_capability": list(torch.cuda.get_device_capability()),
        "driver_and_name": drv.stdout.strip() if drv.returncode == 0 else None,
        "trt_build_flags": TRT_BUILD_FLAGS,
    }


def scale_stats(onnx_path):
    """엔진이 아니라 ONNX에서 스케일 모양을 센다 (per-channel 여부 확인용)."""
    import onnx
    from onnx import numpy_helper
    g = onnx.load(onnx_path).graph
    produced = {i.name: tuple(i.dims) for i in g.initializer}
    for n in g.node:
        if n.op_type == "Constant":
            for att in n.attribute:
                if att.name == "value":
                    produced[n.output[0]] = tuple(numpy_helper.to_array(att.t).shape)
    q = dq = per_axis = scalar = 0
    for n in g.node:
        if n.op_type == "QuantizeLinear":
            q += 1
            d = produced.get(n.input[1]) if len(n.input) > 1 else None
            if d is not None:
                (per_axis if (len(d) >= 1 and d[0] > 1) else scalar).__int__()
                if len(d) >= 1 and d[0] > 1:
                    per_axis += 1
                else:
                    scalar += 1
        elif n.op_type == "DequantizeLinear":
            dq += 1
    return {"QuantizeLinear": q, "DequantizeLinear": dq,
            "per_axis_scales": per_axis, "scalar_scales": scalar}


def calibration_index(frame_index):
    """평탄한 프레임 캐시를 `(에피소드, 에피소드 내 순번)` 좌표로 되돌린다.

    `edgeqgate.calibration`은 프레임을 그 좌표계로 다룬다. `late-phase-only`가
    "에피소드 후반 1/3"을 뜻하려면 순번이 있어야 하고, `IG-1`의 train 한정과
    audit 누출 재검사도 에피소드 단위로 돈다. 캐시는 평탄하므로 되돌려야 한다.

    드라이런 주의: 캐시는 에피소드당 12프레임만 담은 **부분표본**이다. 따라서
    여기서의 "순번"은 캐시된 프레임 사이의 순번이며, 균일 부분표본이므로 실제 위상과
    단조 관계를 유지한다. 본 실험에서는 캐시가 전 프레임을 담으므로 둘이 일치한다.
    """
    import pandas as pd
    df = pd.read_parquet(f"{DATASET_ROOT}/data/chunk-000/file-000.parquet")
    ep_col = df.set_index("index")["episode_index"]
    all_eps = sorted({f"ep{int(x):03d}" for x in ep_col.unique()})
    manifest = determine_splits(all_eps, seed=SEED, sizes=SPLIT_SIZES)

    # `frame_index`는 전역 프레임 번호의 오름차순이고, 캐시 배열의 위치와 1:1이다.
    lengths = {ep: 0 for ep in manifest.ids("train")}
    pos_of = {}
    for pos, g in enumerate(frame_index):
        ep = f"ep{int(ep_col.loc[int(g)]):03d}"
        i = lengths.get(ep, 0)
        pos_of[(ep, i)] = pos
        lengths[ep] = i + 1
    return manifest, lengths, pos_of


def free_gpu(*objs):
    """attempt-009: 학습/양자화 텐서를 쥔 채 trtexec를 띄우면 OOM이 난다."""
    for o in objs:
        del o
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()


def build_engine(onnx_path, engine_path, precision):
    flags = list(TRT_BUILD_FLAGS)
    if precision == "int8":
        # `--int8`만 켜면 INT8 커널이 없는 레이어가 FP32로 떨어지고 그 사이마다
        # reformat 노드가 붙는다. 실측(attempt-013): --int8 단독 28.57ms / 274레이어 vs
        # --int8 --fp16 16.22ms / 236레이어. 반드시 함께 켠다.
        flags += ["--int8", "--fp16"]
    elif precision == "fp16":
        flags.append("--fp16")
    cmd = [TRTEXEC, f"--onnx={onnx_path}", f"--saveEngine={engine_path}"] + flags
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    ok = p.returncode == 0 and os.path.exists(engine_path)
    err = None
    if not ok:
        tail = [l for l in (p.stdout + p.stderr).splitlines()
                if any(k in l for k in ("Error", "error", "failure", "FAILED"))]
        err = " | ".join(tail[-3:])[:400]
    return ok, round(time.time() - t0, 1), err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="/out/grid")
    ap.add_argument("--checkpoint", default="/out/act_fp32_reference.pt")
    ap.add_argument("--cache", default="/out/frames_cache.npz")
    ap.add_argument("--cells", nargs="*", default=None, help="부분 빌드 (리허설용)")
    ap.add_argument("--max-calib-size", type=int, default=None,
                    help="드라이런에서 프레임이 부족할 때 상한을 건다")
    ap.add_argument("--keep-onnx", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    variants = load_grid()
    if a.cells:
        variants = [v for v in variants if v.code in set(a.cells)]
    log(f"대상 {len(variants)}셀")

    ck_hash = sha256_file(a.checkpoint)
    ck = torch.load(a.checkpoint, map_location="cpu", weights_only=False)
    log(f"IG-3 레퍼런스 체크포인트 sha256={ck_hash[:16]}")

    d = np.load(a.cache)
    imgs = torch.from_numpy(d["images"]).float() / 255.0
    states = d["states"]
    s_mean, s_std = ck["norm"]["s_mean"], ck["norm"]["s_std"]
    S = torch.from_numpy((states - s_mean) / s_std).float()
    n_frames = imgs.shape[0]
    manifest, ep_lengths, pos_of = calibration_index(d["frame_index"])
    n_eps = sum(1 for v in ep_lengths.values() if v)
    log(f"캘리브레이션 풀 {n_frames} 프레임 / train 에피소드 {n_eps}개 "
        f"(manifest_hash={manifest.manifest_hash[:16]})")
    # 공개 데이터셋에는 성공/실패 라벨이 없다. `success=None`이면 `success-only`가
    # `mixed`와 같아지고 `CalibrationSet.approximated`가 True로 표시된다.
    # 본 실험에서는 `G1` 라벨을 넘긴다 — 여기서 조용히 넘어가지 않도록 셀마다 기록한다.
    success_labels = None

    import modelopt.torch.quantization as mtq
    env = env_metadata()
    log(f"환경: TRT {env['tensorrt']}, sm{''.join(map(str, env['device_capability']))}, "
        f"{env['driver_and_name']}")

    results_path = f"{a.outdir}/build_results.json"
    results = json.load(open(results_path)) if os.path.exists(results_path) else {}

    for v in variants:
        if results.get(v.code, {}).get("ok"):
            log(f"{v.code}: 이미 성공 — 건너뜀")
            continue
        t_cell = time.time()
        rec = {"code": v.code, "precision": v.precision, "target": v.target,
               "calib_size": v.calib_size, "calib_composition": v.calib_composition,
               "granularity": v.granularity, "checkpoint_sha256": ck_hash}

        if v.precision == "fp32":
            # VC-000은 GX10 FP32 레퍼런스다. TRT 엔진을 만들지 않는다 (§4.1).
            rec.update(ok=True, note="FP32 레퍼런스 — TRT 빌드 대상 아님", sec=0.0)
            results[v.code] = rec
            log(f"{v.code}: FP32 레퍼런스, 빌드 생략")
            continue

        model = copy.deepcopy(ck["state_dict"])
        net = ACTInference()
        net.load_state_dict(model)
        net = net.cuda().eval()
        ex = (imgs[:1].cuda(), S[:1].cuda())

        if v.precision == "int8":
            size = v.calib_size
            if a.max_calib_size:
                size = min(size, a.max_calib_size)
            # 프레임 선택은 `edgeqgate.calibration`이 한다. 여기서 직접 뽑으면
            # `IG-1`(train 한정)·audit 누출 재검사·구성 축 필터가 전부 우회된다.
            try:
                cs = build_calibration_set(
                    cell=v.code, calib_size=size, composition=v.calib_composition,
                    manifest=manifest, episode_lengths=ep_lengths, seed=SEED,
                    success=success_labels)
                verify_no_audit_leak(cs, manifest)
            except CalibrationUnavailable as e:
                rec.update(ok=False, error=str(e)[:400],
                           sec=round(time.time() - t_cell, 1))
                results[v.code] = rec
                log(f"{v.code}: 실패 — {rec['error']}")
                free_gpu(net, ex)
                continue
            sel = [pos_of[f] for f in cs.frames]
            rec["calib_set_hash"] = cs.set_hash
            rec["calib_approximated"] = cs.approximated
            rec["calib_frames_hash"] = hash_obj(sorted(int(x) for x in sel))

            cfg = copy.deepcopy(mtq.INT8_DEFAULT_CFG)
            if v.granularity == "per-tensor":
                for q in cfg["quant_cfg"].values():
                    if isinstance(q, dict) and "axis" in q:
                        q["axis"] = None

            def loop(m, sel=sel):
                with torch.no_grad():
                    for i in sel:
                        m(imgs[i:i+1].cuda(), S[i:i+1].cuda())

            net = mtq.quantize(net, cfg, loop)

        onnx_path = f"{a.outdir}/{v.code}.onnx"
        torch.onnx.export(net, ex, onnx_path, input_names=["images", "state"],
                          output_names=["actions"], opset_version=17,
                          do_constant_folding=True, dynamo=False)
        rec["onnx_sha256"] = sha256_file(onnx_path)
        rec["onnx_bytes"] = os.path.getsize(onnx_path)
        try:
            rec["scales"] = scale_stats(onnx_path)
        except Exception as e:
            rec["scales_error"] = str(e)[:200]

        free_gpu(net, ex)   # attempt-009: 빌드 전 반드시 반납

        eng = f"{a.outdir}/{v.code}.engine"
        ok, sec, err = build_engine(onnx_path, eng, v.precision)
        rec.update(ok=ok, build_sec=sec, sec=round(time.time() - t_cell, 1))
        if ok:
            rec["engine_sha256"] = sha256_file(eng)
            rec["engine_bytes"] = os.path.getsize(eng)
        else:
            rec["error"] = err
        if not a.keep_onnx and os.path.exists(onnx_path):
            os.remove(onnx_path)

        results[v.code] = rec
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        log(f"{v.code}: {'성공' if ok else '실패'} "
            f"({rec.get('build_sec', 0)}s 빌드, {rec['sec']}s 전체)"
            + ("" if ok else f" — {err}"))

    built = [c for c, r in results.items() if r.get("ok") and r.get("precision") != "fp32"]
    manifest = {"schema": "edgeqgate/grid_build/v1", "spec_section": "§4, G3",
                "checkpoint_sha256": ck_hash, "env": env,
                "n_cells_attempted": len(results),
                "n_engines_built": len(built),
                "g3_criterion_min_cells": 20,
                "g3_pass": len(built) >= 20,
                "results": results}
    manifest["manifest_hash"] = hash_obj(manifest)
    with open(f"{a.outdir}/grid_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    log(f"\n엔진 {len(built)}개 빌드 성공 / G3 기준 20개 -> "
        f"{'통과' if manifest['g3_pass'] else 'K4 발동 검토'}")
    log(f"manifest_hash={manifest['manifest_hash'][:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
