"""학습된 LeRobot ACT 체크포인트(pretrained_model 폴더) → ONNX. 실제 녹화 프레임 1개로 torch와 ONNX 출력을 비교한다.
입력은 정규화된 텐서(전처리기 적용 후)이며, 정규화·역정규화는 런타임 쪽 processor가 맡는다.
사용(컨테이너 edgeqgate-lerobot:25.11): python export_trained_act.py <ckpt_dir> <dataset_root> <out.onnx>"""
import sys, os, json, time
import numpy as np, torch, av, pandas as pd
torch.backends.mha.set_fastpath_enabled(False)   # attempt-003: fused MHA fast path가 export·양자화를 깨뜨린다
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.utils.constants import OBS_IMAGES, OBS_STATE
from safetensors.torch import load_file

ckpt, root, out = sys.argv[1:4]
pol = ACTPolicy.from_pretrained(ckpt).eval().cpu()
cams = [k for k in pol.config.input_features if k.startswith("observation.images.")]
print("cameras (order):", cams)

class Wrap(torch.nn.Module):
    def __init__(self, m):
        super().__init__(); self.m = m
    def forward(self, state, *imgs):
        r = self.m({OBS_STATE: state, OBS_IMAGES: list(imgs)})
        return r[0] if isinstance(r, (tuple, list)) else r

# 실제 프레임 1개(에피소드 0, 프레임 100)와 학습 정규화 통계로 입력을 만든다
norm = load_file(os.path.join(ckpt, "policy_preprocessor_step_3_normalizer_processor.safetensors"))
d = pd.read_parquet(f"{root}/data/chunk-000/file-000.parquet"); i = 100
st = torch.tensor(np.stack(d["observation.state"].to_numpy())[i:i + 1], dtype=torch.float32)
st = (st - norm["observation.state.mean"]) / norm["observation.state.std"]
imgs = []
for k in cams:
    c = av.open(f"{root}/videos/{k}/chunk-000/file-000.mp4")
    f = next(fr for j, fr in enumerate(c.decode(video=0)) if j == i).to_ndarray(format="rgb24")
    x = torch.from_numpy(f).permute(2, 0, 1)[None].float() / 255.0
    imgs.append((x - norm[f"{k}.mean"]) / norm[f"{k}.std"])
w = Wrap(pol.model).eval()
with torch.no_grad():
    ref = w(st, *imgs)
t0 = time.time()
torch.onnx.export(w, (st, *imgs), out, input_names=["state"] + [k.split(".")[-1] for k in cams],
                  output_names=["actions"], opset_version=17, do_constant_folding=True, dynamo=False)
print(f"ONNX {os.path.getsize(out)/1e6:.0f} MB ({time.time()-t0:.0f}s)")
import onnxruntime as ort
sess = ort.InferenceSession(out, providers=["CPUExecutionProvider"])
o = sess.run(None, {n.name: v.numpy() for n, v in zip(sess.get_inputs(), [st, *imgs])})[0]
err = np.abs(o - ref.numpy())
print(f"torch vs onnx (normalized actions, shape {o.shape}): max {err.max():.2e}  mean {err.mean():.2e}")
np.savez(out.replace(".onnx", "_io.npz"), state=st.numpy(), **{k.split(".")[-1]: v.numpy() for k, v in zip(cams, imgs)}, ref=ref.numpy())
