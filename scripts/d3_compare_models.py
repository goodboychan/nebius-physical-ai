"""`D3` 배포 리포트를 Token Factory의 여러 모델로 같은 증거에서 써 보고 비교한다 (해커톤 설문의 근거 수집).
§6상 D3는 제품 구성요소이며 과학적 claim이 아니다. 비교 지표는 기계적으로 잰다:
  - 날조 수치: 리포트의 숫자 중 증거에 없는 것 (d3_report_agent.verify_numbers)
  - 형식 준수: 지시한 4개 절 제목이 모두 있는가, 빈 응답인가
  - 금지 주장: 실기 성공률을 주장했는가(키워드 검사, 사람 검토용 플래그)
  - 지연, prompt/completion 토큰
증거: G3 빌드 기록, G4 감사 점수(동결본), Orin 지연, D5 errata 스냅샷.
사용: python scripts/d3_compare_models.py --evidence <json> [--models a,b,...] [--repeats N]"""
import argparse, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d3_report_agent as d3

SECTIONS = ["## 1.", "## 2.", "## 3.", "## 4."]
FORBIDDEN = re.compile(r"(성공률|success rate)[^\n]{0,40}\d+\s*%")

def run(model, evidence, max_tokens):
    d3.MODEL = model
    t0 = time.time()
    try:
        text, usage, dt = d3.call_model(evidence, max_tokens=max_tokens)
    except Exception as e:
        return {"model": model, "error": str(e)[:300], "latency_sec": round(time.time() - t0, 1)}
    um = d3.verify_numbers(text, evidence) if text.strip() else []
    nums = len(d3.NUM.findall(d3._normalize_separators(text)))
    return {"model": model, "latency_sec": round(dt, 1), "empty": not text.strip(), "chars": len(text),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
            "numbers_in_report": nums, "unmatched_numbers": um, "n_unmatched": len(um),
            "sections_present": sum(s in text for s in SECTIONS), "forbidden_claim_flag": bool(FORBIDDEN.search(text)),
            "text": text}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True); ap.add_argument("--out", default="artifacts/reports/d3_model_compare.json")
    ap.add_argument("--models", default="nvidia/nemotron-3-super-120b-a12b,nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B,"
                    "nvidia/Nemotron-3-Ultra-550b-a55b,nvidia/Nemotron-3_5-Lightning,openai/gpt-oss-120b,Qwen/Qwen3-235B-A22B-Instruct-2507")
    ap.add_argument("--repeats", type=int, default=2); ap.add_argument("--max-tokens", type=int, default=8192)
    a = ap.parse_args()
    ev = json.load(open(a.evidence)); res = []
    for model in a.models.split(","):
        for r in range(a.repeats):
            x = run(model, ev, a.max_tokens); x["repeat"] = r; res.append(x)
            print(f"{model:45s} r{r} {x.get('latency_sec')}s empty={x.get('empty')} unmatched={x.get('n_unmatched')}/"
                  f"{x.get('numbers_in_report')} sections={x.get('sections_present')} forbidden={x.get('forbidden_claim_flag')} "
                  f"tok={x.get('completion_tokens')} {x.get('error','')}", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({"evidence_hash": d3.hash_obj(ev), "results": res}, open(a.out, "w"), indent=1, ensure_ascii=False)
