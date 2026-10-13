"""`D3` deployment report v2 (2026-10-13, external review): **code decides, the model explains.**

1. `verdict_table()` builds the decided verdicts from committed artifacts only:
   - G6 sensitivity (Newcombe), stress v2, the FP16 run, the simple checks and the positive control (if analyzed).
   - Each row carries candidate, metric, value, unit, comparison, verdict and evidence_path.
2. Nemotron 3 Super (Token Factory) writes prose that explains the table. It must not change a verdict or a number.
3. `check_report()` validates the prose against the table, row by row (structured):
   - a sentence that names a candidate may state only that candidate's verdict, its own success fraction or its
     reference's, and its own latency values;
   - any other number must exist somewhere in the table. Small integers are no longer skipped, except list markers and
     section numbers.
   Findings are printed in the report header; the report is never silently trusted.
Usage: python scripts/d3_report_v2.py [--out artifacts/reports] [--dry]   (--dry: table + validator self-test, no model call)"""
import argparse, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "src")
from edgeqgate.hashing import hash_obj

R = "artifacts/reports"
VERDICTS = ("GO", "NO-GO", "INSUFFICIENT_EVIDENCE", "FLAGGED")


def _ld(p):
    return json.load(open(p)) if os.path.exists(p) else None


def verdict_table():
    rows = []; S = _ld(f"{R}/g6_q2_sensitivity.json"); A = _ld(f"{R}/g6_analysis.json")
    for c, q in S["Q2"].items():
        rows.append({"candidate": c, "context": "G6 nominal, pads", "success": q["cell"], "reference": q["fp32"],
                     "e1_ci_pp": q["E1_ci_pp_newcombe99.75"], "e2": q["E2_decision_locked"], "verdict": q["verdict"],
                     "e2e_ms": round(json.load(open(f"{R}/g6_supplement.json"))["EX-1_EX-2"][c]["infer_ms_mean"], 1),
                     "evidence_path": f"{R}/g6_q2_sensitivity.json#Q2.{c}"})
    F = _ld(f"{R}/fp16_analysis.json")
    if F:
        p = F["primary_fp16_vs_fp32"]
        rows.append({"candidate": "VC-025", "context": "FP16 run, rubber bands", "success": p["test_k_n"], "reference": p["ref_k_n"],
                     "e1_ci_pp": [round(x, 1) for x in p["E1"]["ci_pp"]], "e2_px": round(p["E2"]["degradation_px"], 2),
                     "e2_ci_px": [round(x, 2) for x in p["E2"]["ci_px"]], "e2": p["E2"]["decision"], "verdict": p["verdict"],
                     "e2e_ms": round(F["latency"]["VC-025"]["infer_ms_mean"], 1), "evidence_path": f"{R}/fp16_analysis.json#primary_fp16_vs_fp32"})
    St = _ld(f"{R}/stress_v2_analysis.json")
    if St:
        for c, p in St["S4"]["secondary_vs_fp32"].items():
            rows.append({"candidate": c, "context": "stress S4 unseen can", "success": p["test_k_n"], "reference": p["ref_k_n"],
                         "e1_ci_pp": [round(x, 1) for x in p["E1"]["ci_pp"]], "e2": p["E2"]["decision"], "verdict": p["verdict"],
                         "evidence_path": f"{R}/stress_v2_analysis.json#S4.secondary_vs_fp32.{c}"})
    C = _ld(f"{R}/simple_checks_vs_audit.json")
    for c in ("PC-N", "PC-B"):
        t = C["cells"][c]
        rows.append({"candidate": c, "context": "offline, deliberately miscalibrated", "verdict": "FLAGGED",
                     "flags": {k: t[k] for k in ("input_check", "action_mse_flag", "score_mag_flag", "score_align_flag")},
                     "evidence_path": f"{R}/simple_checks_vs_audit.json#cells.{c}"})
    P = _ld(f"{R}/positive_control_analysis.json")
    if P:
        p = P["comparison"]
        rows.append({"candidate": "PC-B", "context": "positive control real arm", "success": p["test_k_n"], "reference": p["ref_k_n"],
                     "verdict": p["verdict"], "evidence_path": f"{R}/positive_control_analysis.json#comparison"})
    cost = {"VC-025": 11.6, "VC-002": 16.8, "VC-020": 16.8, "VC-005": 17.1, "VC-000": 53.4}
    for r in rows:
        if r["candidate"] in cost: r["gpu_ms_trtexec"] = cost[r["candidate"]]
    return {"rows": rows, "notes": {
        "recommendation_vs_approval": "FP16 (VC-025) is the recommended candidate to validate first (cheapest on the device). Approval is a separate status: on hold while every success comparison is INSUFFICIENT_EVIDENCE.",
        "gpu_ms_source": f"{R}/power_bench/SUMMARY.md (trtexec, 15 W)",
        "simple_checks_scope": "The action-MSE and audit-score thresholds were set on the same 24 normal cells, so '0 normal cells flagged' holds by construction; only the input check is independent of that set.",
        "ai_judge": "Cosmos-Reason2 single-frame end judge: 0 of 7 G6 failures detected (d4_retro_judge_g6.json)."}}


SYSTEM = """You explain a robotics deployment review. The verdicts and numbers are already decided by code.
RULES: 1) Never change or re-derive a verdict. Use exactly: GO, NO-GO, INSUFFICIENT_EVIDENCE, FLAGGED.
2) Use only numbers that appear in the table, attached to the candidate they belong to. 3) Name candidates by code (VC-025 etc.).
4) Keep recommendation (what to validate first) separate from approval. 5) Concise, factual, English, no marketing words."""
USER = """Decided verdict table:
```json
{table}
```
Write: ## 1. Recommendation ## 2. Approval status ## 3. Flagged candidates ## 4. What is still missing"""

