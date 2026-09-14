"""`D4` 운영 시 토큰 소비 실측 — Token Factory 크레딧 소진 추정용.

§7.1이 실기 225 trial, §2.1이 trial당 최대 60초, §6이 `D4`를 2Hz로 규정한다.
프레임 1장당 실제 prompt_tokens를 재서 전체 소비를 추정한다.
"""
import base64, json, os, struct, time, urllib.request, zlib

KEY = os.environ["NEBIUS_API_KEY"]
BASE = "https://api.studio.nebius.com/v1"


def frame_png(w, h):
    rows = b""
    for y in range(h):
        rows += b"\x00" + bytes([((x * 7 + y * 13) % 256) for x in range(w) for _ in range(3)])
    def ch(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + ch(b"IDAT", zlib.compress(rows, 6)) + ch(b"IEND", b""))
    return base64.b64encode(png).decode()


def call(model, w, h):
    img = frame_png(w, h)
    content = [{"type": "text", "text": "Reply one word: CONTINUE, ABORT, or FALLBACK."},
               {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}]
    body = json.dumps({"model": model, "max_tokens": 8,
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read()).get("usage", {})


M = "openbmb/MiniCPM-V-4_5"
print(f"모델: {M}\n")
rows = []
for w, h in [(640, 480), (320, 240), (160, 120)]:
    u = call(M, w, h)
    pt, ct = u.get("prompt_tokens"), u.get("completion_tokens")
    rows.append((f"{w}x{h}", pt, ct))
    print(f"  {w}x{h:<4} prompt={pt:>6}  completion={ct}")

print("\n=== D4 전체 소비 추정 (§7.1 225 trial x 60초 x 2Hz) ===")
n_req = 225 * 60 * 2
print(f"  총 요청 수: {n_req:,}")
for label, pt, ct in rows:
    tot = n_req * ((pt or 0) + (ct or 0))
    print(f"  {label:<9} 총 토큰 {tot/1e6:8.1f} M")
print("\n참고: 리허설·재시행을 감안하면 위의 1.5~2배로 봐야 한다.")
