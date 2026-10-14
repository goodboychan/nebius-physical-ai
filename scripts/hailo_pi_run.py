"""Hailo portability probe (docs/hailo_portability_probe.md), step 3, on the Raspberry Pi 5 + Hailo-8.
- Device outputs on the 2,000 G4 audit states: HEF backbones (uint8 RGB in, float out) + FP32 onnxruntime tail.
- Latency (§4.4): batch 1, 20 discarded then 200 timed calls; backbone, tail and total, median and p95.
Usage: python hailo_pi_run.py <cell.hef> <tail.onnx> <norm.npz> <prepare.json> <audit_npy dir> <out prefix>"""
import json, sys, time
import numpy as np, onnxruntime as ort
from hailo_platform import (HEF, VDevice, ConfigureParams, HailoStreamInterface, InferVStreams, InputVStreamParams,
                            OutputVStreamParams, FormatType)

hef_p, tail_p, norm_p, prep_p, audit, out = sys.argv[1:7]
nz = np.load(norm_p); ti = json.load(open(prep_p))["tail_inputs"]
smu, ssd = nz["observation_state_mean"], nz["observation_state_std"]
top = np.load(f"{audit}/top.npy", mmap_mode="r"); wrist = np.load(f"{audit}/wrist.npy", mmap_mode="r"); state = np.load(f"{audit}/state.npy")
sess = ort.InferenceSession(tail_p, providers=["CPUExecutionProvider"])
hef = HEF(hef_p)
iinfo = {i.name: i.shape for i in hef.get_input_vstream_infos()}
cam = {n: ("top" if s[0] == 480 else "wrist") for n, s in iinfo.items()}           # NHWC shapes without batch
assert sorted(cam.values()) == ["top", "wrist"], iinfo

def tail(s_raw, ft, fw):
    s = ((s_raw - smu) / ssd).astype(np.float32)[None]
    return sess.run(["actions"], {ti["state"]: s, ti["top_feat"]: ft, ti["wrist_feat"]: fw})[0][0]

with VDevice() as dev:
    ng = dev.configure(hef, ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe))[0]
    ivp = InputVStreamParams.make(ng, format_type=FormatType.UINT8); ovp = OutputVStreamParams.make(ng, format_type=FormatType.FLOAT32)
    with InferVStreams(ng, ivp, ovp) as pipe, ng.activate(ng.create_params()):
        def backbone(lo, hi):
            o = pipe.infer({n: np.ascontiguousarray((top if c == "top" else wrist)[lo:hi]) for n, c in cam.items()})
            o = sorted(o.values(), key=lambda a: -a.shape[1] * a.shape[2])
            return [np.ascontiguousarray(np.transpose(a, (0, 3, 1, 2))).astype(np.float32) for a in o]
        acts = []
        for lo in range(0, len(state), 20):
            ft, fw = backbone(lo, lo + 20)
            acts += [tail(state[lo + j], ft[j:j + 1], fw[j:j + 1]) for j in range(len(ft))]
        np.savez(f"{out}_device_audit.npz", actions_norm=np.stack(acts))
        tb, tt = [], []
        for n in range(220):
            i = n % len(state); t0 = time.perf_counter(); ft, fw = backbone(i, i + 1); t1 = time.perf_counter(); tail(state[i], ft, fw); t2 = time.perf_counter()
            if n >= 20: tb.append((t1 - t0) * 1e3); tt.append((t2 - t1) * 1e3)
q = lambda a, p: float(np.percentile(a, p))
tot = np.add(tb, tt)
res = {"backbone_ms": [q(tb, 50), q(tb, 95)], "tail_ms": [q(tt, 50), q(tt, 95)], "total_ms": [q(tot, 50), q(tot, 95)],
       "ort_threads": sess.get_session_options().intra_op_num_threads, "n_timed": len(tb)}
json.dump(res, open(f"{out}_latency.json", "w"), indent=1); print(json.dumps(res))
