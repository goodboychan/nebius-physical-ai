## Errata (`D5` 자동 수집)

> 수집 시각 2026-10-07T08:14:40+00:00 · provider `tavily` · 스냅샷 해시 `ed199938844cf01fac9343221877cf4f5cf509a36113eff926de083e996abc77`
>
> **검색 결과는 시간에 따라 변한다.** 이 절의 근거는 위 해시로 동결된 스냅샷이며,
> `artifacts/retrieval/`의 동결본으로 재현할 수 있다. 사람이 검토하기 전까지
> 여기 링크된 내용을 사실로 인용하지 말 것.

대상 환경: TensorRT 10.3.0 · Jetson Orin Nano Super · CUDA 12.6 · sm_87

### 질의: TensorRT 10.3.0 known issues release notes
- [TensorRT 10.3.0 Release Notes — NVIDIA TensorRT](https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/getting-started/release-notes-10/10.3.0.html) (score 0.89)
- [Release Notes — TensorRT LLM](https://nvidia.github.io/TensorRT-LLM/release-notes.html) (score 0.86)
- [Release Notes — TensorRT-LLM](https://nvidia.github.io/TensorRT-LLM/0.19.0/release-notes.html) (score 0.85)
- [TensorRT-Release-Notes.pdf](https://www.collegesidekick.com/study-docs/14518341) (score 0.82)
- [Releases · NVIDIA/TensorRT · GitHub](https://github.com/NVIDIA/TensorRT/releases) (score 0.80)

### 질의: TensorRT INT8 explicit quantization Q/DQ transformer attention fusion issue
- [Explicit INT8 Quantization Fails to Fuse Concat-Conv Block ...](https://github.com/NVIDIA/TensorRT/issues/4401) (score 0.80)
- [Explicit Quantization — NVIDIA TensorRT](https://docs.nvidia.com/deeplearning/tensorrt/latest/inference-library/quantized-types-explicit-quantization.html) (score 0.80)
- [[question] Myelin: attention fusion and FlashAttention · Issue #3243 · NVIDIA/TensorRT · G](https://github.com/NVIDIA/TensorRT/issues/3243) (score 0.66)
- [How to Quantize Transformer-based model for TensorRT Deployment - The official SqueezeBits](https://blog.squeezebits.com/how-to-quantize-transformerbased-model-for-tensorrt-deployment-55802) (score 0.65)
- [Practical aspects about neural networks quantization with TensorRT - TensorRT - NVIDIA Dev](https://forums.developer.nvidia.com/t/practical-aspects-about-neural-networks-quantization-with-tensorrt/248336) (score 0.64)

### 질의: Jetson Orin Nano Super TensorRT INT8 performance regression
- [TensorRT Model Optimizer INT8 quantization causes 2.7x performance regression on Jetson Or](https://forums.developer.nvidia.com/t/tensorrt-model-optimizer-int8-quantization-causes-2-7x-performance-regression-on-jetson-orin-nano-4gb-vit-s-dpt-architecture/357835) (score 0.92)
- [TensorRT Quantization for Jetson Inference - Jetson Orin Nano - NVIDIA Developer Forums](https://forums.developer.nvidia.com/t/tensorrt-quantization-for-jetson-inference/347929) (score 0.87)
- [Worse performance after quantization on TensorRT - TensorRT - NVIDIA Developer Forums](https://forums.developer.nvidia.com/t/worse-performance-after-quantization-on-tensorrt/355549) (score 0.86)
- [YOLOv8 on Jetson Orin Nano: From PyTorch to TensorRT INT8 -- Hokwang Choi](https://hokwangchoi.com/blog/vision-benchmarks) (score 0.85)
- [Fix YOLO Performance on Jetson Orin Nano: TensorRT ...](https://industrialmonitordirect.com/es/blogs/knowledgebase/resolving-yolo-model-performance-on-jetson-orin-nano-with-tensorrt-export) (score 0.81)

### 질의: TensorRT ModelOpt quantized ONNX build failure Jetson
- [ONNX model conversion failure of TensorRT 10.3 when running trtexec on GPU Jetson Orin · I](https://github.com/NVIDIA/TensorRT/issues/4494) (score 0.85)
- [TensorRT Quantization for Jetson Inference - Jetson Orin Nano - NVIDIA Developer Forums](https://forums.developer.nvidia.com/t/tensorrt-quantization-for-jetson-inference/347929) (score 0.82)
- [TensorRT Model Optimizer INT8 quantization causes 2.7x performance regression on Jetson Or](https://forums.developer.nvidia.com/t/tensorrt-model-optimizer-int8-quantization-causes-2-7x-performance-regression-on-jetson-orin-nano-4gb-vit-s-dpt-architecture/357835) (score 0.82)
- [Unable to build model engine for INT8 yolov8m quantized using tensorrt model optimizer - T](https://forums.developer.nvidia.com/t/unable-to-build-model-engine-for-int8-yolov8m-quantized-using-tensorrt-model-optimizer/304710) (score 0.79)
- [utils.export.engine API Reference | Ultralytics](https://docs.ultralytics.com/reference/utils/export/engine) (score 0.68)

### 질의: TensorRT 10.3.0 JetPack compatibility engine version
- [Does TensorRT 10.3.0.30-1+cuda12.5 support cuda 12.6 jetpack 6.1 - TensorRT - NVIDIA Devel](https://forums.developer.nvidia.com/t/does-tensorrt-10-3-0-30-1-cuda12-5-support-cuda-12-6-jetpack-6-1/344194) (score 0.83)
- [Erroneous mismatch in TensorRT serializations on JetPack 6 (L4T 36.4.0) - Jetson Orin NX -](https://forums.developer.nvidia.com/t/erroneous-mismatch-in-tensorrt-serializations-on-jetpack-6-l4t-36-4-0/353515) (score 0.79)
- [Different version support for TensorRT GA and CUDA between x86_64 and Jetpack - Jetson Nan](https://forums.developer.nvidia.com/t/different-version-support-for-tensorrt-ga-and-cuda-between-x86-64-and-jetpack/339821) (score 0.76)
- [Torch-TensorRT in JetPack — Torch-TensorRT](https://docs.pytorch.org/TensorRT/getting_started/jetpack.html) (score 0.71)
- [NVIDIA Jetson Software Stack: JetPack, CUDA & TensorRT](https://turingpi.com/nvidia-jetson-software-stack) (score 0.70)