CODE = re.compile(r"\b(VC-\d{3}|PC-[NB])\b"); FRAC = re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b")
VERD = re.compile(r"\b(INSUFFICIENT_EVIDENCE|INSUFFICIENT EVIDENCE|NO-GO|GO|FLAGGED)\b")
MS = re.compile(r"(\d+(?:\.\d+)?)\s*ms\b")


def check_report(text, table):
    by = {}
    for r in table["rows"]: by.setdefault(r["candidate"], []).append(r)
    allnums = set()
    def walk(o):
        if isinstance(o, dict): [walk(v) for v in o.values()]
        elif isinstance(o, list): [walk(v) for v in o]
        elif isinstance(o, (int, float)) and not isinstance(o, bool): allnums.add(round(float(o), 2))
    walk(table)
    issues = []
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
        codes = set(CODE.findall(sent)); s_clean = CODE.sub(" ", sent)
        if len(codes) == 1:
            c = codes.pop(); rows = by.get(c, [])
            ok_v = {r["verdict"] for r in rows}
            for v in VERD.findall(s_clean):
                v = v.replace(" ", "_")
                if v not in ok_v: issues.append(f"{c}: verdict '{v}' not in {sorted(ok_v)} — \"{sent.strip()[:90]}\"")
            okf = {tuple(r[k]) for r in rows for k in ("success", "reference") if r.get(k)}
            for a, b in FRAC.findall(s_clean):
                if (int(a), int(b)) not in okf: issues.append(f"{c}: fraction {a}/{b} is not this candidate's — \"{sent.strip()[:90]}\"")
            okm = {round(float(r[k]), 1) for r in rows for k in ("e2e_ms", "gpu_ms_trtexec") if r.get(k) is not None}
            for m in MS.findall(s_clean):
                if round(float(m), 1) not in okm: issues.append(f"{c}: {m} ms is not this candidate's latency — \"{sent.strip()[:90]}\"")
        for m in re.finditer(r"(?<![\w.\-§#])(\d+(?:\.\d+)?)(?![\w])", s_clean):
            v = float(m.group(1)); line_start = sent.lstrip()[:3]
            if re.match(r"^(#+\s*)?\d+\.", sent.lstrip()) and m.start() < sent.find(".") + 1: continue   # heading / list number
            if round(v, 2) not in allnums and round(v, 1) not in {round(x, 1) for x in allnums}:
                issues.append(f"number {m.group(1)} not in the table — \"{sent.strip()[:90]}\"")
    return sorted(set(issues))


def selftest(table):
    good = "VC-025 is INSUFFICIENT_EVIDENCE: it succeeded 19/20 against 10/10, with 24.7 ms end to end."
    bad = ["VC-025 succeeded 20/20.", "VC-025 is GO.", "VC-025 took 34.3 ms end to end.", "VC-002 is NO-GO."]
    res = {"good_issues": check_report(good, table), "bad_caught": {b: bool(check_report(b, table)) for b in bad}}
    assert not res["good_issues"] and all(res["bad_caught"].values()), res
    return res


def call(table, max_tokens=8192):
    import http.client
    body = json.dumps({"model": "nvidia/nemotron-3-super-120b-a12b", "max_tokens": max_tokens, "temperature": 0.2, "messages": [
        {"role": "system", "content": SYSTEM}, {"role": "user", "content": USER.format(table=json.dumps(table, indent=1))}]})
    conn = http.client.HTTPSConnection("api.studio.nebius.com", timeout=300); t0 = time.time()
    conn.request("POST", "/v1/chat/completions", body=body, headers={"Authorization": f"Bearer {os.environ['NEBIUS_API_KEY']}", "Content-Type": "application/json"})
    r = conn.getresponse(); raw = r.read(); conn.close()
    if r.status != 200: raise RuntimeError(f"HTTP {r.status}")
    d = json.loads(raw); return d["choices"][0]["message"]["content"] or "", time.time() - t0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=R); ap.add_argument("--dry", action="store_true"); a = ap.parse_args()
    T = verdict_table(); st = selftest(T); h = hash_obj(T)
    json.dump(T, open(f"{a.out}/d3_v2_verdicts.json", "w"), indent=1)
    print("rows", len(T["rows"]), "selftest", json.dumps(st))
    if a.dry: sys.exit(0)
    text, dt = call(T); issues = check_report(text, T)
    head = (f"# QuantGate — deployment report v2 (auto-generated)\n\n> Verdicts are decided by code (`d3_v2_verdicts.json`, hash `{h[:16]}`); "
            f"Nemotron 3 Super (Token Factory) wrote the explanation. A structured validator checked every candidate's verdict, success "
            f"fractions and latency in the prose. v1 is kept as history (`d3_final_report.md`).\n\n| Item | Value |\n|---|---|\n"
            f"| Latency | {dt:.1f} s |\n| **Validator findings** | **{len(issues)}** |\n\n"
            + ("".join(f"- {i}\n" for i in issues) + "\n" if issues else "") + "---\n\n")
    open(f"{a.out}/d3_report_v2.md", "w").write(head + text)
    json.dump({"verdict_hash": h, "issues": issues, "latency_sec": round(dt, 1), "selftest": st, "text": text}, open(f"{a.out}/d3_report_v2_run.json", "w"), indent=1)
    print("written", f"{a.out}/d3_report_v2.md", "issues", len(issues))
