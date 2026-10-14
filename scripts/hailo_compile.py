"""Hailo portability probe (docs/hailo_portability_probe.md), step 2, on the DFC host (kepler, GPU).
- Parse the two backbones (top/wrist -> input_proj Conv), fold the G2 image normalisation into the HEF,
  optimise with the cell's calibration frames, compile a Hailo-8 HEF.
- Emulate on the 2,000 G4 audit states: SDK_FP_OPTIMIZED (split check, §4.2) and SDK_QUANTIZED (§4.3),
  then run the FP32 CPU tail to get actions_norm.
Usage: python hailo_compile.py <G2 onnx> <prepare dir> <audit_npy dir> <cell HL-16|HL-1024> <out dir>"""
import json, os, re, sys, time
import numpy as np, onnxruntime as ort
from hailo_sdk_client import ClientRunner, InferenceContext

onnx_path, prep, audit, cell, out = sys.argv[1:6]; os.makedirs(out, exist_ok=True)
END = ["/m/encoder_img_feat_input_proj/Conv", "/m/encoder_img_feat_input_proj_1/Conv"]
info = json.load(open(f"{prep}/prepare.json")); nz = np.load(f"{prep}/norm.npz")
r = ClientRunner(hw_arch="hailo8")
r.translate_onnx_model(onnx_path, "act_bb", start_node_names=["top", "wrist"], end_node_names=END,
                       net_input_shapes={"top": [1, 3, 480, 640], "wrist": [1, 3, 200, 320]})
L = r.get_hn_dict()["layers"]
ins = sorted(k for k, v in L.items() if v["type"] == "input_layer")
assert len(ins) == 2 and ins[0].endswith("input_layer1") and ins[1].endswith("input_layer2"), ins   # 1 = top, 2 = wrist (parser log)
cam = {ins[0]: "top", ins[1]: "wrist"}
fmt = lambda a: "[" + ", ".join(f"{x * 255:.6f}" for x in a) + "]"
script = "".join(f"normalization{i + 1} = normalization({fmt(nz[f'observation_images_{c}_mean'])}, {fmt(nz[f'observation_images_{c}_std'])}, {k})\n"
                 for i, (k, c) in enumerate(cam.items()))
script += "model_optimization_flavor(optimization_level=2, compression_level=0)\n"
r.load_model_script(script)
cal = np.load(f"{prep}/{cell}_calib.npz")
calib = {k: cal[c].astype(np.float32) for k, c in cam.items()}
t0 = time.time(); r.optimize(calib); t_opt = time.time() - t0
r.save_har(f"{out}/{cell}_quantized.har")
t0 = time.time(); hef = r.compile(); t_comp = time.time() - t0
open(f"{out}/{cell}.hef", "wb").write(hef)

top = np.load(f"{audit}/top.npy", mmap_mode="r"); wrist = np.load(f"{audit}/wrist.npy", mmap_mode="r"); state = np.load(f"{audit}/state.npy")
sess = ort.InferenceSession(f"{prep}/tail.onnx", providers=["CPUExecutionProvider"]); ti = info["tail_inputs"]
smu, ssd = nz["observation_state_mean"], nz["observation_state_std"]

def to_nchw(a): return np.ascontiguousarray(np.transpose(a, (0, 3, 1, 2))).astype(np.float32)
def feats(ctx, lo, hi):
    o = r.infer(ctx, {k: np.asarray((top if c == "top" else wrist)[lo:hi], dtype=np.float32) for k, c in cam.items()})
    o = list(o.values()) if isinstance(o, dict) else list(o)
    o = sorted(o, key=lambda a: -a.shape[1] * a.shape[2])      # top map (15x20) is larger than wrist (7x10)
    return to_nchw(o[0]), to_nchw(o[1])
res = {}
for name, kind in (("fp_optimized", InferenceContext.SDK_FP_OPTIMIZED), ("quantized", InferenceContext.SDK_QUANTIZED)):
    acts = []
    with r.infer_context(kind) as ctx:
        for lo in range(0, len(state), 50):
            ft, fw = feats(ctx, lo, lo + 50)
            for j in range(len(ft)):
                s = ((state[lo + j] - smu) / ssd).astype(np.float32)[None]
                acts.append(sess.run(["actions"], {ti["state"]: s, ti["top_feat"]: ft[j:j + 1], ti["wrist_feat"]: fw[j:j + 1]})[0][0])
    res[name] = np.stack(acts); np.savez(f"{out}/{cell}_{name}_audit.npz", actions_norm=res[name])
log = open(os.path.expanduser("~/.hailo/etc/hailo/dfc/hailo_sdk.client.log")).read() if os.path.exists(os.path.expanduser("~/.hailo/etc/hailo/dfc/hailo_sdk.client.log")) else ""
json.dump({"cell": cell, "model_script": script, "optimize_s": t_opt, "compile_s": t_comp, "hef_bytes": len(hef),
           "level_notes": re.findall(r".*(?:optimization level|Reducing|reduced).*", log)[-10:]}, open(f"{out}/{cell}_compile.json", "w"), indent=1)
print(cell, "done", t_opt, t_comp, flush=True)
