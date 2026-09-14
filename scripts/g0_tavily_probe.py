"""`G0` — Tavily 호출 검증 (`D5` errata 수집기 경로).

§12가 지목한 재현성 문제도 함께 본다: 같은 질의를 반복하면 결과가 같은가.
`score_folklore`(제안 중) 채택 시 이 값이 동결 설계를 좌우한다.
"""
import hashlib, json, os, sys, time, urllib.request

KEY = os.environ["TAVILY_API_KEY"]
Q = "TensorRT INT8 quantization known issues Jetson Orin transformer attention"


def search(query, n=5, timeout=60):
    body = json.dumps({"query": query, "max_results": n, "search_depth": "basic"}).encode()
    req = urllib.request.Request("https://api.tavily.com/search", data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return time.time() - t0, json.loads(r.read())


def main():
    out = {"query": Q}
    try:
        dt, d = search(Q)
    except Exception as e:
        detail = e.read()[:200].decode(errors="replace") if hasattr(e, "read") else str(e)
        print(f"Tavily 호출 실패: {detail}")
        return 1
    res = d.get("results", [])
    print(f"Tavily 호출 성공 ({dt:.1f}s) — 결과 {len(res)}건")
    for r in res[:5]:
        print(f"   [{r.get('score', 0):.2f}] {r.get('title', '')[:70]}")
        print(f"          {r.get('url', '')[:90]}")
    out["call1"] = {"sec": round(dt, 1), "n": len(res),
                    "urls": [r.get("url") for r in res]}

    # 재현성: 같은 질의 2회차
    dt2, d2 = search(Q)
    u1 = [r.get("url") for r in res]
    u2 = [r.get("url") for r in d2.get("results", [])]
    same_set = set(u1) == set(u2)
    same_order = u1 == u2
    print(f"\n재현성 점검 (동일 질의 2회):")
    print(f"   URL 집합 동일: {same_set}   순서까지 동일: {same_order}")
    if not same_set:
        print(f"   1회차에만: {sorted(set(u1) - set(u2))}")
        print(f"   2회차에만: {sorted(set(u2) - set(u1))}")
    out["reproducibility"] = {"same_set": same_set, "same_order": same_order,
                              "call2_sec": round(dt2, 1)}
    out["content_hash_call1"] = hashlib.sha256(json.dumps(u1).encode()).hexdigest()
    out["content_hash_call2"] = hashlib.sha256(json.dumps(u2).encode()).hexdigest()

    os.makedirs("artifacts/g0", exist_ok=True)
    with open("artifacts/g0/tavily_probe.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("\n저장: artifacts/g0/tavily_probe.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
