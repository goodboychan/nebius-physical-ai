"""§4.1 요인 축이 **실제로 다른 양자화를 만드는가** — `G3` 이전 사전 점검.

동기: §4.1은 `calib_size`(4) x `calib_composition`(3) x `granularity`(2) = 24 INT8 셀을
둔다. 이 축들이 양자화 파라미터를 거의 바꾸지 않는다면 셀 간 분산이 없고 `K3`
("오프라인 점수가 셀 간 분산을 거의 안 보임")이 `G4`에서 발동한다.
26셀을 전부 빌드하기 **전에** 알아두는 편이 낫다.

이 점검은 결과 열람이 아니다. 실기 데이터도, 우리 수집 데이터도 쓰지 않는다.
공개 데이터셋 위에서 계측기가 작동하는지 확인하는 것이며, §4.3이 요구한
"문서만 믿고 축을 설계하지 않는다"의 연장이다.

`IG-3`: 모든 구성이 동일한 FP32 체크포인트 하나에서 파생된다.
"""
import argparse, copy, itertools, json, os, sys
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
torch.backends.mha.set_fastpath_enabled(False)
from act_model import ACTInference

OUT = "/out"
ROOT = "/data/so101_pickplace"


def log(m):
    print(f"[calib] {m}", flush=True)


def load_reference():
    ck = torch.load(f"{OUT}/act_fp32_reference.pt", map_location="cpu", weights_only=False)
    m = ACTInference()
    m.load_state_dict(ck["state_dict"])
    return m, ck


def phase_of(frame_indices):
    """각 전역 프레임이 속한 에피소드 내 정규화 위상 [0,1]."""
    df = pd.read_parquet(f"{ROOT}/data/chunk-000/file-000.parquet")
    d = df.set_index("index")
    ep = d.loc[frame_indices, "episode_index"].to_numpy()
    fi = d.loc[frame_indices, "frame_index"].to_numpy()
    lens = df.groupby("episode_index").size()
    return fi / np.maximum(lens.loc[ep].to_numpy() - 1, 1)


def select(comp, phase, n, rng):
    """캘리브레이션 구성 축 (§4.1). 공개 데이터셋에는 성공/실패 라벨이 없으므로
    'success-only / mixed / late-phase-only'를 **위상 기반**으로 근사한다.
      - uniform     : 전 구간 균등 (mixed에 대응)
      - late-phase  : 위상 상위 1/3만 (late-phase-only에 대응)
      - early-phase : 위상 하위 1/3만 (대조용 추가)
    """
    idx = np.arange(len(phase))
    if comp == "uniform":
        pool = idx
    elif comp == "late-phase":
        pool = idx[phase >= 2 / 3]
    elif comp == "early-phase":
        pool = idx[phase <= 1 / 3]
    else:
        raise ValueError(comp)
    if len(pool) == 0:
        raise ValueError(f"{comp}: 후보 없음")
    take = min(n, len(pool))
    return rng.choice(pool, size=take, replace=False), take


