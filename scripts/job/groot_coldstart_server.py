"""GR00T 콜드스타트 대리 측정 서버 (`D6`, §12).

전체 Isaac-GR00T 스택 대신 **콜드스타트의 지배적 비용**을 잰다:
이미지 풀 -> 의존성 설치 -> 가중치 5.4GB 다운로드 -> GPU 로드 -> 응답 가능.

측정하지 않는 것: 모델 클래스 구성, 워밍업 커널, 실제 추론.
따라서 이 값은 실제 GR00T 콜드스타트의 **하한**이다.
"""
import http.server, json, os, socketserver, sys, threading, time

T0 = time.time()
STAGES = {}


def mark(name):
    STAGES[name] = round(time.time() - T0, 2)
    print(f"[groot] {name}: +{STAGES[name]}s", flush=True)


def load():
    mark("start")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir",
                    "huggingface_hub", "safetensors"], check=True)
    mark("deps_installed")

    from huggingface_hub import snapshot_download
    path = snapshot_download("nvidia/GR00T-N1.5-3B",
                             allow_patterns=["*.safetensors", "*.json"])
    mark("weights_downloaded")

    import torch
    from safetensors.torch import load_file
    import glob
    total = 0
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    for f in sorted(glob.glob(os.path.join(path, "*.safetensors"))):
        sd = load_file(f, device=dev)
        total += sum(v.numel() for v in sd.values())
        del sd
    mark("weights_on_gpu")
    STAGES["device"] = dev
    STAGES["n_params"] = total
    STAGES["gpu"] = torch.cuda.get_device_name(0) if dev == "cuda" else None
    print(f"[groot] 파라미터 {total/1e9:.2f}B, device={dev}", flush=True)


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"ready": "weights_on_gpu" in STAGES, "stages": STAGES,
                           "uptime_s": round(time.time() - T0, 2)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    # 서버를 먼저 띄운다. 그래야 "언제부터 응답 가능한지"와 "언제 준비되는지"를 분리해 잰다.
    srv = socketserver.TCPServer(("0.0.0.0", 8080), H)
    srv.allow_reuse_address = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    mark("http_serving")
    try:
        load()
    except Exception as e:
        STAGES["error"] = f"{type(e).__name__}: {e}"
        print(f"[groot] 실패: {e}", flush=True)
    while True:
        time.sleep(5)


if __name__ == "__main__":
    main()
