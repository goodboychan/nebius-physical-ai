"""손목 카메라(OpenMV AE3) 실시간 미리보기 — 장착 각도 맞출 때만. 녹화 전에 반드시 끈다."""
import cv2, http.server, socketserver, threading, time
from lerobot.utils.import_utils import register_third_party_plugins
register_third_party_plugins()
from lerobot_camera_openmv import OpenMVCamera, OpenMVCameraConfig
cam = OpenMVCamera(OpenMVCameraConfig(fps=30)); cam.connect()
PORT = 8091
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path != "/stream":
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(b"<html><body style='margin:0;background:#111'><img src='/stream' style='width:100%;max-width:960px;image-rendering:pixelated'></body></html>"); return
        self.send_response(200); self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=f"); self.end_headers()
        try:
            while True:
                f = cv2.cvtColor(cam.read_latest(max_age_ms=1000), cv2.COLOR_RGB2BGR)
                f = cv2.resize(f, (640, 400), interpolation=cv2.INTER_NEAREST)
                h, w = f.shape[:2]
                cv2.line(f, (w // 2, 0), (w // 2, h), (80, 80, 80), 1); cv2.line(f, (0, h // 2), (w, h // 2), (80, 80, 80), 1)
                j = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
                self.wfile.write(b"--f\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(j)).encode() + b"\r\n\r\n" + j + b"\r\n")
                time.sleep(1 / 15)
        except (BrokenPipeError, ConnectionResetError): pass
class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
try:
    S(("0.0.0.0", PORT), H).serve_forever()
finally:
    cam.disconnect()
