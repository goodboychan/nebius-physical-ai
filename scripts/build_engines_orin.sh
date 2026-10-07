#!/bin/bash
# §4 변형 그리드 2단계(Orin): 셀별 ONNX → TensorRT 엔진. 동결 timing cache 복사본으로 빌드한다 (decision_log 2026-10-07 #1).
#   1) 워밍업: 그리드와 무관한 WARMUP-per-tensor / WARMUP-per-channel(INT8) + FP32 레퍼런스 ONNX(FP16)를 한 캐시에 빌드 → 동결(444)
#   2) 셀마다 동결본을 임시 파일로 복사해 쓰고 버린다. 셀 N이 셀 1..N−1에 의존하지 않는다(§4.2)
#   3) 결정성 확인: 첫 셀을 두 번 빌드해 엔진 해시가 같은지 본다
# 빌드 옵션은 여기 한 곳에서만 정한다(§4.2). 사용: build_engines_orin.sh <onnx 폴더> <출력 폴더> [셀...]
set -euo pipefail
IN=$1; OUT=$2; shift 2
TRTEXEC=/usr/src/tensorrt/bin/trtexec
FLAGS=(--memPoolSize=workspace:4096 --builderOptimizationLevel=3 --skipInference)
mkdir -p "$OUT"; LOG="$OUT/build.jsonl"; FROZEN="$OUT/frozen.timing.cache"
prec_flags() { case "$1" in int8) echo "--int8 --fp16";; fp16) echo "--fp16";; esac; }
build() {  # onnx engine precision cache
  local s=$SECONDS
  $TRTEXEC --onnx="$1" --saveEngine="$2" ${FLAGS[@]} $(prec_flags "$3") --timingCacheFile="$4" > "$2.log" 2>&1 || { echo "FAIL $1"; tail -5 "$2.log"; return 1; }
  echo $(( SECONDS - s ))
}
if [ ! -f "$FROZEN" ]; then
  echo "[orin] 워밍업 캐시 생성"
  for w in WARMUP-per-tensor WARMUP-per-channel; do build "$IN/$w.onnx" "$OUT/$w.engine" int8 "$FROZEN.tmp" >/dev/null; done
  build "$IN/act_g2_100k.onnx" "$OUT/WARMUP-fp16.engine" fp16 "$FROZEN.tmp" >/dev/null
  mv "$FROZEN.tmp" "$FROZEN"; chmod 444 "$FROZEN"
fi
CACHE_SHA=$(sha256sum "$FROZEN" | cut -c1-64); echo "[orin] frozen cache $CACHE_SHA"
META=$(python3 -c "import tensorrt as t,json,subprocess as s;print(json.dumps({'tensorrt':t.__version__,'nvpmodel':s.run(['nvpmodel','-q'],capture_output=True,text=True).stdout.split(chr(10))[0]}))")
CELLS=("$@"); [ ${#CELLS[@]} -eq 0 ] && CELLS=($(python3 -c "import json;r=json.load(open('$IN/onnx_results.json'));print(' '.join(sorted(r)))"))
first=1
for c in "${CELLS[@]}"; do
  [ -f "$OUT/$c.engine" ] && { echo "[orin] $c 있음"; continue; }
  P=$(python3 -c "import json;print(json.load(open('$IN/onnx_results.json'))['$c']['precision'])")
  cp "$FROZEN" /tmp/cell.cache; chmod 644 /tmp/cell.cache
  sec=$(build "$IN/$c.onnx" "$OUT/$c.engine" "$P" /tmp/cell.cache) || { echo "{\"code\":\"$c\",\"ok\":false}" >> "$LOG"; continue; }
  rep=""
  if [ $first -eq 1 ]; then   # 결정성: 같은 ONNX를 같은 동결본으로 한 번 더
    cp "$FROZEN" /tmp/cell.cache; chmod 644 /tmp/cell.cache
    build "$IN/$c.onnx" /tmp/rebuild.engine "$P" /tmp/cell.cache >/dev/null
    rep=$(sha256sum /tmp/rebuild.engine | cut -c1-64); rm -f /tmp/rebuild.engine; first=0
  fi
  E=$(sha256sum "$OUT/$c.engine" | cut -c1-64)
  echo "{\"code\":\"$c\",\"ok\":true,\"precision\":\"$P\",\"build_sec\":$sec,\"engine_sha256\":\"$E\",\"onnx_sha256\":\"$(sha256sum "$IN/$c.onnx" | cut -c1-64)\",\"frozen_cache_sha256\":\"$CACHE_SHA\",\"rebuild_sha256\":\"$rep\",\"flags\":\"${FLAGS[*]} $(prec_flags $P)\",\"env\":$META}" >> "$LOG"
  echo "[orin] $c ${sec}s ${E:0:12}${rep:+ rebuild ${rep:0:12}}"
  rm -f /tmp/cell.cache
done
