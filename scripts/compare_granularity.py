"""§4.3 검증 — granularity 축이 실제로 다른 양자화를 만드는가."""
import collections, onnx
from onnx import numpy_helper

def scale_shapes(path):
    m = onnx.load(path); g = m.graph
    produced = {}
    for i in g.initializer:
        produced[i.name] = tuple(i.dims)
    for n in g.node:                      # Constant 노드도 스케일 공급원이 된다
        if n.op_type == "Constant":
            for att in n.attribute:
                if att.name == "value":
                    produced[n.output[0]] = tuple(numpy_helper.to_array(att.t).shape)
    shapes = collections.Counter(); per_axis = 0; unknown = 0
    for n in g.node:
        if n.op_type != "QuantizeLinear" or len(n.input) < 2:
            continue
        if n.input[1] in produced:
            dims = produced[n.input[1]]
            key = "스칼라()" if len(dims) == 0 or dims == (1,) else str(dims)
            shapes[key] += 1
            if len(dims) >= 1 and dims[0] > 1:
                per_axis += 1
        else:
            unknown += 1
    return shapes, per_axis, unknown

rows = {}
for tag, path in [("per-channel", "artifacts/g0/act_int8_per-channel.onnx"),
                  ("per-tensor",  "artifacts/g0/act_int8_per-tensor.onnx")]:
    sh, pa, unk = scale_shapes(path)
    rows[tag] = (sh, pa, unk)
    print(f"\n[{tag}] QuantizeLinear 스케일 모양")
    for k, v in sorted(sh.items(), key=lambda kv: -kv[1])[:6]:
        print(f"    {k:>16} : {v}")
    print(f"    벡터(per-axis) 스케일 노드: {pa}   미해석: {unk}")

pc, pt = rows["per-channel"][1], rows["per-tensor"][1]
print(f"\n판정: per-channel 벡터스케일 {pc}개 vs per-tensor {pt}개 -> ", end="")
print("축이 실제로 다른 양자화를 만든다" if pc != pt else "축이 이름뿐이다 (그리드 재설계 필요)")