def amax_vector(model):
    """활성화된 양자화기들의 amax를 이름순으로 모아 벡터화."""
    rows = {}
    for name, mod in model.named_modules():
        a = getattr(mod, "amax", None)
        if a is None:
            continue
        v = a.detach().float().flatten().cpu().numpy()
        rows[name] = v
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[16, 64, 256])
    ap.add_argument("--comps", nargs="+", default=["uniform", "late-phase", "early-phase"])
    ap.add_argument("--granularity", default="per-channel")
    a = ap.parse_args()

    import modelopt.torch.quantization as mtq
    d = np.load(f"{OUT}/frames_cache.npz")
    imgs = torch.from_numpy(d["images"]).float() / 255.0
    states = d["states"]
    fidx = d["frame_index"]
    log(f"캐시 로드: {imgs.shape[0]} 프레임")

    phase = phase_of(fidx)
    log(f"위상 분포: 하위1/3 {int((phase<=1/3).sum())}개, 상위1/3 {int((phase>=2/3).sum())}개")

    ref, ck = load_reference()
    log(f"레퍼런스 체크포인트 로드 (IG-3), split_hash={ck['split_manifest_hash'][:16]}")
    s_mean, s_std = ck["norm"]["s_mean"], ck["norm"]["s_std"]
    S = torch.from_numpy((states - s_mean) / s_std).float()

    results = {}
    for size, comp in itertools.product(a.sizes, a.comps):
        rng = np.random.default_rng(abs(hash((size, comp))) % (2**32))
        sel, took = select(comp, phase, size, rng)
        model = copy.deepcopy(ref).cuda().eval()   # IG-3: 매번 같은 체크포인트에서
        cfg = copy.deepcopy(mtq.INT8_DEFAULT_CFG)
        if a.granularity == "per-tensor":
            for v in cfg["quant_cfg"].values():
                if isinstance(v, dict) and "axis" in v:
                    v["axis"] = None

        def loop(m, sel=sel):
            with torch.no_grad():
                for i in sel:
                    m(imgs[i:i+1].cuda(), S[i:i+1].cuda())

        model = mtq.quantize(model, cfg, loop)
        results[f"{size}/{comp}"] = amax_vector(model)
        log(f"  size={size:<5} comp={comp:<12} 실제표본={took:<4} 양자화기={len(results[f'{size}/{comp}'])}")
        del model
        torch.cuda.empty_cache()

    # ---- 비교 ----
    keys = list(results)
    base = results[f"{a.sizes[-1]}/uniform"]
    common = sorted(set.intersection(*[set(r) for r in results.values()]))
    log(f"\n공통 양자화기 {len(common)}개로 비교")

    # 가중치 양자화기는 캘리브레이션 데이터와 무관하다 (가중치만으로 amax가 정해진다).
    # 축이 작동하는지는 **활성화 양자화기**에서만 판별된다. 반드시 분리해서 본다.
    w_keys = [k for k in common if "weight_quantizer" in k]
    a_keys = [k for k in common if "weight_quantizer" not in k]
    log(f"  가중치 양자화기 {len(w_keys)}개 / 활성화 양자화기 {len(a_keys)}개")

    def flat(r, ks):
        return np.concatenate([np.atleast_1d(r[k]) for k in ks]) if ks else np.array([])

    summary = {}
    for group, ks in (("weight", w_keys), ("activation", a_keys)):
        if not ks:
            continue
        b = flat(base, ks)
        print(f"\n--- {group} 양자화기 ({len(ks)}개, 스칼라 {b.size}개) ---")
        print(f"{'구성':<22} {'중앙 상대차':>12} {'최대 상대차':>12} {'상관':>8}")
        for k in keys:
            v = flat(results[k], ks)
            rel = np.abs(v - b) / np.maximum(np.abs(b), 1e-12)
            corr = float(np.corrcoef(v, b)[0, 1]) if v.size > 1 else float("nan")
            summary[f"{group}|{k}"] = {"median_rel_diff": float(np.median(rel)),
                                       "max_rel_diff": float(rel.max()),
                                       "corr_with_base": corr}
            print(f"{k:<22} {np.median(rel)*100:>11.2f}% {rel.max()*100:>11.1f}% {corr:>8.4f}")
        np.savez(f"{OUT}/calib_amax_{group}.npz",
                 **{k: flat(results[k], ks) for k in keys})

    out = {"reference_checkpoint_sha256_prefix": "ff94f873702c494a",
           "granularity": a.granularity, "n_quantizers_compared": len(common),
           "baseline": f"{a.sizes[-1]}/uniform", "summary": summary}
    with open(f"{OUT}/calib_axis_probe.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    log("\n저장: /out/calib_axis_probe.json")


if __name__ == "__main__":
    sys.exit(main())
