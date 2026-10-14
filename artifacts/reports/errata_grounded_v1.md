# Field reports checked against our measurements (D5 + Nemotron)

Snapshot `ed199938844cf01f…` (Tavily, 25 results). Labels by `nvidia/nemotron-3-super-120b-a12b`; every quote and number checked by code.
Our numbers in the table come from the facts file, not from the model.

| Field report | Label | Our measurement | Supporting quote (verbatim) |
|---|---|---|---|
| [How to Quantize Transformer-based model for TensorRT Deployment - The ](https://blog.squeezebits.com/how-to-quantize-transformerbased-model-for-tensorrt-deployment-55802) | MATCHES F4 | modelopt left a quantizer uncalibrated ('Quantizer has not been calibrated') because PyTorch's fused multi-head-attention fast path bypassed the out_proj module; disabling the fast path fixed it. ([source](docs/tool_feedback.md#1)) | “complex architectural components—such as multi-head attention and RoPE, often introduced to boost model performance—make it difficult for frameworks like TensorRT to automatically identify operations ” |
| [Fix YOLO Performance on Jetson Orin Nano: TensorRT ...](https://industrialmonitordirect.com/es/blogs/knowledgebase/resolving-yolo-model-performance-on-jetson-orin-nano-with-tensorrt-export) | CONTRASTS F1 | On this Orin build, INT8 is slower than FP16: GPU compute 16.8 ms per inference for INT8 against 11.6 ms for FP16 (FP32 53.4 ms), measured with trtexec at batch 1. ([source](artifacts/reports/power_bench/SUMMARY.md)) | “INT8 quantization can push this to 80-150 FPS on Jetson” |

Primary: 1/6 reference matches/contrasts recovered; extra positives: none; accepted 10/25; rejected by rule: {'R1': 14, 'R3': 1}; median latency 4.18 s.
