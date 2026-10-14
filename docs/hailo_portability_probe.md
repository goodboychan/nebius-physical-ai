# Hailo-8 portability probe v1 (LOCKED before any quantized output)

Status: locked on 2026-10-14 by the commit that adds this file. Exploratory and offline only. No real-arm trial, no
sealed schedule, and no existing verdict depends on it.

## 1. Question

> Does the same G2 ACT checkpoint, taken to a different INT8 accelerator (Hailo-8 on a Raspberry Pi 5), keep the
> offline error and latency we measured for Orin + TensorRT INT8?

The point is the gate's premise: a quantization verdict belongs to a deployment target, not to the word "INT8".

## 2. What was already known before this file (feasibility, 2026-10-14)

- The full ONNX graph (`act_g2_100k.onnx`, sha256 a78ebec2…, the VC-025 base) does not parse on Hailo DFC 3.33.1:
  the transformer's Transpose/Reshape and an axis-0 Split are unsupported.
- The two ResNet backbones, from the `top`/`wrist` inputs up to and including `encoder_img_feat_input_proj{,_1}/Conv`,
  parse completely (104 layers: 42 conv, 2 maxpool, 16 add). The DFC itself recommended these end nodes.
- So the only deployable form is a **split**: backbones in INT8 on Hailo-8, the rest (state projection, transformer,
  action head) in FP32 on the Pi 5 CPU. This differs from the Orin INT8 cells, which quantize the whole graph
  (112 quantized nodes). The comparison is therefore target against target as each can actually be deployed, not
  a like-for-like quantizer comparison.

## 3. Cells

| Code | Calibration frames | Orin counterpart (same frames) |
|---|---|---|
| `HL-16` | 16, success-only (`edgeqgate.calibration`, seed as LOCK-1) | VC-002 (INT8 per-channel, 16 success-only) — the cell run on the arm in G6 |
| `HL-1024` | 1024, success-only (nested superset of the 16) | VC-020 (INT8 per-channel, 1024 success-only) |

- Compiler: Hailo DFC 3.34.0 on kepler (RTX A5000), `hw_arch=hailo8`, `optimization_level=2`, `compression_level=0`.
  If the DFC lowers the level (it may for a small calibration set), the level actually applied is reported.
- Image normalisation (per-channel mean/std from the G2 normaliser) is folded into the HEF, so the device takes
  uint8 RGB.
- The CPU tail is the same ONNX graph, cut at the two Conv outputs, run in onnxruntime FP32.

## 4. Measurements (descriptive, no pass threshold)

On the G4 audit buffer (2,000 audit states, hash d9a52977…), against the GX10 FP32 reference (`audit_ref_fp32.npz`):

1. **Offline error** `mag[n] = sqrt(mean_k ‖a_cell − a_ref‖²)` in normalised action units, as in G4. Reported: mean,
   p90, max, and the Orin counterpart's values from `g4_payload_index.json`.
2. **Split check**: the same pipeline with the DFC's full-precision emulation must reproduce the reference
   (mean `mag` below VC-025 FP16's 0.0028). If it does not, the split is wrong and no INT8 number is reported.
3. **Emulator vs device**: the INT8 cell run in the DFC emulator and on the Hailo-8 itself; mean `mag` of their
   difference.
4. **Latency on the Pi 5** (batch 1, 200 warm calls after 20 discarded): Hailo backbone time, CPU tail time, and
   their sum, median and p95. Reference points: Orin VC-002 34.3 ms and VC-025 25.4 ms (G4 `cheap_C`), and the
   runner's prefetch budget of 10 steps at 30 Hz (333 ms).

## 5. Reading

- Any difference in `mag` between `HL-x` and its Orin counterpart is read as "the INT8 label does not transfer
  between targets in this form", with the scope difference of §2 stated alongside.
- No real-arm claim follows from this probe. A real-arm block (FP32 vs Hailo, 12 vs 12, sealed) would need its own
  pre-registration and is planned after the submission.
