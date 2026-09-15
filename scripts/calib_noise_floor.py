"""캘리브레이션 축의 **노이즈 바닥** — attempt-010이 빠뜨린 대조군.

attempt-010은 구성을 바꾸면 활성화 amax가 중앙 1.2~11.2% 움직인다고 보고했다.
그러나 **같은 구성을 다른 시드로 재추첨했을 때의 산포를 재지 않았다.** 그것이 없으면
`256/late-phase`의 2.07%가 축 효과인지 표본 노이즈인지 구분되지 않는다.

`K3`("오프라인 점수가 셀 간 분산을 거의 안 보임")의 사전 신호다. 26셀 빌드(Orin 6.5h)와
225 trial을 태우기 전에 알아야 한다.

프레임 선택은 **생산 경로와 같은 함수**(`edgeqgate.calibration.build_calibration_set`)를
쓴다. attempt-022 이전에는 `build_grid.py`가 자체 RNG를 썼고 구성 축이 시드 문자열에만
들어갔다 — 그 버그를 고친 뒤이므로 여기서 재는 것이 실제로 빌드될 셀의 성질이다.

`IG-3`: 모든 구성이 동일한 FP32 체크포인트 하나에서 파생된다.
결과 열람이 아니다. 공개 데이터셋의 train 분할만 쓴다.
"""
import argparse, copy, itertools, json, os, sys
import numpy as np
import torch

sys.path.insert(0, "/src")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
torch.backends.mha.set_fastpath_enabled(False)

from act_model import ACTInference
from edgeqgate.calibration import CalibrationUnavailable, build_calibration_set, verify_no_audit_leak
from edgeqgate.splits import determine_splits

OUT = "/out"
ROOT = "/data/so101_pickplace"
SEED = "PREREG-SEED-2026-09-14"
SPLIT_SIZES = {"train": 34, "val": 8, "audit": 8}


def log(m):
    print(f"[noise] {m}", flush=True)


def calibration_index(frame_index):
    """`build_grid.calibration_index`와 같은 좌표 복원. 생산 경로와 일치시킨다."""
    import pandas as pd
    df = pd.read_parquet(f"{ROOT}/data/chunk-000/file-000.parquet")
    ep_col = df.set_index("index")["episode_index"]
    all_eps = sorted({f"ep{int(x):03d}" for x in ep_col.unique()})
    manifest = determine_splits(all_eps, seed=SEED, sizes=SPLIT_SIZES)
    lengths = {ep: 0 for ep in manifest.ids("train")}
    pos_of = {}
    for pos, g in enumerate(frame_index):
        ep = f"ep{int(ep_col.loc[int(g)]):03d}"
        i = lengths.get(ep, 0)
        pos_of[(ep, i)] = pos
        lengths[ep] = i + 1
    return manifest, lengths, pos_of


