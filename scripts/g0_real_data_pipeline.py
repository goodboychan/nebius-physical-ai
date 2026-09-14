"""`G0` — 공개 SO-101 데이터셋으로 ACT 학습 -> ONNX -> TRT INT8 한 바퀴.

attempt-003은 무작위 가중치·무작위 캘리브레이션으로 **그래프/툴체인**만 검증했다.
이 스크립트는 실데이터를 태워 `G0`의 원래 산출물 요건을 채운다.

무결성: 분할은 edgeqgate.splits로 결정하고, 학습·캘리브레이션 로더가 `IG-1` 가드를 통과한다.
audit 분할의 에피소드는 여기서 단 한 번도 열리지 않는다.

한계: 이 학습은 **정책을 만들기 위한 것이 아니다.** 실제 가중치와 실제 캘리브레이션
분포를 export 경로에 태우는 것이 목적이며, 스텝 수는 의도적으로 작다.
"""
import argparse, json, os, sys, time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

sys.path.insert(0, "/src")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
torch.backends.mha.set_fastpath_enabled(False)   # attempt-003 발견

from act_model import ACTInference
from edgeqgate.splits import determine_splits, assert_allowed
from edgeqgate.hashing import hash_obj

ROOT = "/data/so101_pickplace"
FPS = 30
SEED = "PREREG-SEED-2026-09-14"


def log(m):
    print(f"[real] {m}", flush=True)


