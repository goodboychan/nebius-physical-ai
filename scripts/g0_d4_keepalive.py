"""`D4` 재측정 — 연결 재사용(keep-alive) 시의 지연.

앞선 측정(attempt-004)은 요청마다 새 TLS 연결을 맺어 핸드셰이크 비용을 매번 지불했다.
런타임 감독자는 같은 연결을 계속 쓰므로 그 측정은 실제 운영 조건과 다르다.
"""
import base64, http.client, json, os, struct, time, zlib

KEY = os.environ["NEBIUS_API_KEY"]
HOST = "api.studio.nebius.com"
BUDGET_MS = 500


def frame_png(w=640, h=480):
    rows = b""
    for y in range(h):
        rows += b"\x00" + bytes([((x * 7 + y * 13) % 256) for x in range(w) for _ in range(3)])
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode()


def main():
    img = frame_png()
    content = [
        {"type": "text", "text": "Robot inserting object into slot. Reply exactly one word: CONTINUE, ABORT, or FALLBACK."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
    ]
    out = {"budget_ms": BUDGET_MS, "mode": "keep-alive"}

    for model in ["openbmb/MiniCPM-V-4_5", "google/gemma-3-27b-it"]:
        conn = http.client.HTTPSConnection(HOST, timeout=90)
        body = json.dumps({"model": model, "max_tokens": 8,
                           "messages": [{"role": "user", "content": content}]})
        headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                   "Connection": "keep-alive"}
        lat, errs = [], 0
        t_open = time.time()
        conn.connect()
        connect_ms = (time.time() - t_open) * 1000
        for i in range(6):
            t0 = time.time()
            try:
                conn.request("POST", "/v1/chat/completions", body=body, headers=headers)
                r = conn.getresponse()
                r.read()
                dt = (time.time() - t0) * 1000
                (lat.append(dt) if r.status == 200 else errs.__add__(1))
                if r.status != 200:
                    errs += 1
            except Exception:
                errs += 1
                conn.close(); conn.connect()
        conn.close()
        if lat:
            lat.sort()
            med = lat[len(lat) // 2]
            print(f"{model}\n   연결 수립 {connect_ms:.0f}ms | 이후 요청 중앙값 {med:.0f}ms "
                  f"(최소 {lat[0]:.0f} 최대 {lat[-1]:.0f}, n={len(lat)}, 실패 {errs})")
            print(f"   -> 2Hz 예산 {BUDGET_MS}ms 대비: {'예산 내' if med <= BUDGET_MS else f'{med/BUDGET_MS:.1f}배 초과'}")
            out[model] = {"connect_ms": round(connect_ms), "median_ms": round(med),
                          "min_ms": round(lat[0]), "max_ms": round(lat[-1]),
                          "n": len(lat), "errors": errs,
                          "within_budget": med <= BUDGET_MS}
        else:
            print(f"{model}\n   전부 실패 ({errs}건)")
            out[model] = {"errors": errs, "within_budget": False}

    with open("artifacts/g0/d4_keepalive.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("\n저장: artifacts/g0/d4_keepalive.json")


if __name__ == "__main__":
    main()
