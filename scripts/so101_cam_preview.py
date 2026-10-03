"""오버헤드 카메라 실시간 미리보기 (MJPEG over HTTP). 구도 맞출 때만 쓰고, 녹화 전에는 꼭 끈다."""
import cv2, http.server, socketserver, threading, time
DEV, PORT = "/dev/so101_cam_top", 8090
cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")); cap.set(3, 640); cap.set(4, 480); cap.set(5, 30)
latest = [None]; lock = threading.Lock()
def reader():
    while True:
        ok, f = cap.read()
        if not ok: time.sleep(0.05); continue
        # 화면 중앙 십자선과 3x3 격자: 팔로워·캔 위치를 맞추는 기준
        h, w = f.shape[:2]
        for i in (1, 2):
            cv2.line(f, (w * i // 3, 0), (w * i // 3, h), (80, 80, 80), 1)
            cv2.line(f, (0, h * i // 3), (w, h * i // 3), (80, 80, 80), 1)
        ok, j = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with lock: latest[0] = j.tobytes()
threading.Thread(target=reader, daemon=True).start()
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path != "/stream":
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write("<html><body style='margin:0;background:#111'><img src='/stream' style='width:100%;max-width:1280px'></body></html>".encode()); return
        self.send_response(200); self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=f"); self.end_headers()
        try:
            while True:
                with lock: j = latest[0]
                if j:
                    self.wfile.write(b"--f\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(j)).encode() + b"\r\n\r\n" + j + b"\r\n")
                time.sleep(1 / 15)
        except (BrokenPipeError, ConnectionResetError): pass
class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
S(("0.0.0.0", PORT), H).serve_forever()