def load_frames(video_path, frame_indices, chunk_pad=2):
    """전역 프레임 인덱스 목록에 해당하는 프레임을 디코딩한다."""
    from torchvision.io import read_video
    out = {}
    for gi in sorted(frame_indices):
        t = gi / FPS
        v, _, _ = read_video(video_path, start_pts=max(0.0, t - 0.001),
                             end_pts=t + chunk_pad / FPS, pts_unit="sec", output_format="TCHW")
        if v.shape[0] == 0:
            continue
        out[gi] = v[0]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="/out")
    ap.add_argument("--frames-per-episode", type=int, default=12)
    ap.add_argument("--train-steps", type=int, default=300)
    ap.add_argument("--calib-size", type=int, default=64)
    ap.add_argument("--granularity", default="per-channel", choices=["per-channel", "per-tensor"])
    ap.add_argument("--batch", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    res = {"dataset": "lerobot/svla_so101_pickplace", "seed": SEED}

    df = pd.read_parquet(f"{ROOT}/data/chunk-000/file-000.parquet")
    eps = sorted(df.episode_index.unique().tolist())
    ep_ids = [f"ep{int(e):03d}" for e in eps]
    log(f"에피소드 {len(ep_ids)}개, 프레임 {len(df)}개")

    # ---- 분할 (§3.2) ----
    sizes = {"train": 34, "val": 8, "audit": 8}
    manifest = determine_splits(ep_ids, seed=SEED, sizes=sizes)
    log(f"분할 {sizes} manifest_hash={manifest.manifest_hash[:16]}")
    res["split_manifest_hash"] = manifest.manifest_hash
    res["sizes"] = sizes

    train_eps = manifest.ids("train")
    # `IG-1`: 학습 경로에 audit이 섞이면 여기서 예외
    assert_allowed(manifest, train_eps, "policy_training")
    audit_eps = set(manifest.ids("audit"))
    log(f"IG-1 통과. audit {len(audit_eps)}개는 이 스크립트에서 열지 않는다")

    # ---- 프레임 인덱스 선정 (train만) ----
    train_idx_nums = {int(e[2:]) for e in train_eps}
    sub = df[df.episode_index.isin(train_idx_nums)]
    picks = []
    for e, g in sub.groupby("episode_index"):
        gi = g["index"].to_numpy()
        sel = np.linspace(0, len(gi) - 1, a.frames_per_episode).round().astype(int)
        picks.extend(gi[np.unique(sel)].tolist())
    picks = sorted(set(picks))
    log(f"학습·캘리브레이션용 프레임 {len(picks)}개 (train 에피소드에서만)")

    # 누출 검사: 고른 프레임이 정말 train 에피소드에서 왔는가
    chosen_eps = {f"ep{int(x):03d}" for x in df.set_index('index').loc[picks, 'episode_index']}
    leaked = chosen_eps & audit_eps
    if leaked:
        raise RuntimeError(f"[IG-1] audit 에피소드가 프레임 선택에 섞였다: {sorted(leaked)}")
    log(f"누출 검사 통과 (선택된 에피소드 {len(chosen_eps)}개, audit 교집합 0)")

    # ---- 디코딩 ----
    t0 = time.time()
    frames = {}
    for cam in ("observation.images.up", "observation.images.side"):
        p = f"{ROOT}/videos/{cam}/chunk-000/file-000.mp4"
        frames[cam] = load_frames(p, picks)
        log(f"{cam}: {len(frames[cam])}프레임 디코딩 ({time.time()-t0:.0f}s 누적)")
    common = sorted(set(frames["observation.images.up"]) & set(frames["observation.images.side"]))
    log(f"양 카메라 공통 프레임 {len(common)}개")
    res["n_frames_decoded"] = len(common)

    rows = df.set_index("index").loc[common]
    states = np.stack(rows["observation.state"].to_numpy()).astype(np.float32)
    actions = np.stack(rows["action"].to_numpy()).astype(np.float32)
    imgs = torch.stack([
        torch.stack([frames["observation.images.up"][i], frames["observation.images.side"][i]])
        for i in common]).float() / 255.0
    log(f"텐서 구성: images {tuple(imgs.shape)} states {states.shape} actions {actions.shape}")

    s_mean, s_std = states.mean(0), states.std(0) + 1e-6
    a_mean, a_std = actions.mean(0), actions.std(0) + 1e-6
    S = torch.from_numpy((states - s_mean) / s_std)
    A = torch.from_numpy((actions - a_mean) / a_std)

    # ---- 학습 (짧게. 정책 품질이 목적이 아니다) ----
    model = ACTInference().cuda().train()
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4)
    n = len(common)
    log(f"학습 시작: {a.train_steps} step, batch {a.batch}")
    t0 = time.time()
    losses = []
    for step in range(a.train_steps):
        idx = torch.randint(0, n, (a.batch,))
        im = imgs[idx].cuda(non_blocking=True)
        st = S[idx].cuda()
        # 청크 타깃: 해당 프레임의 행동을 chunk 길이만큼 반복 (드라이런 단순화)
        tgt = A[idx].cuda().unsqueeze(1).expand(-1, model.chunk_size, -1)
        pred = model(im, st)
        loss = nn.functional.l1_loss(pred, tgt)
        opt.zero_grad(); loss.backward(); opt.step()
        losses.append(loss.item())
        if step % 50 == 0 or step == a.train_steps - 1:
            log(f"  step {step:4d}  L1 {np.mean(losses[-50:]):.4f}  ({time.time()-t0:.0f}s)")
    res["train_steps"] = a.train_steps
    res["final_l1"] = round(float(np.mean(losses[-50:])), 5)
    res["train_sec"] = round(time.time() - t0, 1)

    model.eval()
    ex = (imgs[:1].cuda(), S[:1].cuda())

    # ---- 캘리브레이션: 실데이터, train 분할에서만 (`IG-1`) ----
    import copy, modelopt.torch.quantization as mtq
    cfg = copy.deepcopy(mtq.INT8_DEFAULT_CFG)
    if a.granularity == "per-tensor":
        for v in cfg["quant_cfg"].values():
            if isinstance(v, dict) and "axis" in v:
                v["axis"] = None
    k = min(a.calib_size, n)
    cal_idx = torch.linspace(0, n - 1, k).round().long()
    log(f"캘리브레이션 {k}개 프레임 (실데이터, train 분할)")

    def forward_loop(m):
        with torch.no_grad():
            for i in cal_idx:
                m(imgs[i:i+1].cuda(), S[i:i+1].cuda())

    t0 = time.time()
    model = mtq.quantize(model, cfg, forward_loop)
    log(f"캘리브레이션 완료 ({time.time()-t0:.0f}s)")
    res["calib_size"] = int(k)

    # ---- export & build ----
    onnx_path = f"{a.outdir}/act_real_int8_{a.granularity}.onnx"
    torch.onnx.export(model, ex, onnx_path, input_names=["images", "state"],
                      output_names=["actions"], opset_version=17,
                      do_constant_folding=True, dynamo=False)
    log(f"ONNX export 완료 ({os.path.getsize(onnx_path)/1e6:.0f} MB)")

    # trtexec를 띄우기 전에 GPU 메모리를 반납한다. 학습 텐서를 쥔 채로 빌드를 시작하면
    # workspace 할당이 실패한다 ("Cuda failure ... out of memory", attempt-009 발견).
    import gc, subprocess
    del imgs, S, A, ex, opt
    model_cpu = model.cpu()
    del model
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    log("GPU 메모리 반납 후 빌드 시작")
    eng = f"{a.outdir}/act_real_int8_{a.granularity}.engine"
    cmd = ["/opt/tensorrt/bin/trtexec", f"--onnx={onnx_path}", f"--saveEngine={eng}",
           "--memPoolSize=workspace:4096", "--skipInference", "--int8"]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
    ok = p.returncode == 0 and os.path.exists(eng)
    log(f"TRT INT8 빌드 {'성공' if ok else '실패'} ({time.time()-t0:.0f}s)")
    if not ok:
        for l in (p.stdout + p.stderr).splitlines()[-12:]:
            log("   " + l.strip())
    res["int8_build_ok"] = ok
    res["int8_build_sec"] = round(time.time() - t0, 1)
    res["G0_real_data_criterion_met"] = ok

    res["norm_stats_hash"] = hash_obj({"s_mean": s_mean, "s_std": s_std,
                                       "a_mean": a_mean, "a_std": a_std})
    with open(f"{a.outdir}/g0_real_result.json", "w") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    log(f"결과: {json.dumps(res, ensure_ascii=False)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
