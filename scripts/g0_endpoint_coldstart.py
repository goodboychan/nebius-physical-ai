"""`G0` — Nebius Serverless Endpoint 콜드스타트 및 웜 지연 측정 (`D6`).

§12: "Endpoint 콜드스타트가 길어 런타임 폴백 비현실적 -> `D6` 서사 붕괴".
완화책은 "웜 상태 유지 또는 폴백을 권고로 격하"인데, 어느 쪽인지 정하려면 두 수치가 필요하다.

  1) 프로비저닝: create -> 최초 응답까지. 엔드포인트를 미리 띄워두면 런타임에는 안 겪는다
  2) 웜 왕복 지연: 이미 떠 있는 엔드포인트의 요청 지연. **실기 중 폴백이 실제로 겪는 값**

인증은 토큰으로 건다 (기본값 none은 인터넷에 열린다).
측정이 끝나면 엔드포인트를 삭제한다 — 과금이 계속되기 때문이다.
"""
import argparse, json, os, re, secrets, subprocess, sys, time
import urllib.request

NEBIUS = os.path.expanduser("~/.nebius/bin/nebius")


def run(args, timeout=180):
    return subprocess.run([NEBIUS] + args, capture_output=True, text=True, timeout=timeout)


def get_status(ep_id):
    p = run(["ai", "endpoint", "get", ep_id, "--format", "json"], timeout=60)
    try:
        return json.loads(p.stdout).get("status", {})
    except Exception:
        return {}


def probe(url, token, timeout=20):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(256)
        return time.time() - t0, None
    except Exception as e:
        code = getattr(e, "code", None)
        return time.time() - t0, f"{type(e).__name__}{'/' + str(code) if code else ''}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-id", required=True)
    ap.add_argument("--platform", default="cpu-d3")
    ap.add_argument("--preset", default="2vcpu-8gb")
    ap.add_argument("--max-wait", type=int, default=1200)
    ap.add_argument("--warm-probes", type=int, default=10)
    ap.add_argument("--keep", action="store_true", help="측정 후 삭제하지 않음")
    a = ap.parse_args()

    token = secrets.token_urlsafe(24)
    name = f"g0-coldstart-{int(time.time())}"
    result = {"platform": a.platform, "preset": a.preset}
    ep_id = None
    try:
        print(f"[ep] 생성: {name} ({a.platform}/{a.preset}, auth=token)", flush=True)
        t_create = time.time()
        p = run(["ai", "endpoint", "create", "--parent-id", a.parent_id,
                 "--name", name, "--image", "python:3.12-slim",
                 "--platform", a.platform, "--preset", a.preset,
                 "--container-port", "8080",
                 "--container-command",
                 "python -m http.server 8080 --bind 0.0.0.0",
                 "--auth", "token", "--token", token, "--async"])
        m = re.search(r"aiendpoint-[a-z0-9]+|endpoint-[a-z0-9]+", p.stdout + p.stderr)
        if not m:
            print("[ep] 생성 실패:", (p.stderr or p.stdout)[:400])
            return 1
        ep_id = m.group(0)
        print(f"[ep] id={ep_id}  (create 호출 {time.time()-t_create:.1f}s)", flush=True)

        url, ready_at = None, None
        while time.time() - t_create < a.max_wait:
            st = get_status(ep_id)
            state = st.get("state", "?")
            eps = st.get("public_endpoints") or []
            if eps and not url:
                url = eps[0] if isinstance(eps[0], str) else eps[0].get("url")
                print(f"[ep] URL 확보 (+{time.time()-t_create:.0f}s): {url}", flush=True)
            if url:
                dt, err = probe(url, token)
                if err is None:
                    ready_at = time.time() - t_create
                    print(f"[ep] 최초 응답 성공 (+{ready_at:.0f}s, 요청 {dt*1000:.0f}ms)", flush=True)
                    break
                print(f"[ep] +{time.time()-t_create:5.0f}s state={state} probe={err}", flush=True)
            else:
                print(f"[ep] +{time.time()-t_create:5.0f}s state={state} (URL 대기)", flush=True)
            time.sleep(10)

        result["provision_to_first_response_sec"] = round(ready_at, 1) if ready_at else None
        result["url_obtained"] = bool(url)

        if ready_at:
            lat = []
            for _ in range(a.warm_probes):
                dt, err = probe(url, token)
                if err is None:
                    lat.append(dt * 1000)
                time.sleep(1)
            if lat:
                lat.sort()
                result["warm_latency_ms"] = {
                    "n": len(lat), "median": round(lat[len(lat) // 2]),
                    "min": round(lat[0]), "max": round(lat[-1]),
                    "p90": round(lat[int(len(lat) * 0.9) - 1]),
                }
                print(f"[ep] 웜 지연 중앙값 {result['warm_latency_ms']['median']}ms "
                      f"(최소 {result['warm_latency_ms']['min']}, 최대 {result['warm_latency_ms']['max']})")
    finally:
        if ep_id and not a.keep:
            print(f"[ep] 삭제: {ep_id}", flush=True)
            d = run(["ai", "endpoint", "delete", ep_id], timeout=120)
            result["deleted"] = d.returncode == 0
            if d.returncode != 0:
                print("[ep] 삭제 실패 — 수동 확인 필요:", (d.stderr or d.stdout)[:200])

    os.makedirs("artifacts/g0", exist_ok=True)
    with open("artifacts/g0/endpoint_coldstart.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("\n[ep] 결과:", json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
