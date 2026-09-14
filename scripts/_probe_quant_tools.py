import importlib
mods = ["modelopt", "modelopt.onnx.quantization", "modelopt.torch.quantization",
        "pytorch_quantization", "onnxruntime", "onnxruntime.quantization", "onnx"]
for m in mods:
    try:
        mod = importlib.import_module(m)
        print(f"  OK   {m}  {getattr(mod, '__version__', '')}")
    except Exception as e:
        print(f"  없음 {m}  ({type(e).__name__})")
