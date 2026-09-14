"""`G0` 드라이런 — ACT 그래프 -> ONNX -> TRT INT8 빌드.

통과 기준(§10.2 `G0`): "TRT INT8 빌드가 한 번이라도 성공".

경로는 explicit quantization이다. §4.3 확인 결과 TRT 10.1에서 IInt8Calibrator가
deprecated되었고, per-channel 제어 지점(IQuantizeLayer.axis)이 explicit 경로에만 있다.
따라서 캘리브레이션은 modelopt(PyTorch 단)에서 수행하고 TRT는 Q/DQ가 박힌 ONNX를 빌드만 한다.
"""
import argparse, json, os, subprocess, sys, time
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from act_model import ACTInference, make_example_inputs

# PyTorch의 fused multi-head attention fast path는 nn.MultiheadAttention의 out_proj를
# 모듈로 호출하지 않고 융합 커널로 처리한다. 그러면 modelopt가 out_proj에 삽입한
# 양자화기가 캘리브레이션 데이터를 한 번도 보지 못해 amax가 비고, ONNX export가
# "Quantizer has not been calibrated"로 실패한다. 양자화 경로에서는 꺼야 한다.
torch.backends.mha.set_fastpath_enabled(False)


def log(msg):
    print(f"[g0] {msg}", flush=True)


def export_onnx(model, args_tuple, path, opset=17):
    t0 = time.time()
    torch.onnx.export(
        model, args_tuple, path,
        input_names=["images", "state"], output_names=["actions"],
        opset_version=opset, do_constant_folding=True, dynamo=False,
    )
    log(f"ONNX export 완료: {path} ({os.path.getsize(path)/1e6:.1f} MB, {time.time()-t0:.1f}s)")


def build_trt(onnx_path, engine_path, int8=False, fp16=False, extra=None, timeout=1800):
    cmd = ["/opt/tensorrt/bin/trtexec", f"--onnx={onnx_path}", f"--saveEngine={engine_path}",
           "--memPoolSize=workspace:8192", "--skipInference"]
    if int8:
        cmd.append("--int8")
    if fp16:
        cmd.append("--fp16")
    if extra:
        cmd += extra
    log(f"trtexec: {' '.join(cmd[1:])}")
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    dur = time.time() - t0
    ok = p.returncode == 0 and os.path.exists(engine_path)
    tail = [l for l in p.stdout.splitlines() if any(k in l for k in
            ("PASSED", "FAILED", "Error", "error", "Engine built", "Total Host"))][-8:]
    log(f"빌드 {'성공' if ok else '실패'} ({dur:.1f}s, rc={p.returncode})")
    for l in tail:
        log("   " + l.strip())
    if not ok:
        for l in p.stderr.splitlines()[-15:]:
            log("   ERR " + l.strip())
    return ok, dur, p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="/out")
    ap.add_argument("--calib-size", type=int, default=64)
    ap.add_argument("--granularity", choices=["per-tensor", "per-channel"], default="per-channel")
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--skip-fp32", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    result = {"calib_size": a.calib_size, "granularity": a.granularity,
              "resolution": [a.height, a.width]}

    log("ACT 추론 그래프 생성 (무작위 가중치 — 그래프/툴체인 검증용)")
    model = ACTInference().cuda().eval()
    n_params = sum(p.numel() for p in model.parameters())
    log(f"파라미터 {n_params/1e6:.1f}M")
    result["params_M"] = round(n_params / 1e6, 2)
    ex = make_example_inputs(1, h=a.height, w=a.width)

    with torch.no_grad():
        out = model(*ex)
    log(f"FP32 forward OK, 출력 {tuple(out.shape)}")
    result["output_shape"] = list(out.shape)

    # ---- FP32/FP16 기준 빌드 (INT8 실패 시 원인 분리용) ----
    if not a.skip_fp32:
        p32 = os.path.join(a.outdir, "act_fp32.onnx")
        export_onnx(model, ex, p32)
        ok16, d16, _ = build_trt(p32, os.path.join(a.outdir, "act_fp16.engine"), fp16=True)
        result["fp16_build"] = {"ok": ok16, "sec": round(d16, 1)}

    # ---- INT8: modelopt explicit quantization ----
    import modelopt.torch.quantization as mtq
    cfg_name = "INT8_DEFAULT_CFG" if a.granularity == "per-channel" else "INT8_SMOOTHQUANT_CFG"
    base_cfg = getattr(mtq, "INT8_DEFAULT_CFG")
    import copy
    cfg = copy.deepcopy(base_cfg)
    if a.granularity == "per-tensor":
        # 가중치 양자화기의 axis를 None으로 바꿔 per-tensor로 강제한다.
        for k, v in cfg["quant_cfg"].items():
            if isinstance(v, dict) and "axis" in v:
                v["axis"] = None
    log(f"양자화 설정: {a.granularity} (기반 {cfg_name})")

    calib_imgs, calib_states = [], []
    for _ in range(a.calib_size):
        i, s = make_example_inputs(1, h=a.height, w=a.width)
        calib_imgs.append(i)
        calib_states.append(s)

    def forward_loop(m):
        with torch.no_grad():
            for i, s in zip(calib_imgs, calib_states):
                m(i, s)

    t0 = time.time()
    model = mtq.quantize(model, cfg, forward_loop)
    log(f"캘리브레이션 완료 ({a.calib_size} 샘플, {time.time()-t0:.1f}s)")
    result["calib_sec"] = round(time.time() - t0, 1)

    # 캘리브레이션 누락 진단: amax가 빈 양자화기를 export 전에 세어 본다.
    uncal = [n for n, m in model.named_modules()
             if hasattr(m, "amax") and getattr(m, "amax", None) is None]
    log(f"미캘리브레이션 양자화기: {len(uncal)}개")
    for n in uncal[:8]:
        log("   " + n)
    result["uncalibrated_quantizers"] = len(uncal)

    pq = os.path.join(a.outdir, f"act_int8_{a.granularity}.onnx")
    export_onnx(model, ex, pq)

    import onnx
    g = onnx.load(pq).graph
    qn = sum(1 for n in g.node if n.op_type == "QuantizeLinear")
    dqn = sum(1 for n in g.node if n.op_type == "DequantizeLinear")
    log(f"ONNX Q/DQ 노드: QuantizeLinear={qn}, DequantizeLinear={dqn}")
    result["qdq_nodes"] = {"QuantizeLinear": qn, "DequantizeLinear": dqn}

    ok8, d8, rc = build_trt(pq, os.path.join(a.outdir, f"act_int8_{a.granularity}.engine"), int8=True)
    result["int8_build"] = {"ok": ok8, "sec": round(d8, 1), "rc": rc}
    result["G0_criterion_met"] = bool(ok8)

    with open(os.path.join(a.outdir, f"g0_result_{a.granularity}_{a.calib_size}.json"), "w") as f:
        json.dump(result, f, indent=2)
    log(f"결과: {json.dumps(result, ensure_ascii=False)}")
    return 0 if ok8 else 1


if __name__ == "__main__":
    sys.exit(main())
