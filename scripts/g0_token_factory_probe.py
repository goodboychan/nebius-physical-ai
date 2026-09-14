"""`G0` — Token Factory 호출 검증 및 §6 모델 전제 확인.

확인 대상:
  1) `D3`(배포 리포트 에이전트)용 Nemotron 3 Super 텍스트 호출이 되는가
  2) `D4`(런타임 감독자)는 오버헤드 프레임을 봐야 한다. 사전등록이 지정한
     "Nemotron 3 Nano Omni"가 Token Factory 목록에 없으므로, 대체 후보들의
     **비전 입력 지원 여부를 실제 호출로 확인**한다.
"""
import base64, io, json, os, sys, time, urllib.request

BASE = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1")
KEY = os.environ["NEBIUS_API_KEY"]


def tiny_png() -> str:
    """32x32 2색 합성 이미지. 민감 데이터 없음."""
    import zlib, struct
    w = h = 32
    rows = b""
    for y in range(h):
        rows += b"\x00" + bytes([(255 if (x // 8 + y // 8) % 2 else 0) for x in range(w) for _ in range(3)])
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows))
           + chunk(b"IEND", b""))
    return base64.b64encode(png).decode()


def call(model, content, max_tokens=32, timeout=90):
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
        dt = time.time() - t0
        txt = d["choices"][0]["message"]["content"]
        usage = d.get("usage", {})
        return True, dt, (txt or "").strip()[:120], usage, None
    except urllib.error.HTTPError as e:
        return False, time.time() - t0, "", {}, f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}"
    except Exception as e:
        return False, time.time() - t0, "", {}, f"{type(e).__name__}: {e}"


def main():
    result = {"base_url": BASE}

    print("[1] D3 후보 — Nemotron 3 Super 텍스트 호출")
    m = "nvidia/nemotron-3-super-120b-a12b"
    ok, dt, txt, usage, err = call(m, "Reply with exactly: OK")
    print(f"    {m}\n    -> {'성공' if ok else '실패'} ({dt:.1f}s) {txt if ok else err}")
    print(f"       usage: {usage}")
    result["D3"] = {"model": m, "ok": ok, "sec": round(dt, 1), "usage": usage, "error": err}

    print("\n[2] D4 후보 — 비전 입력 지원 여부 (오버헤드 프레임 판독용)")
    img = tiny_png()
    vision_msg = [
        {"type": "text", "text": "Answer in one word: how many distinct colors?"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
    ]
    cands = ["nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "openbmb/MiniCPM-V-4_5", "google/gemma-3-27b-it"]
    result["D4_candidates"] = []
    for m in cands:
        ok, dt, txt, usage, err = call(m, vision_msg, max_tokens=16)
        print(f"    {m}\n    -> {'비전 지원' if ok else '비전 불가'} ({dt:.1f}s) {txt if ok else err[:150]}")
        result["D4_candidates"].append(
            {"model": m, "vision_ok": ok, "sec": round(dt, 1), "error": err})

    os.makedirs("artifacts/g0", exist_ok=True)
    with open("artifacts/g0/token_factory_probe.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("\n저장: artifacts/g0/token_factory_probe.json")


if __name__ == "__main__":
    sys.exit(main())
