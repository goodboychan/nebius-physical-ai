"""`G0` — Nebius Jobs 더미 팬아웃으로 동시성·큐 지연 측정.

§12가 "Jobs 동시성/큐 지연이 예상보다 큼"을 `G4` 지연 리스크로 지목했다.
§5.3의 팬아웃(잡 5,200건)이 일정 안에 끝나는지가 여기서 갈린다.

측정 대상:
  - submit 지연 (API 왕복)
  - PROVISIONING -> RUNNING 큐 대기
  - 실제 동시 실행 수 (쿼터 compute.instance.count 한도와 비교)
"""
import argparse, json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

NEBIUS = os.path.expanduser("~/.nebius/bin/nebius")
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "ERROR", "DELETED"}
# 관측된 비종료 상태. "RUNNING"은 실제로 나타나지 않는다 (attempt-007 발견) —
# 잡은 PROVISIONING -> STARTING -> IMAGE_PULLING -> COMPLETED로 전이한다.
ACTIVE_STATES = {"STARTING", "IMAGE_PULLING", "RUNNING"}


def run(args, timeout=180):
    return subprocess.run([NEBIUS] + args, capture_output=True, text=True, timeout=timeout)


def submit(parent, idx, platform, preset, sleep_s):
    t0 = time.time()
    p = run(["ai", "job", "create", "--parent-id", parent,
             "--name", f"g0-fanout-{idx:02d}",
             "--image", "ubuntu:24.04",
             "--platform", platform, "--preset", preset,
             "--container-command", f"echo job-{idx}; sleep {sleep_s}",
             "--timeout", "15m", "--async"])
    dt = time.time() - t0
    m = re.search(r"aijob-[a-z0-9]+", p.stdout + p.stderr)
    return {"idx": idx, "submit_sec": round(dt, 2),
            "job_id": m.group(0) if m else None,
            "error": None if m else (p.stderr or p.stdout)[:200]}


def state_of(job_id):
    p = run(["ai", "job", "get", job_id, "--format", "json"], timeout=60)
    try:
        return json.loads(p.stdout).get("status", {}).get("state", "UNKNOWN")
    except Exception:
        return "UNKNOWN"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-id", required=True)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--platform", default="cpu-d3")
    ap.add_argument("--preset", default="2vcpu-8gb")
    ap.add_argument("--sleep", type=int, default=30)
    ap.add_argument("--submit-workers", type=int, default=10)
    ap.add_argument("--poll", type=int, default=15)
    ap.add_argument("--max-wait", type=int, default=1800)
    a = ap.parse_args()

    print(f"[fanout] {a.n}건 제출 시작 ({a.platform}/{a.preset}, sleep {a.sleep}s)", flush=True)
    t_start = time.time()
    with ThreadPoolExecutor(max_workers=a.submit_workers) as ex:
        subs = list(ex.map(lambda i: submit(a.parent_id, i, a.platform, a.preset, a.sleep),
                           range(a.n)))
    t_submitted = time.time()
    ok = [s for s in subs if s["job_id"]]
    lat = sorted(s["submit_sec"] for s in ok)
    print(f"[fanout] 제출 완료 {len(ok)}/{a.n}, 벽시계 {t_submitted-t_start:.1f}s")
    if lat:
        print(f"[fanout] submit 지연 중앙값 {lat[len(lat)//2]:.1f}s, 최소 {lat[0]:.1f}s, 최대 {lat[-1]:.1f}s")
    for s in subs:
        if s["error"]:
            print(f"[fanout] 제출 실패 idx={s['idx']}: {s['error'][:120]}")

    first_seen, done_at = {}, {}
    conc_samples = []
    ids = [s["job_id"] for s in ok]
    while time.time() - t_submitted < a.max_wait:
        with ThreadPoolExecutor(max_workers=10) as ex:
            states = dict(zip(ids, ex.map(state_of, ids)))
        now = time.time()
        running = sum(1 for v in states.values() if v in ACTIVE_STATES)
        conc_samples.append(running)
        for j, st in states.items():
            if st in ACTIVE_STATES and j not in first_seen:
                first_seen[j] = now - t_submitted
            if st in TERMINAL and j not in done_at:
                done_at[j] = now - t_submitted
        counts = {}
        for v in states.values():
            counts[v] = counts.get(v, 0) + 1
        print(f"[fanout] +{now-t_submitted:6.0f}s  {counts}  (동시실행 {running})", flush=True)
        if all(v in TERMINAL for v in states.values()):
            break
        time.sleep(a.poll)

    q = sorted(first_seen.values())
    d = sorted(done_at.values())
    result = {
        "n_requested": a.n, "n_submitted": len(ok),
        "platform": a.platform, "preset": a.preset, "sleep_s": a.sleep,
        "submit_wall_sec": round(t_submitted - t_start, 1),
        "submit_latency_sec": {"median": lat[len(lat)//2] if lat else None,
                               "min": lat[0] if lat else None, "max": lat[-1] if lat else None},
        "queue_to_running_sec": {"median": round(q[len(q)//2], 1) if q else None,
                                 "min": round(q[0], 1) if q else None,
                                 "max": round(q[-1], 1) if q else None, "n": len(q)},
        "to_terminal_sec": {"median": round(d[len(d)//2], 1) if d else None,
                            "max": round(d[-1], 1) if d else None, "n": len(d)},
        "max_observed_concurrency": max(conc_samples) if conc_samples else 0,
        "job_ids": ids,
    }
    os.makedirs("artifacts/g0", exist_ok=True)
    with open("artifacts/g0/jobs_fanout.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("\n[fanout] 결과:", json.dumps(
        {k: v for k, v in result.items() if k != "job_ids"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
