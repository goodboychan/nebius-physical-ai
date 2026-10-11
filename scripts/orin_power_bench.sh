#!/bin/bash
# Orin engine power/latency/memory bench (exploratory, decision_log 2026-10-11). Run with the robot idle.
# For each engine: trtexec back-to-back inference for 30 s while tegrastats samples every 100 ms. Also a 30 s idle baseline.
# Output: <out>/<name>.trtexec.log, <name>.tegra.log
set -u
OUT=${1:?out dir}; mkdir -p "$OUT"
T=/usr/src/tensorrt/bin/trtexec
declare -A E=( [VC-000_fp32]=~/edgeqgate/g2/act_g2_100k_fp32.engine [VC-025_fp16]=~/edgeqgate/g3/engines/VC-025.engine
               [VC-002_int8]=~/edgeqgate/g3/engines/VC-002.engine [VC-005_int8]=~/edgeqgate/g3/engines/VC-005.engine
               [VC-020_int8]=~/edgeqgate/g3/engines/VC-020.engine )
nvpmodel -q > "$OUT/nvpmodel.txt" 2>&1
sha256sum "${E[@]}" > "$OUT/engines.sha256"
tegrastats --interval 100 --logfile "$OUT/idle.tegra.log" & P=$!; sleep 30; kill $P
for n in VC-000_fp32 VC-025_fp16 VC-002_int8 VC-005_int8 VC-020_int8; do
  sleep 10
  tegrastats --interval 100 --logfile "$OUT/$n.tegra.log" & P=$!
  $T --loadEngine="${E[$n]}" --warmUp=2000 --duration=30 --useSpinWait > "$OUT/$n.trtexec.log" 2>&1
  kill $P
done
echo done
