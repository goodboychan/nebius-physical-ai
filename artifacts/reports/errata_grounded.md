# Field reports checked against our measurements (D5 + Nemotron)

Snapshot `ed199938844cf01f…` (Tavily, 25 results). Labels by `nvidia/nemotron-3-super-120b-a12b` (structured output, amendment 1);
every quote and number checked by code. Our numbers come from the facts file, not from the model.

## Accepted matches and contrasts

| Field report | Nemotron | Reference | Our measurement | Supporting quote (verbatim) |
|---|---|---|---|---|
| [How to Quantize Transformer-based model for TensorRT Deployment - The ](https://blog.squeezebits.com/how-to-quantize-transformerbased-model-for-tensorrt-deployment-55802) | MATCHES F3 | MATCHES F1 | Building the INT8 engine with trtexec --int8 alone gave 28.57 ms; with --int8 --fp16 it gave 16.22 ms, because layers without INT8 kernels fell back to FP32 with reformat nodes. ([source](docs/tool_feedback.md#2)) | “brute-force quantization—applying INT8 to all nodes indiscriminately (Figure 2b)—even increased latency by 1.3× compared to the recommended setup, due to loss of kernel fusion opportunities.” |
| [TensorRT Quantization for Jetson Inference - Jetson Orin Nano - NVIDIA](https://forums.developer.nvidia.com/t/tensorrt-quantization-for-jetson-inference/347929) | MATCHES F1 | NOT_APPLICABLE | On this Orin build, INT8 is slower than FP16: GPU compute 16.8 ms per inference for INT8 against 11.6 ms for FP16 (FP32 53.4 ms), measured with trtexec at batch 1. ([source](artifacts/reports/power_bench/SUMMARY.md)) | “TensorRT Model Optimizer INT8 quantization causes 2.7x performance regression on Jetson Orin Nano 4GB (ViT-S + DPT architecture)” |
| [Worse performance after quantization on TensorRT - TensorRT - NVIDIA D](https://forums.developer.nvidia.com/t/worse-performance-after-quantization-on-tensorrt/355549) | MATCHES F1 | MATCHES F1 | On this Orin build, INT8 is slower than FP16: GPU compute 16.8 ms per inference for INT8 against 11.6 ms for FP16 (FP32 53.4 ms), measured with trtexec at batch 1. ([source](artifacts/reports/power_bench/SUMMARY.md)) | “While my FP16/BF16 baseline achieves 580 QPS, the quantized INT8 version drops to 380 QPS.” |
| [Fix YOLO Performance on Jetson Orin Nano: TensorRT ...](https://industrialmonitordirect.com/es/blogs/knowledgebase/resolving-yolo-model-performance-on-jetson-orin-nano-with-tensorrt-export) | CONTRASTS F1 | CONTRASTS F1 | On this Orin build, INT8 is slower than FP16: GPU compute 16.8 ms per inference for INT8 against 11.6 ms for FP16 (FP32 53.4 ms), measured with trtexec at batch 1. ([source](artifacts/reports/power_bench/SUMMARY.md)) | “INT8 quantization can push this to 80-150 FPS on Jetson” |

## Rejected by the validator

| Result | Nemotron | Reference | Rule |
|---|---|---|---|
| [TensorRT Model Optimizer INT8 quantization causes 2.7x perfo](https://forums.developer.nvidia.com/t/tensorrt-model-optimizer-int8-quantization-causes-2-7x-performance-regression-on-jetson-orin-nano-4gb-vit-s-dpt-architecture/357835) | MATCHES F1 | MATCHES F1 | R4: number 24 not in the quote, content or fact |
| [YOLOv8 on Jetson Orin Nano: From PyTorch to TensorRT INT8 --](https://hokwangchoi.com/blog/vision-benchmarks) | CONTRASTS F1 | CONTRASTS F1 | R4: number 15 not in the quote, content or fact |
| [TensorRT Model Optimizer INT8 quantization causes 2.7x perfo](https://forums.developer.nvidia.com/t/tensorrt-model-optimizer-int8-quantization-causes-2-7x-performance-regression-on-jetson-orin-nano-4gb-vit-s-dpt-architecture/357835) | MATCHES F1 | MATCHES F1 | R4: number 114 not in the quote, content or fact; R4: number 42 not in the quote, content or fact |
| [Unable to build model engine for INT8 yolov8m quantized usin](https://forums.developer.nvidia.com/t/unable-to-build-model-engine-for-int8-yolov8m-quantized-using-tensorrt-model-optimizer/304710) | APPLIES_UNVERIFIED  | APPLIES_UNVERIFIED | R3: quote not found in the content |
| [Different version support for TensorRT GA and CUDA between x](https://forums.developer.nvidia.com/t/different-version-support-for-tensorrt-ga-and-cuda-between-x86-64-and-jetpack/339821) | APPLIES_UNVERIFIED  | NOT_APPLICABLE | R3: quote not found in the content |

Primary: 2/6 reference matches/contrasts recovered and accepted; extra positives: ['R12']; accepted 20/25; rejected by rule: {'R4': 4, 'R3': 2}; median latency 4.23 s. Details: docs/errata_grounding_preregistration.md.
