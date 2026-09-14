"""INT8/FP16/FP32 엔진의 출력 차이를 재기 위한 공통 입력을 만든다.

이것이 `score_mag` 기계장치의 축소판이다 — 같은 상태에 대한 행동 차이를 본다.
"""
import numpy as np, os
d = np.load("/out/frames_cache.npz")
ck = __import__("torch").load("/out/act_fp32_reference.pt", map_location="cpu", weights_only=False)
s = ck["norm"]
N = 16
imgs = (d["images"][:N].astype(np.float32) / 255.0)
st = ((d["states"][:N] - s["s_mean"]) / s["s_std"]).astype(np.float32)
os.makedirs("/out/io", exist_ok=True)
for i in range(N):
    imgs[i].tofile(f"/out/io/images_{i:02d}.bin")
    st[i].tofile(f"/out/io/state_{i:02d}.bin")
np.save("/out/io/states.npy", st)
print(f"입력 {N}개 준비: images {imgs[0].shape} state {st[0].shape}")
