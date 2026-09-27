"""캘리브레이션 **추첨 노이즈**를 출력 수준에서, 크기별로 잰다.

attempt-026: 그리드 4셀을 Orin에 빌드해 비교했더니 `VC-001` vs `VC-003`이 7.5%
벌어졌다. 그런데 공개 데이터셋에는 성공 라벨이 없어 `success-only`와 `mixed`의 풀이
**동일**하다. 두 셀은 **같은 풀에서 다른 16프레임을 뽑은 것**이 차이의 전부다.

즉 7.5%는 축 효과가 아니라 **추첨 효과**다. 그리고 `build_calibration_set`의 시드에
`cell`이 들어가므로 **26셀 전부가 서로 독립한 추첨**을 받는다.

이 스크립트는 그 추첨 노이즈가 `calib_size`에 따라 어떻게 줄어드는지 잰다.
같은 요인 조합(`mixed` / `per-tensor`)에서 시드만 바꾼 ONNX를 크기별로 2개씩 만든다.
Orin에서 동결 캐시로 빌드해 비교하면 **빌드 추첨이 제거된 상태의 순수 추첨 노이즈**가 나온다.

`IG-3`: 전부 동일 FP32 체크포인트에서 파생. 결과 열람 아님 — train 분할만 쓴다.
"""
import argparse, copy, os, sys, time
import numpy as np
import torch

sys.path.insert(0, "/src")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
torch.backends.mha.set_fastpath_enabled(False)

from act_model import ACTInference
from edgeqgate.calibration import build_calibration_set, verify_no_audit_leak
from build_grid import calibration_index, SEED


def log(m):
    print(f"[draw] {m}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="/out/draw_probe")
    ap.add_argument("--checkpoint", default="/out/act_fp32_reference.pt")
    ap.add_argument("--cache", default="/out/frames_cache.npz")
    ap.add_argument("--sizes", type=int, nargs="+", default=[16, 64, 256])
    ap.add_argument("--reps", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    import modelopt.torch.quantization as mtq
    d = np.load(a.cache)
    imgs = torch.from_numpy(d["images"]).float() / 255.0
    manifest, lengths, pos_of = calibration_index(d["frame_index"])
    ck = torch.load(a.checkpoint, map_location="cpu", weights_only=False)
    s_mean, s_std = ck["norm"]["s_mean"], ck["norm"]["s_std"]
    S = torch.from_numpy((d["states"] - s_mean) / s_std).float()
    log(f"풀 {imgs.shape[0]}프레임, manifest={manifest.manifest_hash[:16]}")

    for size in a.sizes:
        for rep in range(a.reps):
            tag = f"s{size}_r{rep}"
            t0 = time.time()
            cs = build_calibration_set(
                cell=f"DRAW-{tag}", calib_size=size, composition="mixed",
                manifest=manifest, episode_lengths=lengths,
                seed=f"{SEED}|draw{rep}", success=None)
            verify_no_audit_leak(cs, manifest)
            sel = [pos_of[f] for f in cs.frames]

            net = ACTInference()
            net.load_state_dict(copy.deepcopy(ck["state_dict"]))
            net = net.cuda().eval()
            ex = (imgs[:1].cuda(), S[:1].cuda())
            cfg = copy.deepcopy(mtq.INT8_DEFAULT_CFG)
            for q in cfg["quant_cfg"].values():          # per-tensor로 고정
                if isinstance(q, dict) and "axis" in q:
                    q["axis"] = None

            def loop(m, sel=sel):
                with torch.no_grad():
                    for i in sel:
                        m(imgs[i:i+1].cuda(), S[i:i+1].cuda())

            net = mtq.quantize(net, cfg, loop)
            p = f"{a.outdir}/{tag}.onnx"
            torch.onnx.export(net, ex, p, input_names=["images", "state"],
                              output_names=["actions"], opset_version=17,
                              do_constant_folding=True, dynamo=False)
            log(f"{tag}: set_hash={cs.set_hash[:12]} ({time.time()-t0:.0f}s)")
            del net, ex
            torch.cuda.empty_cache()
    log("완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
