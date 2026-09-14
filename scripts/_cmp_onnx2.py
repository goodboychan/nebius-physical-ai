import onnx, collections
from onnx import numpy_helper
def summarize(p):
    g = onnx.load(p).graph
    names = [i.name for i in g.initializer]
    groups = collections.Counter()
    bytes_by = collections.Counter()
    for i in g.initializer:
        a = numpy_helper.to_array(i)
        key = ("backbone" if "backbone" in i.name else
               "encoder" if "encoder" in i.name else
               "decoder" if "decoder" in i.name else
               "other")
        groups[key] += 1; bytes_by[key] += a.nbytes
    ops = collections.Counter(n.op_type for n in g.node)
    return groups, bytes_by, ops, len(names)

for p in ["/out/act_int8_per-channel.onnx", "/out/act_real_int8_per-channel.onnx"]:
    gr, by, ops, n = summarize(p)
    print(f"\n=== {p.split('/')[-1]} (initializer {n}개) ===")
    for k in ("backbone", "encoder", "decoder", "other"):
        print(f"   {k:<10} {gr[k]:>4}개  {by[k]/1e6:7.1f} MB")
    print("   주요 op:", dict(ops.most_common(8)))
