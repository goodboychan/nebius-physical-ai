"""`D4`의 2Hz 예산이 실현 가능한가 (§6).

`D4`는 오버헤드 프레임 + 텔레메트리를 **2Hz**로 보고 abort/폴백/계속을 판정한다.
2Hz = 요청당 500ms 예산. 실제 오버헤드 프레임 크기로 왕복 지연을 측정한다.
"""
import base64, json, os, struct, sys, time, urllib.request, zlib

BASE = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1")
KEY = os.environ["NEBIUS_API_KEY"]
BUDGET_MS = 500


def frame_png(w=640, h=480):
    """오버헤드 카메라 해상도의 합성 프레임."""
    rows = b""
    for y in range(h):
        rows += b"\x00" + bytes([((x * 7 + y * 13) % 256) for x in range(w) for _ in range(3)])
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode()


def call(model, content, max_tokens, timeout=120):
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
        return time.time() - t0, (d["choices"][0]["message"]["content"] or "").strip(), d.get("usage", {}), None
    except Exception as e:
        detail = e.read()[:160].decode(errors="replace") if hasattr(e, "read") else str(e)
        return time.time() - t0, "", {}, detail


def main():
    out = {"budget_ms": BUDGET_MS, "frame": "640x480 PNG"}
    img = frame_png()
    print(f"프레임 base64 크기: {len(img)/1024:.0f} KB\n")

    prompt = [
        {"type": "text", "text": "Robot inserting object into slot. Reply exactly one word: CONTINUE, ABORT, or FALLBACK."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
    ]
    print(f"[D4 후보] 실제 프레임 지연 (3회, 예산 {BUDGET_MS}ms)")
    out["D4"] = []
    for m in ["openbmb/MiniCPM-V-4_5", "google/gemma-3-27b-it"]:
        lat = []
        last = ""
        for _ in range(3):
            dt, txt, usage, err = call(m, prompt, 8)
            if err:
                print(f"  {m} -> 실패: {err[:120]}")
                lat = []
                break
            lat.append(dt * 1000)
            last = txt[:40]
        if lat:
            med = sorted(lat)[len(lat) // 2]
            verdict = "예산 내" if med <= BUDGET_MS else f"예산 초과 ({med/BUDGET_MS:.1f}배)"
            print(f"  {m}\n    중앙값 {med:.0f}ms  (전체 {[f'{x:.0f}' for x in lat]})  -> {verdict}   응답: {last!r}")
            out["D4"].append({"model": m, "median_ms": round(med), "all_ms": [round(x) for x in lat],
                              "within_budget": med <= BUDGET_MS})

    print("\n[D3] Nemotron Super — max_tokens를 늘려 실제 출력 확인 (추론 모델)")
    dt, txt, usage, err = call("nvidia/nemotron-3-super-120b-a12b",
                               "Reply with exactly: OK", 512)
    print(f"  {dt:.1f}s  usage={usage.get('completion_tokens')}토큰  출력={txt[:80]!r}  {err or ''}")
    out["D3"] = {"sec": round(dt, 1), "completion_tokens": usage.get("completion_tokens"),
                 "output_nonempty": bool(txt)}

    with open("artifacts/g0/d4_latency.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("\n저장: artifacts/g0/d4_latency.json")


if __name__ == "__main__":
    sys.exit(main())
