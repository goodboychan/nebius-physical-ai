"""`D4` 런타임 감독자 — Token Factory 백엔드 (§6).

실제 2Hz 운용을 검증한다. 팔이 없으므로 프레임은 합성이지만, **모델 호출·연결 재사용·
판정 관리·`EX-3` 집계는 전부 실제 경로**다.

측정 근거 (attempt-008, attempt-013):
  - `openbmb/MiniCPM-V-4_5` keep-alive 중앙 381ms. 2Hz 예산 500ms 안
  - `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`는 이미지 입력 미지원 (§6 지정 모델이 없음)
  - 연결을 재사용하지 않으면 TLS 핸드셰이크로 650ms를 매번 더 쓴다
"""
import argparse, base64, http.client, json, os, struct, sys, time, zlib
from pathlib import Path

sys.path.insert(0, "src")
from edgeqgate.supervisor import Supervisor, SupervisorConfig

HOST = "api.studio.nebius.com"
MODEL = "openbmb/MiniCPM-V-4_5"
PROMPT = ("Overhead view of a robot arm inserting an object into a slot. "
          "Reply with exactly one word: CONTINUE, ABORT, or FALLBACK.")


def log(m):
    print(f"[d4] {m}", flush=True)


def synth_frame(i, w=640, h=480):
    """합성 오버헤드 프레임. 팔이 오면 실제 카메라 grab으로 교체한다."""
    rows = b""
    for y in range(h):
        rows += b"\x00" + bytes([((x * 7 + y * 13 + i * 31) % 256) for x in range(w) for _ in range(3)])
    def ch(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + ch(b"IDAT", zlib.compress(rows, 6)) + ch(b"IEND", b""))
    return base64.b64encode(png).decode()


class TokenFactoryVision:
    """연결을 유지하는 추론 클라이언트. 끊기면 한 번 재연결한다."""

    def __init__(self, model=MODEL, timeout=20):
        self.model, self.timeout = model, timeout
        self.key = os.environ["NEBIUS_API_KEY"]
        self.conn = None
        self.reconnects = 0

    def _connect(self):
        if self.conn:
            try: self.conn.close()
            except Exception: pass
        self.conn = http.client.HTTPSConnection(HOST, timeout=self.timeout)
        self.conn.connect()

    def __call__(self, frame_b64: str) -> str:
        body = json.dumps({"model": self.model, "max_tokens": 8, "temperature": 0.0,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{frame_b64}"}}]}]})
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                   "Connection": "keep-alive"}
        for attempt in (1, 2):
            try:
                if self.conn is None:
                    self._connect()
                self.conn.request("POST", "/v1/chat/completions", body=body, headers=headers)
                r = self.conn.getresponse()
                raw = r.read()
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}: {raw[:120].decode(errors='replace')}")
                return json.loads(raw)["choices"][0]["message"]["content"] or ""
            except Exception:
                self.conn = None
                self.reconnects += 1
                if attempt == 2:
                    raise
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--rate", type=float, default=2.0)
    ap.add_argument("--out", default="artifacts/g0/d4_runtime.json")
    a = ap.parse_args()

    infer = TokenFactoryVision()
    counter = {"i": 0}
    def grab():
        counter["i"] += 1
        return synth_frame(counter["i"])

    cfg = SupervisorConfig(rate_hz=a.rate)
    sup = Supervisor(infer=infer, grab_frame=grab, config=cfg)
    log(f"시작: {a.rate}Hz, {a.seconds}s, 모델 {MODEL}")
    log(f"설정: stale_after={cfg.stale_after_ms}ms, abort_on_stale={cfg.abort_on_stale}, "
        f"연속 abort 요건={cfg.consecutive_for_abort}")

    sup.start()
    t0 = time.time()
    control_reads = []
    # 제어 루프를 흉내낸다: 30Hz로 최신 판정을 읽는다 (판정을 기다리지 않는다)
    while time.time() - t0 < a.seconds:
        d, info = sup.current()
        control_reads.append({"t": round(time.time() - t0, 3), "decision": d,
                              "stale": info["stale"], "age_ms": info["age_ms"]})
        time.sleep(1 / 30)
    sup.stop()

    ex3 = sup.ex3_summary()
    achieved = ex3["n_verdicts"] / a.seconds
    n_stale = sum(1 for r in control_reads if r["stale"])
    out = {"model": MODEL, "target_rate_hz": a.rate, "achieved_rate_hz": round(achieved, 2),
           "duration_s": a.seconds, "reconnects": infer.reconnects,
           "control_loop_reads": len(control_reads),
           "stale_read_fraction": round(n_stale / max(len(control_reads), 1), 4),
           "ex3": ex3}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))

    log(f"판정 {ex3['n_verdicts']}회, 달성 {achieved:.2f}Hz (목표 {a.rate}Hz)")
    log(f"지연 중앙 {ex3['latency_ms']['median']:.0f}ms  p90 {ex3['latency_ms']['p90']:.0f}ms  "
        f"최대 {ex3['latency_ms']['max']:.0f}ms")
    log(f"판정 분포 {ex3['decisions']}  오류 {ex3['n_errors']}회  재연결 {infer.reconnects}회")
    log(f"제어 루프 {len(control_reads)}회 읽기 중 낡은 판정 {n_stale}회 "
        f"({100*n_stale/max(len(control_reads),1):.1f}%)")
    log(f"저장: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
