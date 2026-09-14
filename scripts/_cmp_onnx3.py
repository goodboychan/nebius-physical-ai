import onnx
from onnx import numpy_helper
for p in ["/out/act_int8_per-channel.onnx", "/out/act_real_int8_per-channel.onnx"]:
    g = onnx.load(p).graph
    init = sum(numpy_helper.to_array(i).nbytes for i in g.initializer)
    const = 0
    for n in g.node:
        if n.op_type == "Constant":
            for att in n.attribute:
                if att.name == "value":
                    const += numpy_helper.to_array(att.t).nbytes
    import os
    print(f"{p.split('/')[-1]:<34} initializer {init/1e6:7.1f} MB + Constant {const/1e6:7.1f} MB "
          f"= {(init+const)/1e6:7.1f} MB   (파일 {os.path.getsize(p)/1e6:.1f} MB)")
