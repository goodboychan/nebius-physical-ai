"""LeRobot ACT의 INT8 양자화 + TRT 빌드 경로 검증.

우리 파이프라인 전체가 이 위에서 돌 수 있는지가 여기서 갈린다.
"""
import os, subprocess, sys, time
import torch

torch.backends.mha.set_fastpath_enabled(False)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lerobot_export_probe import build, Wrap  # noqa


def log(m): print(f"[lq] {m}", flush=True)


def trt(onnx, eng, flags, tag):
    cmd = ["/opt/tensorrt/bin/trtexec", f"--onnx={onnx}", f"--saveEngine={eng}",
           "--memPoolSize=workspace:4096", "--skipInference",
           "--builderOptimizationLevel=3"] + flags
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    ok = p.returncode == 0 and os.path.exists(eng)
    log(f"TRT {tag}: {'성공' if ok else '실패'} ({time.time()-t0:.0f}s)"
        + ("" if ok else " — " + " | ".join(
            [l.strip() for l in (p.stdout+p.stderr).splitlines()
             if "rror" in l or "ailed" in l][-2:])[:300]))
    if ok:
        log(f"   엔진 {os.path.getsize(eng)/1e6:.0f} MB")
    return ok


def main():
    cfg, policy = build()
    w = Wrap(policy.model).cuda().eval()
    ex = (torch.randn(1, 6).cuda(), torch.rand(1, 3, 480, 640).cuda(),
          torch.rand(1, 3, 480, 640).cuda())
    with torch.no_grad():
        log(f"forward {tuple(w(*ex).shape)}")

    ok_fp = trt("/out/lerobot_act.onnx", "/out/lerobot_act_fp16.engine", ["--fp16"], "FP16")

    import copy, modelopt.torch.quantization as mtq
    qcfg = copy.deepcopy(mtq.INT8_DEFAULT_CFG)
    n_cal = 16

    def loop(m):
        with torch.no_grad():
            for _ in range(n_cal):
                m(torch.randn(1, 6).cuda(), torch.rand(1, 3, 480, 640).cuda(),
                  torch.rand(1, 3, 480, 640).cuda())

    t0 = time.time()
    wq = mtq.quantize(w, qcfg, loop)
    log(f"modelopt 캘리브레이션 완료 ({n_cal} 샘플, {time.time()-t0:.0f}s)")

    uncal = [n for n, m in wq.named_modules()
             if hasattr(m, "amax") and getattr(m, "amax", None) is None
             and getattr(m, "is_enabled", True)]
    log(f"미캘리브레이션(활성) 양자화기: {len(uncal)}개")

    wq = wq.cpu()
    exc = tuple(t.cpu() for t in ex)
    p8 = "/out/lerobot_act_int8.onnx"
    torch.onnx.export(wq, exc, p8, input_names=["state", "images_up", "images_side"],
                      output_names=["actions"], opset_version=17,
                      do_constant_folding=True, dynamo=False)
    log(f"INT8 ONNX export 성공 — {os.path.getsize(p8)/1e6:.0f} MB")

    import onnx
    g = onnx.load(p8).graph
    q = sum(1 for n in g.node if n.op_type == "QuantizeLinear")
    log(f"Q/DQ 노드: QuantizeLinear={q}")

    del wq, w
    import gc; gc.collect(); torch.cuda.empty_cache()

    ok8 = trt(p8, "/out/lerobot_act_int8.engine", ["--int8", "--fp16"], "INT8")
    log(f"결과: FP16={ok_fp} INT8={ok8}")
    return 0 if (ok_fp and ok8) else 1


if __name__ == "__main__":
    sys.exit(main())
