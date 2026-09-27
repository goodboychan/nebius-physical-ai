"""캘리브레이션 추첨의 **분포**를 본다 — TRT 빌드 없이 많은 표본으로.

attempt-026에서 크기 16의 두 추첨이 출력 상관 −0.16까지 벌어졌다(`s16_r0` vs `s16_r1`).
표본이 2개뿐이라 "드문 파국적 추첨"인지 "늘 그런 것"인지 알 수 없다.

TRT 빌드는 추첨당 ~220초라 표본을 늘릴 수 없다. 대신 **modelopt fake-quant를 PyTorch에서
그대로 평가**한다. 추첨당 수 초다. fake-quant는 TRT INT8 커널과 다르지만, 여기서 보려는
것은 **캘리브레이션 추첨이 amax를 통해 출력을 얼마나 흔드는가**이고 그 경로는 동일하다.
TRT 빌드 6건이 대응 검증 앵커 역할을 한다.

`IG-3`: 전부 동일 FP32 체크포인트에서 파생. train 분할만 사용. 결과 열람 아님.
"""
import argparse, copy, json, os, sys
import numpy as np
import torch

sys.path.insert(0, "/src")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
torch.backends.mha.set_fastpath_enabled(False)

from act_model import ACTInference
from edgeqgate.calibration import build_calibration_set, verify_no_audit_leak
from build_grid import calibration_index, SEED


def log(m):
    print(f"[dist] {m}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/out/draw_distribution.json")
    ap.add_argument("--checkpoint", default="/out/act_fp32_reference.pt")
    ap.add_argument("--cache", default="/out/frames_cache.npz")
    ap.add_argument("--sizes", type=int, nargs="+", default=[16, 64, 256])
    ap.add_argument("--draws", type=int, default=20)
    ap.add_argument("--granularity", default="per-tensor")
    a = ap.parse_args()

    import modelopt.torch.quantization as mtq
    d = np.load(a.cache)
    imgs = torch.from_numpy(d["images"]).float() / 255.0
    manifest, lengths, pos_of = calibration_index(d["frame_index"])
    ck = torch.load(a.checkpoint, map_location="cpu", weights_only=False)
    s_mean, s_std = ck["norm"]["s_mean"], ck["norm"]["s_std"]
    S = torch.from_numpy((d["states"] - s_mean) / s_std).float()
    log(f"풀 {imgs.shape[0]}프레임, manifest={manifest.manifest_hash[:16]}")

    # 평가 입력은 **고정**한다 — 추첨 외의 변동을 없앤다. train 분할 프레임이다.
    ev = torch.arange(0, imgs.shape[0], max(1, imgs.shape[0] // 32))[:32]
    eval_imgs, eval_S = imgs[ev].cuda(), S[ev].cuda()

    # FP32 레퍼런스 출력
    ref = ACTInference(); ref.load_state_dict(ck["state_dict"]); ref = ref.cuda().eval()
    with torch.no_grad():
        y_fp32 = ref(eval_imgs, eval_S).float().cpu().numpy().reshape(-1)
    log(f"FP32 레퍼런스 출력 {y_fp32.size}개, |y| mean={np.abs(y_fp32).mean():.5f}")

    results = {}
    for size in a.sizes:
        outs, hashes = [], []
        for r in range(a.draws):
            cs = build_calibration_set(
                cell=f"DIST-{size}-{r}", calib_size=size, composition="mixed",
                manifest=manifest, episode_lengths=lengths,
                seed=f"{SEED}|dist{r}", success=None)
            verify_no_audit_leak(cs, manifest)
            sel = [pos_of[f] for f in cs.frames]
            net = ACTInference(); net.load_state_dict(copy.deepcopy(ck["state_dict"]))
            net = net.cuda().eval()
            cfg = copy.deepcopy(mtq.INT8_DEFAULT_CFG)
            if a.granularity == "per-tensor":
                for q in cfg["quant_cfg"].values():
                    if isinstance(q, dict) and "axis" in q:
                        q["axis"] = None

            def loop(m, sel=sel):
                with torch.no_grad():
                    for i in sel:
                        m(imgs[i:i+1].cuda(), S[i:i+1].cuda())

            net = mtq.quantize(net, cfg, loop)
            with torch.no_grad():
                outs.append(net(eval_imgs, eval_S).float().cpu().numpy().reshape(-1))
            hashes.append(cs.set_hash[:12])
            del net
            torch.cuda.empty_cache()

        Y = np.stack(outs)
        # FP32 대비 상대오차 — 이것이 score_mag의 원재료와 같은 성질의 양이다
        err = np.linalg.norm(Y - y_fp32, axis=1) / np.linalg.norm(y_fp32)
        # 추첨끼리의 거리
        pair = [float(np.linalg.norm(Y[i] - Y[j]) / np.linalg.norm(Y[j]))
                for i in range(len(Y)) for j in range(i + 1, len(Y))]
        corr = [float(np.corrcoef(Y[i], y_fp32)[0, 1]) for i in range(len(Y))]
        results[size] = {
            "n_draws": len(Y),
            "err_vs_fp32": {"median": float(np.median(err)), "min": float(err.min()),
                            "max": float(err.max()), "p90": float(np.quantile(err, .9))},
            "pairwise_between_draws": {"median": float(np.median(pair)),
                                       "max": float(max(pair))},
            "corr_with_fp32": {"median": float(np.median(corr)), "min": float(min(corr))},
            "n_broken_corr_below_0.9": int(sum(1 for c in corr if c < 0.9)),
            "set_hashes": hashes,
        }
        log(f"size={size:<5} FP32대비 중앙 {np.median(err)*100:6.2f}% "
            f"최대 {err.max()*100:7.2f}%  추첨간 중앙 {np.median(pair)*100:6.2f}% "
            f"최대 {max(pair)*100:7.2f}%  corr최소 {min(corr):.3f}  "
            f"파국 {sum(1 for c in corr if c < 0.9)}/{len(Y)}")

    with open(a.out, "w") as f:
        json.dump({"granularity": a.granularity, "n_eval_states": int(ev.numel()),
                   "results": {str(k): v for k, v in results.items()}}, f,
                  indent=2, ensure_ascii=False)
    log(f"저장: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
