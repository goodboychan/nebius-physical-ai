#!/bin/bash
# Nebius Job: LeRobot 0.6.1 ACT 학습. 데이터는 S3 볼륨(/s3, ro 아님 — 체크포인트도 같은 볼륨에 쓴다).
# 사용 env: CALIB(팔로워 캘리브레이션 json 경로), DS(버킷 안 데이터셋 경로), OUT(버킷 안 출력 경로), STEPS, BATCH, SEED
# 학습 전에 action을 팔로워 모터 제한으로 자른다(decision_log 2026-10-04): 모터가 실제로 받은 명령과 같게.
set -euo pipefail
echo "[job] $(date -u +%FT%TZ) start DS=$DS OUT=$OUT STEPS=$STEPS BATCH=$BATCH"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
pip install -q --no-cache-dir "lerobot[dataset]==0.6.1" "av>=15,<16" 2>&1 | tail -2
python -c "import lerobot, torch; print('[job] lerobot', lerobot.__version__, 'torch', torch.__version__, 'cuda', torch.cuda.is_available())"
mkdir -p /work && cp -r "/s3/$DS" /work/ds
python - <<'PY'
import json, glob, os, numpy as np, pandas as pd
cal = json.load(open(os.environ["CALIB"]))
names = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
lo, hi = [], []
for n in names:
    c = cal[n]
    if n == "gripper":
        lo.append(0.0); hi.append(100.0)
    else:
        m = (c["range_min"] + c["range_max"]) / 2
        lo.append((c["range_min"] - m) * 360 / 4095); hi.append((c["range_max"] - m) * 360 / 4095)
lo, hi = np.array(lo, np.float32), np.array(hi, np.float32)
allv = []; clipped = 0; total = 0
for f in sorted(glob.glob("/work/ds/data/chunk-*/file-*.parquet")):
    d = pd.read_parquet(f); a = np.stack(d["action"].to_numpy()).astype(np.float32)
    c = np.clip(a, lo, hi); clipped += int((c != a).any(axis=1).sum()); total += len(a)
    d["action"] = list(c); d.to_parquet(f); allv.append(c)
A = np.concatenate(allv)
st = json.load(open("/work/ds/meta/stats.json"))
st["action"].update({"min": A.min(0).tolist(), "max": A.max(0).tolist(), "mean": A.mean(0).tolist(), "std": A.std(0).tolist(),
                     **{f"q{q:02d}": np.quantile(A, q / 100, axis=0).tolist() for q in (1, 10, 50, 90, 99)}})
json.dump(st, open("/work/ds/meta/stats.json", "w"), indent=2)
print(f"[job] action clipped to follower limits: {clipped}/{total} frames")
PY
t0=$(date +%s)
lerobot-train \
  --policy.type=act --policy.device=cuda --policy.push_to_hub=false \
  --dataset.repo_id=local/train --dataset.root=/work/ds --dataset.video_backend=pyav \
  --steps="$STEPS" --batch_size="$BATCH" --seed="$SEED" --num_workers=4 \
  --save_freq="$STEPS" --log_freq=50 --env_eval_freq=0 --wandb.enable=false \
  --output_dir=/work/out --job_name=act
echo "[job] train_sec $(( $(date +%s) - t0 ))"
mkdir -p "/s3/$OUT" && cp -r /work/out/checkpoints/last/pretrained_model "/s3/$OUT/"
ls -la "/s3/$OUT/pretrained_model"
echo "[job] $(date -u +%FT%TZ) done"
