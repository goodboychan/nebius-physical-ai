"""`D3` 배포 리포트 에이전트 (§6).

감사 아티팩트를 읽고 셀별 go/no-go 근거를 서술한다.
모델: Nemotron 3 Super @ Nebius Token Factory.

**이 레이어는 §7의 가설 검정 대상이 아니다** (§6). 제품 구성요소이며 과학적 claim이 아니다.

설계 제약 — 이전 시도에서 얻은 것들:
  - Nemotron Super는 추론 모델이다. max_tokens를 넉넉히 주지 않으면 thinking에 다 쓰고
    빈 문자열을 반환한다 (attempt-004)
  - Token Factory는 TCP RTT 315ms로 멀다. 연결을 재사용한다 (attempt-008)

무결성 장치:
  - 증거 번들을 해시해서 리포트 헤더에 박는다. 리포트가 어떤 입력에서 나왔는지 추적 가능
  - **날조 검증**: 리포트에 등장하는 수치가 증거에 실재하는지 대조하고, 없는 수치는 경고한다.
    LLM이 쓴 리포트를 그대로 믿지 않는다
"""
import argparse, http.client, json, os, re, sys, time
from datetime import datetime, timezone

sys.path.insert(0, "/src" if os.path.isdir("/src") else "src")
from edgeqgate.hashing import hash_obj

HOST = "api.studio.nebius.com"
MODEL = "nvidia/nemotron-3-super-120b-a12b"


def log(m):
    print(f"[d3] {m}", flush=True)


def collect_evidence(art="artifacts/g0"):
    """아티팩트에서 증거를 모은다. 추정·보간 없이 있는 것만 담는다."""
    ev = {"collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    gm = f"{art}/grid/grid_manifest.json"
    if os.path.exists(gm):
        m = json.load(open(gm))
        cells = {}
        for c, r in m["results"].items():
            cells[c] = {k: r.get(k) for k in
                        ("precision", "calib_size", "calib_composition", "granularity",
                         "ok", "build_sec", "engine_bytes", "error")}
            if r.get("scales"):
                cells[c]["per_axis_scales"] = r["scales"]["per_axis_scales"]
                cells[c]["scalar_scales"] = r["scales"]["scalar_scales"]
        ev["grid_build"] = {
            "env": m["env"], "checkpoint_sha256": m["checkpoint_sha256"],
            "n_engines_built": m["n_engines_built"], "g3_pass": m["g3_pass"],
            "cells": cells,
        }

    ol = f"{art}/orin_latency.json"
    if os.path.exists(ol):
        ev["deployment_target_latency"] = json.load(open(ol))

    ca = f"{art}/calib_axis_probe.json"
    if os.path.exists(ca):
        ev["calibration_axis_analysis"] = json.load(open(ca))

    return ev


SYSTEM = """You are a deployment report writer for a pre-registered robotics experiment.

HARD RULES:
1. Use ONLY numbers that appear in the provided evidence JSON. Never estimate, interpolate, or invent.
2. If the evidence does not support a claim, write that the evidence is absent. Do not speculate.
3. Do not claim closed-loop task performance. No real-robot trials have been run.
4. Be concise and factual. No marketing language. Do not use words like "robust" or "excellent".
5. Write in Korean.

You produce a deployment readiness report with per-cell go/no-go rationale."""

USER_TMPL = """다음은 엣지 양자화 정책 배포 게이트 실험의 감사 아티팩트다.

```json
{evidence}
```

아래 형식으로 리포트를 작성하라.

## 1. 빌드 상태 요약
몇 개 셀이 빌드되었는지, 실패가 있는지. G3 통과 기준(최소 20셀)과 대조.

## 2. 배포 대상 지연
실제 Jetson Orin에서 측정된 정밀도별 지연. 특이사항이 있으면 지적하라.

## 3. 셀별 go / no-go
현재 증거만으로 판단 가능한 범위에서 판정하라. 판정 불가면 "판정 불가"와 그 이유를 쓰라.
INT8 셀 24개를 전부 나열하지 말고, **구분되는 그룹**으로 묶어 서술하라.

## 4. 이 리포트가 답할 수 없는 것
증거가 없어서 판단할 수 없는 항목을 명시하라.

중요: 클로즈드루프 성공률에 대한 주장은 절대 하지 마라. 실기 시행이 아직 없다."""


def call_model(evidence, max_tokens=4096, timeout=300):
    key = os.environ["NEBIUS_API_KEY"]
    body = json.dumps({
        "model": MODEL, "max_tokens": max_tokens, "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER_TMPL.format(
                evidence=json.dumps(evidence, ensure_ascii=False, indent=1))},
        ],
    })
    conn = http.client.HTTPSConnection(HOST, timeout=timeout)
    t0 = time.time()
    conn.request("POST", "/v1/chat/completions", body=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "Connection": "keep-alive"})
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    if r.status != 200:
        raise RuntimeError(f"HTTP {r.status}: {raw[:300].decode(errors='replace')}")
    d = json.loads(raw)
    return (d["choices"][0]["message"]["content"] or ""), d.get("usage", {}), time.time() - t0


