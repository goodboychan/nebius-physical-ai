#!/bin/bash
# Follow-up to orin_power_bench.sh (exploratory, external review 6): the position-fine-tuned engine FT-FP16 had no
# measurement of its own. Same protocol; VC-025 is re-run in the same session as a drift reference. Run with the robot idle.
set -u
OUT=${1:?out dir}; mkdir -p "$OUT"
T=/usr/src/tensorrt/bin/trtexec
declare -A E=( [FT-FP16_fp16]=~/edgeqgate/ft/engines/FT-FP16.engine [VC-025_fp16]=~/edgeqgate/g3/engines/VC-025.engine )
nvpmodel -q > "$OUT/nvpmodel.txt" 2>&1
sha256sum "${E[@]}" > "$OUT/engines.sha256"
tegrastats --interval 100 --logfile "$OUT/idle.tegra.log" & P=$!; sleep 30; kill $P
for n in FT-FP16_fp16 VC-025_fp16; do
  sleep 10
  tegrastats --interval 100 --logfile "$OUT/$n.tegra.log" & P=$!
  $T --loadEngine="${E[$n]}" --warmUp=2000 --duration=30 --useSpinWait > "$OUT/$n.trtexec.log" 2>&1
  kill $P
done
echo done
