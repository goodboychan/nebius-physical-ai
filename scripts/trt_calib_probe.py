"""§4.3 — TRT 캘리브레이션/양자화 동작을 API 레벨에서 직접 확인한다.

문서를 믿지 않고 실제 API 표면을 찍어본다. 확인 목적:
  1) 캘리브레이터 경로(implicit quantization)가 TRT 10.x에서 아직 살아 있는가
  2) `granularity`(per-tensor vs per-channel) 축이 **캘리브레이터 경로에서 제어 가능한가**
     -> 불가능하다면 §4.1의 3축 설계 중 한 축이 실현 불가이며 그리드를 고쳐야 한다
  3) calib_size가 실제로 무엇을 제어하는가 (배치 수 x 배치 크기)
"""
import inspect
import tensorrt as trt

print("TRT", trt.__version__)

print("\n[1] Int8/Calib 관련 심볼")
syms = sorted(x for x in dir(trt) if "Int8" in x or "Calib" in x)
for n in syms:
    print("   ", n)

print("\n[2] BuilderFlag 양자화 관련")
for n in sorted(x for x in dir(trt.BuilderFlag) if not x.startswith("_")):
    if any(k in n.upper() for k in ("INT8", "FP8", "INT4", "FP16", "OBEY", "PREC", "STRICT", "WEIGHT")):
        print("   ", n)

print("\n[3] IInt8Calibrator 인터페이스")
if hasattr(trt, "IInt8Calibrator"):
    for m in ("get_batch", "get_batch_size", "read_calibration_cache",
              "write_calibration_cache", "get_algorithm"):
        print(f"    {m}: {'있음' if hasattr(trt.IInt8Calibrator, m) else '없음'}")
    print("    docstring:", (trt.IInt8Calibrator.__doc__ or "")[:300].replace("\n", " "))
else:
    print("    IInt8Calibrator 없음 — 캘리브레이터 경로 제거됨")

print("\n[4] CalibrationAlgoType")
if hasattr(trt, "CalibrationAlgoType"):
    print("   ", [x for x in dir(trt.CalibrationAlgoType) if not x.startswith("_")])

print("\n[5] per-channel 제어 지점")
for cls, names in [("ITensor", ("set_dynamic_range", "dynamic_range", "dtype")),
                   ("ILayer", ("precision", "set_output_type", "precision_is_set")),
                   ("INetworkDefinition", ("add_quantize", "add_dequantize", "add_scale"))]:
    c = getattr(trt, cls, None)
    print(f"    {cls}:", {n: hasattr(c, n) for n in names} if c else "클래스 없음")

print("\n[6] add_quantize 시그니처 (axis 인자 유무 = per-channel 가능 여부)")
try:
    print("    ", inspect.signature(trt.INetworkDefinition.add_quantize))
except Exception as e:
    print("     시그니처 조회 실패:", e)
print("     doc:", (getattr(trt.INetworkDefinition, "add_quantize").__doc__ or "")[:500].replace("\n", " "))

print("\n[7] IQuantizeLayer 속성 (axis가 있으면 per-axis 스케일 지원)")
if hasattr(trt, "IQuantizeLayer"):
    print("   ", [x for x in dir(trt.IQuantizeLayer) if not x.startswith("_")])

print("\n[8] BuilderConfig의 int8_calibrator 속성")
print("    int8_calibrator:", hasattr(trt.IBuilderConfig, "int8_calibrator"))
