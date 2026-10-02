import base64, io, json, time, statistics as st, numpy as np, requests
from PIL import Image
a = np.fromfile("/home/chanseok/workspace/neubius/artifacts/g0/real_images.dat", dtype=np.float32).reshape(1, 2, 3, 480, 640)
img = (a[0, 0].transpose(1, 2, 0) * 255).clip(0, 255).astype(np.uint8)   # 실제 SO-101 프레임 (up 카메라)
buf = io.BytesIO(); Image.fromarray(img).save(buf, "JPEG", quality=85)
uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
PROMPT = ("You supervise a robot arm doing a pick task. Based on this overhead frame, answer with exactly one word: "
          "CONTINUE if the task looks normal, FALLBACK if the arm looks stuck or off-target, ABORT if unsafe.")
s = requests.Session(); lat = []; outs = []; toks = []
for i in range(32):
    body = {"model": "cosmos-reason2-2b", "max_tokens": 8, "temperature": 0,
            "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": uri}},
                                                     {"type": "text", "text": PROMPT}]}]}
    t = time.perf_counter(); r = s.post("http://127.0.0.1:8123/v1/chat/completions", json=body, timeout=30).json()
    dt = (time.perf_counter() - t) * 1000
    if i >= 2: lat.append(dt)                       # 첫 2회는 워밍업
    outs.append(r["choices"][0]["message"]["content"].strip()); toks.append(r["usage"]["prompt_tokens"])
lat.sort()
print(f"n={len(lat)}  median {st.median(lat):.0f} ms  p95 {lat[int(len(lat)*0.95)-1]:.0f} ms  max {lat[-1]:.0f} ms")
print(f"under 500ms budget: {sum(x < 500 for x in lat)}/{len(lat)}   prompt_tokens={toks[0]}")
print("answers:", sorted(set(outs)))
