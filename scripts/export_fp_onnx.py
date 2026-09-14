"""레퍼런스 체크포인트에서 비양자화 ONNX를 뽑는다 (FP16/FP32 빌드용, `VC-000`/`VC-025`)."""
import os, sys
import numpy as np, torch
sys.path.insert(0, "/src"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
torch.backends.mha.set_fastpath_enabled(False)
from act_model import ACTInference

ck = torch.load("/out/act_fp32_reference.pt", map_location="cpu", weights_only=False)
net = ACTInference(); net.load_state_dict(ck["state_dict"]); net = net.cuda().eval()
d = np.load("/out/frames_cache.npz")
imgs = torch.from_numpy(d["images"][:1]).float().cuda() / 255.0
s = ck["norm"]
S = torch.from_numpy((d["states"][:1] - s["s_mean"]) / s["s_std"]).float().cuda()
out = "/out/act_fp_reference.onnx"
torch.onnx.export(net, (imgs, S), out, input_names=["images", "state"],
                  output_names=["actions"], opset_version=17,
                  do_constant_folding=True, dynamo=False)
print(f"export 완료: {os.path.getsize(out)/1e6:.0f} MB")
