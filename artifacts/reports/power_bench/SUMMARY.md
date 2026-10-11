# Orin engine bench (2026-10-11 23:37, robot idle, nvpmodel 15W)

Exploratory. Each engine runs back-to-back on trtexec for 30 s after a 2 s warm-up, while tegrastats samples every 100 ms.
Latency is GPU compute time per inference: batch 1, both cameras plus state, one 100-step chunk. It excludes the
runner's preprocessing and socket round trip; the end-to-end figures in G6 are INT8 ≈ 34 ms and FP32 ≈ 79 ms. Power is
the median VDD_IN (whole module). Energy per inference = (median VDD_IN − idle VDD_IN) / throughput.

| Engine | Precision | Size | GPU ms (median / p99) | Throughput | VDD_IN | CPU+GPU rail | ΔEnergy / inference |
|---|---|---|---|---|---|---|---|
| idle | — | — | — | — | 4.86 W | 1.18 W | — |
| VC-000 | FP32 (no TF32) | 175 MB | 53.4 / 53.6 | 18.7 qps | 12.40 W | 6.56 W | 403 mJ |
| VC-025 | FP16 | 72 MB | **11.6 / 11.6** | **86.1 qps** | 11.97 W | 6.05 W | **82 mJ** |
| VC-002 | INT8 (calib 16, success-only, per-channel) | 57 MB | 16.8 / 16.9 | 59.3 qps | 10.85 W | 4.85 W | 101 mJ |
| VC-005 | INT8 (calib 16, late-phase-only, per-tensor) | 57 MB | 17.1 / 17.2 | 58.3 qps | 10.73 W | 4.78 W | 101 mJ |
| VC-020 | INT8 (calib 1024, success-only, per-channel) | 57 MB | 16.8 / 16.9 | 59.3 qps | 10.87 W | 4.89 W | 101 mJ |

- FP16 is the fastest engine and uses the least energy per inference on this Orin and TensorRT 10.3 build. INT8 draws
  about 1.1 W less while running, but takes 45% longer per inference. It is smallest on disk.
- The three INT8 cells are indistinguishable in latency, power and energy, so calibration choice does not change the
  cost axis.
- At the deployed duty cycle (one chunk per 90 steps ≈ 3 s at 30 Hz), inference energy is ≤ 0.13 W on average for
  every engine. The cost differences matter for latency headroom and for multi-policy or larger-model budgets, not for
  this single ACT's power draw.
- Limitation: the 15W power mode was in use, not MAXN. The numbers are for this mode only.
