"""`D5` Errata 수집기 (§6) — TRT·Orin·컴파일러 known issue를 검색해 리포트에 첨부.

질의를 **실제 빌드 환경에서 유도**한다. 손으로 쓴 고정 질의가 아니라, 우리가 실제로
쓰는 TRT 버전·디바이스·연산 종류에서 만든다. 환경이 바뀌면 질의도 바뀐다.

결과는 `edgeqgate.retrieval`로 동결한다. 검색은 시간에 따라 변하므로, 리포트의 근거를
나중에 재현하려면 스냅샷이 해시로 고정되어야 한다 (§12의 재현성 요구).
"""
import argparse, json, os, sys, urllib.request
from pathlib import Path

sys.path.insert(0, "src")
from edgeqgate.retrieval import (SnapshotMissing, drift, freeze, load_snapshot,
                                 write_snapshot)

SNAP = Path("artifacts/retrieval")


def log(m):
    print(f"[d5] {m}", flush=True)


def build_queries(env: dict) -> list[str]:
    """환경 메타데이터에서 질의를 유도한다."""
    trt = env.get("tensorrt", "")
    dev = env.get("device", "Jetson Orin")
    return [
        f"TensorRT {trt} known issues release notes",
        f"TensorRT INT8 explicit quantization Q/DQ transformer attention fusion issue",
        f"{dev} TensorRT INT8 performance regression",
        f"TensorRT ModelOpt quantized ONNX build failure Jetson",
        f"TensorRT {trt} JetPack compatibility engine version",
    ]


def tavily_search(query: str, n: int = 5) -> list[dict]:
    key = os.environ["TAVILY_API_KEY"]
    body = json.dumps({"query": query, "max_results": n,
                       "search_depth": "advanced"}).encode()
    req = urllib.request.Request("https://api.tavily.com/search", data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read())
    return [{"url": x.get("url", ""), "title": x.get("title", ""),
             "content": (x.get("content", "") or "")[:1200],
             "score": x.get("score")} for x in d.get("results", [])]


def render_markdown(snap, env) -> str:
    lines = [
        "## Errata (`D5` 자동 수집)",
        "",
        f"> 수집 시각 {snap.frozen_at} · provider `{snap.provider}` · "
        f"스냅샷 해시 `{snap.snapshot_hash}`",
        ">",
        "> **검색 결과는 시간에 따라 변한다.** 이 절의 근거는 위 해시로 동결된 스냅샷이며,",
        "> `artifacts/retrieval/`의 동결본으로 재현할 수 있다. 사람이 검토하기 전까지",
        "> 여기 링크된 내용을 사실로 인용하지 말 것.",
        "",
        f"대상 환경: TensorRT {env.get('tensorrt')} · {env.get('device')} · "
        f"CUDA {env.get('cuda')} · sm_{env.get('sm')}",
        "",
    ]
    for q in snap.queries:
        rs = snap.results.get(q, [])
        lines.append(f"### 질의: {q}")
        if not rs:
            lines.append("- 결과 없음")
        for r in rs:
            sc = f" (score {r['score']:.2f})" if r.get("score") is not None else ""
            lines.append(f"- [{r['title'][:90]}]({r['url']}){sc}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["freeze", "replay", "drift"], default="freeze")
    ap.add_argument("--name", default="errata")
    ap.add_argument("--against", help="drift 모드: 비교 대상 스냅샷 파일")
    ap.add_argument("--build-log", default="artifacts/manifests/g3_engine_build.jsonl",
                    help="G3 엔진 빌드 기록. 있으면 거기 적힌 실제 TensorRT 버전으로 질의를 만든다")
    a = ap.parse_args()

    if os.path.exists(a.build_log):
        rec = json.loads(open(a.build_log).readline())
        env = {"tensorrt": rec["env"]["tensorrt"], "device": "Jetson Orin Nano Super", "cuda": "12.6", "sm": "87"}
    else:
        lat = json.load(open("artifacts/g0/orin_latency.json"))
        env = {"tensorrt": lat["tensorrt"], "device": lat["device"],
               "cuda": lat["cuda"], "sm": "87"}
    queries = build_queries(env)
    path = SNAP / f"{a.name}.json"

    if a.mode == "replay":
        snap = load_snapshot(path)          # 없으면 예외. 조용히 새 검색하지 않는다
        log(f"동결본 replay: {snap.frozen_at}, 해시 {snap.snapshot_hash[:16]}")
    elif a.mode == "drift":
        old = load_snapshot(Path(a.against))
        new = freeze(queries, tavily_search, notes=["drift 비교용 재수집"])
        d = drift(old, new)
        print(json.dumps(d, indent=2, ensure_ascii=False))
        changed = sum(1 for v in d.values() if not v["same_set"])
        log(f"질의 {len(d)}개 중 결과 집합이 바뀐 것 {changed}개")
        Path("artifacts/retrieval/drift.json").write_text(
            json.dumps({"old": str(a.against), "old_frozen_at": old.frozen_at,
                        "new_frozen_at": new.frozen_at, "drift": d},
                       indent=2, ensure_ascii=False))
        return 0
    else:
        log(f"질의 {len(queries)}개 수집 중")
        snap = freeze(queries, tavily_search,
                      notes=[f"대상 환경 TRT {env['tensorrt']} / {env['device']}"])
        h = write_snapshot(snap, path)
        log(f"동결: {path}  해시 {h[:16]}")

    md = render_markdown(snap, env)
    out = Path("artifacts/reports/errata.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    n = sum(len(v) for v in snap.results.values())
    log(f"결과 {n}건, 고유 URL {len(snap.all_urls())}개 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