# 천단위 쉼표를 포함해 매칭한다. 쉼표를 무시하면 157,811,276이 157/811/276 세 개로
# 쪼개져 존재하지 않는 수치로 오탐된다 (attempt-013에서 발견).
# 천단위 쉼표를 포함한 수와 평범한 수를 모두 매칭한다.
# 쉼표를 무시하면 157,811,276이 157/811/276 세 개로 쪼개져 오탐이 되고,
# [\d,]* 로 느슨하게 잡으면 뒤따르는 쉼표까지 먹는다. 둘 다 attempt-013에서 겪었다.
NUM = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def _to_float(tok: str) -> float:
    return float(tok.replace(",", ""))


def _normalize_separators(text: str) -> str:
    """천단위 구분자를 제거해 수치를 한 덩어리로 만든다.

    모델은 `139,971,220`(쉼표)와 `101 866 996`(공백)을 모두 쓴다. 정규화하지 않으면
    한 숫자가 세 조각으로 쪼개져 "증거에 없는 수치"로 오탐된다 (attempt-013에서 둘 다 겪음).
    """
    # 모델이 쓰는 구분자: 쉼표, 보통 공백, NBSP(U+00A0), NNBSP(U+202F), 얇은 공백(U+2009),
    # 숫자 공백(U+2007). 실제로 U+202F를 쓰는 것을 확인했다.
    seps = ",\u0020\u00a0\u202f\u2009\u2007"
    return re.sub(rf"(?<=\d)[{seps}](?=\d{{3}}(?!\d))", "", text)


def verify_numbers(report, evidence, tol=0.005):
    """리포트의 수치가 증거에 실재하는지 대조한다.

    LLM이 쓴 문서를 그대로 신뢰하지 않기 위한 장치다. 완벽한 검증은 아니다 —
    반올림·단위 변환·합계는 증거에 그대로 없을 수 있으므로 **경고**이지 오류가 아니다.
    """
    flat = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            flat.add(float(o))
        elif isinstance(o, str):
            for m in NUM.findall(o):
                flat.add(_to_float(m))

    walk(evidence)
    # 파생값도 허용: 바이트 -> MB, 초 -> 분
    derived = {round(v / 1e6, 1) for v in flat} | {round(v / 1e6) for v in flat} \
              | {round(v / 60, 1) for v in flat} | {round(v, 1) for v in flat} | {round(v) for v in flat}
    known = flat | derived

    unmatched = []
    norm = _normalize_separators(report)
    # 식별자에 붙은 숫자(p90_ms, VC-001, INT8 등)는 값이 아니라 이름이다. 제외한다.
    for m in NUM.finditer(norm):
        tok = m.group()
        # 식별자(p90_ms), 코드(VC-001), 섹션 참조(§4.1) 앞자리는 값이 아니다.
        if m.start() > 0 and (norm[m.start() - 1].isalpha()
                              or norm[m.start() - 1] in "-§"):
            continue
        v = _to_float(tok)
        if v <= 26 and v == int(v):
            continue        # 셀 번호·섹션 번호·작은 정수는 대조 대상에서 뺀다
        if not any(abs(v - k) <= max(tol * max(abs(k), 1), 1e-9) for k in known):
            unmatched.append(tok)
    return sorted(unmatched, key=_to_float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts/g0")
    ap.add_argument("--out", default="artifacts/reports")
    ap.add_argument("--max-tokens", type=int, default=4096)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    ev = collect_evidence(a.artifacts)
    ev_hash = hash_obj(ev)
    n_cells = len(ev.get("grid_build", {}).get("cells", {}))
    log(f"증거 수집: {n_cells}셀, 섹션 {sorted(k for k in ev if k != 'collected_at')}")
    log(f"evidence_hash = {ev_hash[:16]}")

    text, usage, dt = call_model(ev, a.max_tokens)
    log(f"생성 완료 {dt:.1f}s, completion {usage.get('completion_tokens')}토큰, "
        f"prompt {usage.get('prompt_tokens')}토큰")
    if not text.strip():
        log("경고: 빈 응답. 추론 모델이 thinking에 토큰을 다 썼을 수 있다 — max_tokens를 늘려라")
        return 1

    unmatched = verify_numbers(text, ev)
    log(f"날조 검증: 증거에 없는 수치 {len(unmatched)}개" + (f" -> {unmatched[:12]}" if unmatched else ""))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = f"{a.out}/deployment_report_{stamp}.md"
    header = f"""# 배포 리포트 (자동 생성)

> **이 문서는 `D3` 에이전트가 생성했다.** §6에 따라 제품 구성요소이며 과학적 claim이 아니다.
> 사람이 검토하기 전까지 근거로 인용하지 말 것.

| 항목 | 값 |
|---|---|
| 모델 | `{MODEL}` |
| 생성 시각 | {datetime.now(timezone.utc).isoformat(timespec='seconds')} |
| 증거 해시 | `{ev_hash}` |
| 증거 셀 수 | {n_cells} |
| 생성 토큰 | {usage.get('completion_tokens')} |
| 지연 | {dt:.1f}s |
| **증거에 없는 수치** | **{len(unmatched)}개**{(' — ' + ', '.join(unmatched[:10])) if unmatched else ''} |

---

"""
    open(path, "w", encoding="utf-8").write(header + text)
    json.dump({"evidence_hash": ev_hash, "model": MODEL, "usage": usage,
               "latency_sec": round(dt, 1), "unmatched_numbers": unmatched,
               "report_path": path},
              open(f"{a.out}/last_run.json", "w"), indent=2, ensure_ascii=False)
    log(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
