"""Orin TensorRT ACT 추론 서버 (시스템 python3.10: tensorrt 10.3 + cuda-python). 로봇·카메라는 lerobot-env(py3.12)의
so101_trial.py가 다루고, 둘은 유닉스 소켓으로 통신한다(Jetson용 tensorrt 파이썬 바인딩은 3.10에만 있다).

요청: 헤더(JSON 한 줄) + state f32[6] + top u8[480,640,3] + wrist u8[200,320,3]
응답: JSON 한 줄 {"actions": [[6]...100], "infer_ms": ...}  — 역정규화된 action(도, 집게 0–100)
정규화는 체크포인트의 전처리기 통계(norm_stats.npz)로 학습과 같게 한다. 엔진 입력 순서: state, top, wrist.
사용: python3 trt_policy_server.py <engine> <norm_stats.npz> [소켓 경로]"""
import json, os, socket, struct, sys, time
import numpy as np, tensorrt as trt
from cuda.bindings import runtime as rt

eng_path, stats_path = sys.argv[1:3]; SOCK = sys.argv[3] if len(sys.argv) > 3 else "/tmp/so101_policy.sock"
ns = np.load(stats_path)
def ck(r):
    err = r[0] if isinstance(r, tuple) else r
    if int(err) != 0: raise RuntimeError(f"CUDA error {err}")
    return r[1] if isinstance(r, tuple) and len(r) > 1 else None
log = trt.Logger(trt.Logger.WARNING)
eng = trt.Runtime(log).deserialize_cuda_engine(open(eng_path, "rb").read()); ctx = eng.create_execution_context()
names = [eng.get_tensor_name(i) for i in range(eng.num_io_tensors)]
bufs, host = {}, {}
for n in names:
    shp = tuple(eng.get_tensor_shape(n)); dt = trt.nptype(eng.get_tensor_dtype(n))
    host[n] = np.zeros(shp, dt); bufs[n] = ck(rt.cudaMalloc(host[n].nbytes)); ctx.set_tensor_address(n, bufs[n])
stream = ck(rt.cudaStreamCreate())
print("engine", os.path.basename(eng_path), {n: host[n].shape for n in names}, flush=True)

def infer(state, top, wrist):
    host["state"][:] = ((state - ns["observation_state_mean"]) / ns["observation_state_std"])[None]
    for k, img in (("top", top), ("wrist", wrist)):
        x = img.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        host[k][:] = (x - ns[f"observation_images_{k}_mean"]) / ns[f"observation_images_{k}_std"]
    t0 = time.perf_counter()
    for n in ("state", "top", "wrist"):
        ck(rt.cudaMemcpyAsync(bufs[n], host[n].ctypes.data, host[n].nbytes, rt.cudaMemcpyKind.cudaMemcpyHostToDevice, stream))
    ctx.execute_async_v3(stream)
    ck(rt.cudaMemcpyAsync(host["actions"].ctypes.data, bufs["actions"], host["actions"].nbytes, rt.cudaMemcpyKind.cudaMemcpyDeviceToHost, stream))
    ck(rt.cudaStreamSynchronize(stream))
    ms = (time.perf_counter() - t0) * 1000
    a = host["actions"][0] * ns["post_action_std"] + ns["post_action_mean"]
    return a, ms

def recv_exact(c, n):
    b = bytearray()
    while len(b) < n:
        p = c.recv(n - len(b))
        if not p: raise ConnectionError("closed")
        b += p
    return bytes(b)

if os.path.exists(SOCK): os.unlink(SOCK)
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(SOCK); srv.listen(1)
# 시작 시 한 번 돌려 워밍업한다
infer(np.zeros(6, np.float32), np.zeros((480, 640, 3), np.uint8), np.zeros((200, 320, 3), np.uint8))
print("ready", SOCK, flush=True)
while True:
    c, _ = srv.accept()
    try:
        while True:
            n = struct.unpack("<I", recv_exact(c, 4))[0]
            st = np.frombuffer(recv_exact(c, 24), np.float32)
            top = np.frombuffer(recv_exact(c, 480 * 640 * 3), np.uint8).reshape(480, 640, 3)
            wr = np.frombuffer(recv_exact(c, 200 * 320 * 3), np.uint8).reshape(200, 320, 3)
            a, ms = infer(st, top, wr)
            out = json.dumps({"seq": n, "actions": a.round(4).tolist(), "infer_ms": round(ms, 2)}).encode() + b"\n"
            c.sendall(out)
    except ConnectionError:
        pass
    finally:
        c.close()