def amax_vector(model):
    out = {}
    for name, mod in model.named_modules():
        a = getattr(mod, "amax", None)
        if a is not None:
            out[name] = a.detach().float().cpu().numpy().reshape(-1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[16, 64, 128])
    ap.add_argument("--comps", nargs="+", default=["mixed", "late-phase-only"])
    ap.add_argument("--replicates", type=int, default=6)
    ap.add_argument("--granularity", default="per-channel")
    a = ap.parse_args()

    import modelopt.torch.quantization as mtq
    d = np.load(f"{OUT}/frames_cache.npz")
    imgs = torch.from_numpy(d["images"]).float() / 255.0
    manifest, lengths, pos_of = calibration_index(d["frame_index"])
    log(f"캐시 {imgs.shape[0]}프레임, train 에피소드 "
        f"{sum(1 for v in lengths.values() if v)}개, manifest={manifest.manifest_hash[:16]}")

    ck = torch.load(f"{OUT}/act_fp32_reference.pt", map_location="cpu", weights_only=False)
    ref = ACTInference(); ref.load_state_dict(ck["state_dict"])
    s_mean, s_std = ck["norm"]["s_mean"], ck["norm"]["s_std"]
    S = torch.from_numpy((d["states"] - s_mean) / s_std).float()
    log(f"IG-3 레퍼런스 로드, split_hash={ck['split_manifest_hash'][:16]}")

    runs = {}          # (size, comp, rep) -> amax dict
    frame_sets = {}    # 같은 프레임이 두 번 뽑혔는지 확인용
    for size, comp in itertools.product(a.sizes, a.comps):
        for rep in range(a.replicates):
            key = (size, comp, rep)
            # 시드만 바꾼다. 셀 코드·구성·크기는 고정 — 이것이 노이즈 바닥의 정의다.
            try:
                cs = build_calibration_set(
                    cell="NF", calib_size=size, composition=comp, manifest=manifest,
                    episode_lengths=lengths, seed=f"{SEED}|rep{rep}", success=None)
                verify_no_audit_leak(cs, manifest)
            except CalibrationUnavailable as e:
                log(f"  size={size} comp={comp} rep={rep}: 건너뜀 — {e}")
                continue
            sel = [pos_of[f] for f in cs.frames]
            frame_sets[key] = cs.set_hash

            model = copy.deepcopy(ref).cuda().eval()
            cfg = copy.deepcopy(mtq.INT8_DEFAULT_CFG)
            if a.granularity == "per-tensor":
                for q in cfg["quant_cfg"].values():
                    if isinstance(q, dict) and "axis" in q:
                        q["axis"] = None

            def loop(m, sel=sel):
                with torch.no_grad():
                    for i in sel:
                        m(imgs[i:i+1].cuda(), S[i:i+1].cuda())

            model = mtq.quantize(model, cfg, loop)
            runs[key] = amax_vector(model)
            del model
            torch.cuda.empty_cache()
        log(f"size={size:<4} comp={comp:<16} 완료 "
            f"({sum(1 for k in runs if k[0] == size and k[1] == comp)}회)")

    if not runs:
        log("측정된 구성이 없다"); return 1

    # ---- 활성화 양자화기만 본다. 가중치는 캘리브레이션과 무관하다(attempt-010) ----
    common = sorted(set.intersection(*[set(r) for r in runs.values()]))
    a_keys = [k for k in common if "weight_quantizer" not in k]
    log(f"공통 양자화기 {len(common)}개 중 활성화 {len(a_keys)}개로 비교")

    def flat(r):
        return np.concatenate([np.atleast_1d(r[k]) for k in a_keys])

    vecs = {k: flat(v) for k, v in runs.items()}
    n_scalar = len(next(iter(vecs.values())))
    log(f"활성화 스칼라 {n_scalar}개")

    def rel_dist(u, v):
        """중앙 상대차. attempt-010과 같은 통계라야 비교가 된다."""
        return float(np.median(np.abs(u - v) / np.maximum(np.abs(v), 1e-12)))

    configs = sorted({(k[0], k[1]) for k in vecs})
    within = {}
    for c in configs:
        reps = [vecs[k] for k in vecs if (k[0], k[1]) == c]
        pairs = [rel_dist(reps[i], reps[j])
                 for i in range(len(reps)) for j in range(i + 1, len(reps))]
        within[c] = pairs

    medians = {c: np.median(np.stack([vecs[k] for k in vecs if (k[0], k[1]) == c]), axis=0)
               for c in configs}

    print("\n=== 노이즈 바닥: 같은 구성, 시드만 다름 ===")
    print(f"{'구성':<26} {'복제':>4} {'쌍':>4} {'중앙 상대차':>12} {'최대':>10}")
    for c in configs:
        pairs = within[c]
        n_rep = sum(1 for k in vecs if (k[0], k[1]) == c)
        print(f"{str(c):<26} {n_rep:>4} {len(pairs):>4} "
              f"{np.median(pairs)*100:>11.3f}% {max(pairs)*100:>9.3f}%")

    pooled = [x for c in configs for x in within[c]]
    floor = float(np.median(pooled))
    print(f"\n통합 노이즈 바닥 (중앙): {floor*100:.3f}%")

    print("\n=== 구성 간 차이 (같은 크기, 다른 구성) ===")
    print(f"{'비교':<40} {'중앙 상대차':>12} {'바닥 대비':>10}")
    comp_effects = []
    for size in sorted({c[0] for c in configs}):
        cs_ = sorted([c for c in configs if c[0] == size])
        for i in range(len(cs_)):
            for j in range(i + 1, len(cs_)):
                dv = rel_dist(medians[cs_[i]], medians[cs_[j]])
                comp_effects.append((size, cs_[i][1], cs_[j][1], dv))
                lbl = f"size={size} {cs_[i][1]} vs {cs_[j][1]}"
                print(f"{lbl:<40} {dv*100:>11.3f}% {dv/floor:>9.2f}x")

    print("\n=== 크기 간 차이 (같은 구성, 다른 크기) ===")
    print(f"{'비교':<40} {'중앙 상대차':>12} {'바닥 대비':>10}")
    size_effects = []
    for comp in sorted({c[1] for c in configs}):
        cs_ = sorted([c for c in configs if c[1] == comp])
        for i in range(len(cs_)):
            for j in range(i + 1, len(cs_)):
                dv = rel_dist(medians[cs_[i]], medians[cs_[j]])
                size_effects.append((comp, cs_[i][0], cs_[j][0], dv))
                lbl = f"{comp} {cs_[i][0]} vs {cs_[j][0]}"
                print(f"{lbl:<40} {dv*100:>11.3f}% {dv/floor:>9.2f}x")

    # ---- 구성 효과가 시드 노이즈 분포의 어디에 있나 (같은 크기 안에서) ----
    print("\n=== 구성 효과의 위치: 같은 크기의 시드 쌍 거리 분포 대비 ===")
    print(f"{'크기':<8} {'구성 간':>10} {'시드 쌍 중앙':>12} {'시드 쌍 최대':>12} {'백분위':>10}")
    placement = []
    for size in sorted({c[0] for c in configs}):
        cs_ = sorted([c for c in configs if c[0] == size])
        if len(cs_) < 2:
            continue
        null = [x for c in cs_ for x in within[c]]
        eff = rel_dist(medians[cs_[0]], medians[cs_[1]])
        pct = 100.0 * float(np.mean(np.asarray(null) < eff))
        placement.append({"size": size, "effect": eff, "null_median": float(np.median(null)),
                          "null_max": float(max(null)), "percentile": pct, "n_null": len(null)})
        print(f"{size:<8} {eff*100:>9.3f}% {np.median(null)*100:>11.3f}% "
              f"{max(null)*100:>11.3f}% {pct:>9.1f}%")

    np.savez_compressed(f"{OUT}/calib_noise_floor_vectors.npz",
                        **{f"{k[0]}|{k[1]}|{k[2]}": v for k, v in vecs.items()})

    out = {
        "n_activation_scalars": n_scalar,
        "effect_placement": placement,
        "n_activation_quantizers": len(a_keys),
        "granularity": a.granularity,
        "replicates": a.replicates,
        "noise_floor_median_rel": floor,
        "within_config": {f"{c[0]}/{c[1]}": {"median": float(np.median(within[c])),
                                            "max": float(max(within[c])),
                                            "n_pairs": len(within[c])} for c in configs},
        "composition_effects": [{"size": s, "a": x, "b": y, "median_rel": v,
                                 "vs_floor": v / floor} for s, x, y, v in comp_effects],
        "size_effects": [{"composition": c, "a": x, "b": y, "median_rel": v,
                          "vs_floor": v / floor} for c, x, y, v in size_effects],
        "calibration_set_hashes": {f"{k[0]}/{k[1]}/rep{k[2]}": v
                                   for k, v in frame_sets.items()},
    }
    with open(f"{OUT}/calib_noise_floor.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    log(f"\n저장: {OUT}/calib_noise_floor.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
