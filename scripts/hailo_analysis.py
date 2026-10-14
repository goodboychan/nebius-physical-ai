"""Hailo portability probe (docs/hailo_portability_probe.md), step 4: offline error table (§4.1–4.3) and latency (§4.4).
mag[n] = sqrt(mean_k ||a - a_ref||^2) in normalised action units, exactly as g4_build_payload.py.
Usage: python hailo_analysis.py <g4 dir> <results dir> <out.json>
  results dir holds <cell>_{fp_optimized,quantized,device}_audit.npz and <cell>_latency.json / <cell>_compile.json"""
import json, os, sys
import numpy as np

g4, rd, out = sys.argv[1:4]
ref = np.load(f"{g4}/audit_ref_fp32.npz")["actions_norm"].astype(np.float64)
P = json.load(open(f"{g4}/g4_payload_index.json"))["cells"]
mag = lambda a, b: np.sqrt(((a - b) ** 2).sum(-1).mean(-1))
summ = lambda m: {"mean": float(m.mean()), "p90": float(np.percentile(m, 90)), "max": float(m.max())}
load = lambda p: np.load(p)["actions_norm"].astype(np.float64) if os.path.exists(p) else None
R = {"reference": {c: summ(mag(load(f"{g4}/outs/{c}_audit.npz"), ref)) | {"orin_gpu_ms_median": P[c]["cheap_C_ms"]}
                   for c in ("VC-002", "VC-020", "VC-025")}, "cells": {}}
for cell, twin in (("HL-16", "VC-002"), ("HL-1024", "VC-020")):
    fp, q, dv = (load(f"{rd}/{cell}_{k}_audit.npz") for k in ("fp_optimized", "quantized", "device"))
    if q is None: continue
    c = {"twin": twin, "split_check_fp_optimized": summ(mag(fp, ref)), "split_check_pass": bool(mag(fp, ref).mean() < P["VC-025"]["mag_mean"])}
    if c["split_check_pass"]:
        c["emulated_int8"] = summ(mag(q, ref))
        if dv is not None:
            c["device_int8"] = summ(mag(dv, ref)); c["device_vs_emulator"] = summ(mag(dv, q))
            c["device_over_twin_mean"] = c["device_int8"]["mean"] / R["reference"][twin]["mean"]
    for k in ("latency", "compile"):
        p = f"{rd}/{cell}_{k}.json"
        if os.path.exists(p): c[k] = json.load(open(p))
    R["cells"][cell] = c
json.dump(R, open(out, "w"), indent=1); print(json.dumps(R, indent=1))
