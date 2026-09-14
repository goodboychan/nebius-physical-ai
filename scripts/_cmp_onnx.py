import onnx, numpy as np
from onnx import numpy_helper
for p in ["/out/act_fp32.onnx", "/out/act_int8_per-channel.onnx", "/out/act_real_int8_per-channel.onnx"]:
    try:
        m = onnx.load(p)
    except Exception as e:
        print(f"{p}: 로드 실패 {e}"); continue
    g = m.graph
    tot = 0; dtypes = {}
    for i in g.initializer:
        a = numpy_helper.to_array(i)
        tot += a.nbytes
        dtypes[str(a.dtype)] = dtypes.get(str(a.dtype), 0) + a.nbytes
    print(f"{p.split('/')[-1]:<34} 노드 {len(g.node):>5}  initializer {tot/1e6:7.1f} MB  "
          f"dtypes={ {k: round(v/1e6,1) for k,v in dtypes.items()} }")
