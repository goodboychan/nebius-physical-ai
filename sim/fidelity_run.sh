#!/bin/bash
# Sim-to-real outcome agreement (exploratory): replay every rollout of the episode bundle with one fixed physics setting, unassisted.
# Usage: [CALIB=...] [CAMERA=...] sim/fidelity_run.sh <out dir>
OUT=${1:?out}; mkdir -p "$OUT"; L=${EPISODE_BUNDLE:-~/edgeqgate_data/episode_bundle}
for d in $L/rollout_*; do id=$(basename $d)
  [ -f "$OUT/$id/replay_log.json" ] && continue
  timeout 1800 sim/isaac.sh sim/build_scene.py ~/edgeqgate_data/sim_assets/so101_usd/so101_new_calib.usdc sim/scene_estimate.json $d/trajectory.csv "$OUT/$id" \
    --calib ${CALIB:-sim/twin_calibration_v4.json} --camera ${CAMERA:-sim/twin_camera.json} --can-from-video $d/video/top.mp4 --every 30 --use-action --smooth --arm-damp 200 \
    --grip-k 0.6 --mu 1.0 --split-friction --mu-table 0.4 --iters 32 --arm-k 2000 --arm-fmax 3.5 --torsion 0.01 --steps 750 > "$OUT/$id.log" 2>&1
  echo "$id done"
done
echo ALL-DONE
