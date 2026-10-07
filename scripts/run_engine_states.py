"""Orin(python3.10, tensorrt 10.3)에서 셀 엔진 하나로 고정 상태 집합(감사 2,000 / train 2,000)의 action chunk를 낸다 (`G4`).
입력은 학습과 같은 정규화. 출력은 정규화 단위 actions (N,100,6) — 오차는 GX10 FP32 레퍼런스와 같은 단위로 비교한다.
지연(`score_cheap_C`)은 GPU 실행만(H2D·D2H 제외) CUDA 이벤트로 잰다. 다른 GPU 작업이 없을 때 돌린다.
사용: python3 run_engine_states.py <engine> <states 폴더(.npy)> <norm_stats.npz> <out.npz>"""
import sys, time
import numpy as np, tensorrt as trt
from cuda.bindings import runtime as rt

eng_p, sdir, stats_p, out_p = sys.argv[1:5]
def ck(r):
    err = r[0] if isinstance(r, tuple) else r
    if int(err) != 0: raise RuntimeError(f"CUDA error {err}")
    return r[1] if isinstance(r, tuple) and len(r) > 1 else None
ns = np.load(stats_p)
S = np.load(f"{sdir}/state.npy"); TOP = np.load(f"{sdir}/top.npy", mmap_mode="r"); WR = np.load(f"{sdir}/wrist.npy", mmap_mode="r")
eng = trt.Runtime(trt.Logger(trt.Logger.WARNING)).deserialize_cuda_engine(open(eng_p, "rb").read()); ctx = eng.create_execution_context()
names = [eng.get_tensor_name(i) for i in range(eng.num_io_tensors)]
host, dev = {}, {}
for n in names:
    host[n] = np.zeros(tuple(eng.get_tensor_shape(n)), trt.nptype(eng.get_tensor_dtype(n))); dev[n] = ck(rt.cudaMalloc(host[n].nbytes)); ctx.set_tensor_address(n, dev[n])
stream = ck(rt.cudaStreamCreate()); e0, e1 = ck(rt.cudaEventCreate()), ck(rt.cudaEventCreate())
H2D, D2H = rt.cudaMemcpyKind.cudaMemcpyHostToDevice, rt.cudaMemcpyKind.cudaMemcpyDeviceToHost
def run(i):
    host["state"][:] = ((S[i] - ns["observation_state_mean"]) / ns["observation_state_std"])[None]
    host["top"][:] = (TOP[i].astype(np.float32).transpose(2, 0, 1)[None] / 255.0 - ns["observation_images_top_mean"]) / ns["observation_images_top_std"]
    host["wrist"][:] = (WR[i].astype(np.float32).transpose(2, 0, 1)[None] / 255.0 - ns["observation_images_wrist_mean"]) / ns["observation_images_wrist_std"]
    for n in ("state", "top", "wrist"): ck(rt.cudaMemcpyAsync(dev[n], host[n].ctypes.data, host[n].nbytes, H2D, stream))
    ck(rt.cudaEventRecord(e0, stream)); ctx.execute_async_v3(stream); ck(rt.cudaEventRecord(e1, stream))
    ck(rt.cudaMemcpyAsync(host["actions"].ctypes.data, dev["actions"], host["actions"].nbytes, D2H, stream)); ck(rt.cudaStreamSynchronize(stream))
    return host["actions"][0].copy(), ck(rt.cudaEventElapsedTime(e0, e1))
for _ in range(20): run(0)  # 워밍업
t0 = time.time(); A = np.zeros((len(S), 100, 6), np.float32); L = np.zeros(len(S), np.float32)
for i in range(len(S)): A[i], L[i] = run(i)
np.savez(out_p, actions_norm=A, gpu_ms=L)
print(f"{eng_p.split('/')[-1]}: {len(S)} states {time.time()-t0:.0f}s, gpu median {np.median(L):.2f} ms")
