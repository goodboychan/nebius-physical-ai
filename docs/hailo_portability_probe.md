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

## 6. Results (2026-10-14)

Mean `mag` over the 2,000 audit states (p90 in brackets), normalised action units. Device numbers are from the Hailo-8
itself. Reports: `artifacts/reports/hailo_probe_v1.json`.

| | Orin TensorRT INT8 (whole graph) | Hailo-8 device (backbones INT8) | Hailo emulator | Hailo / Orin |
|---|---|---|---|---|
| 16 calibration frames (VC-002 ↔ HL-16) | 0.0544 [0.088] | **0.0476** [0.081] | 0.0458 | 0.87 |
| 1024 calibration frames (VC-020 ↔ HL-1024) | 0.0616 [0.101] | **0.0350** [0.058] | 0.0340 | 0.57 |
| Split check, full-precision emulation (§4.2) | | | 0.0011 (< 0.0028, pass) | |
| Device vs emulator (§4.3) | | 0.026 (HL-16), 0.020 (HL-1024) | | |

Latency on the Pi 5, batch 1, median [p95]. It is the same for both cells.

| Part | ms |
|---|---|
| Hailo-8 backbones | 12.8 [15.6] |
| CPU FP32 tail (onnxruntime, 4 × A76) | 226 [249] |
| Total | 239 [264] |

Reference points: Orin VC-002 34.3 ms, VC-025 FP16 25.4 ms, runner prefetch budget 333 ms.

- **Calibration size works in opposite directions on the two targets.**
  - Going from 16 to 1024 frames *raises* the Orin INT8 error (0.054 → 0.062) and *lowers* the Hailo error
    (0.048 → 0.035).
  - A plausible cause, not tested here: the DFC uses the calibration set for quantization-aware fine-tuning, which
    ran in both cells, so more data helps it. TensorRT/ModelOpt uses the frames only for activation ranges.
  - Either way, the best calibration choice on one target is not the best on the other.
- **The emulator is not the device.** The device-vs-emulator difference (0.020–0.026) is about half of the
  quantization error itself. A gate built on the vendor emulator alone would audit a different model from the
  one that ships.
- **Latency is dominated by the CPU half of the split.** The accelerator part is 13 ms. The FP32 transformer on
  the Pi CPU takes 226 ms. (Corrected in §7: the real deadline is 200 ms, which the total exceeds.)
- The Pi reported a past under-voltage and throttling event (`vcgencmd get_throttled` = 0x50000) when it was checked
  after the runs. Latency may therefore be pessimistic. Error numbers are unaffected.
- **Scope, as stated in §2**: Hailo quantizes only the backbones and Orin quantizes the whole graph. The lower
  Hailo error is therefore not a claim that Hailo quantizes better.
- No real-arm claim follows from this probe (§5).
- Note: `level_notes` in `*_compile.json` matched stale lines from an older shared DFC log (August) and should be
  ignored. The run logs show no level reduction, and quantization-aware fine-tuning ran in both cells.
- Output SNR reported by the DFC: HL-16 20.7 / 20.6 dB, HL-1024 23.2 / 22.9 dB (top / wrist).

## 7. Correction (external review 4, 2026-10-14): the latency budget is 200 ms, not 333 ms

- §4 and §6 compared the Pi's 239 ms to "10 steps at 30 Hz = 333 ms". That is the wrong deadline.
- The runner requests the next chunk when 10 steps remain. It must have the result **before blending starts**, at the
  last 4 steps. So the deadline is (10 − 4) / 30 Hz = **200 ms**; a later chunk counts as late and the loop waits.
  See the `so101_trial.py` docstring.
- The split pipeline's median 239 ms and p95 264 ms are **over** this deadline. With today's runner, every chunk
  would be late.
- "Fits the budget with a thin margin" is therefore withdrawn. The arm was not run on this target, so this is a
  timing statement, not an observed failure.
- Real-arm use would need one of the following, each to be pre-registered:
  - an earlier request (a larger prefetch);
  - a faster CPU tail, e.g. a quantized transformer;
  - running the tail elsewhere.
