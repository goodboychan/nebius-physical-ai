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
VERDICTS = ("GO", "NO-GO", "INSUFFICIENT_EVIDENCE", "FLAGGED", "IMPROVEMENT_DETECTED", "NOT_DETECTED")


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
                     "flagged_by": [n for k, n in (("input_check", "simple input check"), ("action_mse_flag", "action error (MSE)"),
                                                   ("score_mag_flag", "audit score (magnitude)"), ("score_align_flag", "audit score (alignment)")) if t[k]],
                     "evidence_path": f"{R}/simple_checks_vs_audit.json#cells.{c}"})
    P = _ld(f"{R}/positive_control_analysis.json")
    if P:
        p = P["comparison"]
        rows.append({"candidate": "PC-B", "context": "positive control real arm", "success": p["test_k_n"], "reference": p["ref_k_n"],
                     "e1_ci_pp": [round(x, 1) for x in p["E1"]["ci_pp"]], "e2": p["E2"]["decision"], "verdict": p["verdict"],
                     "e2e_ms": P["e2e_ms"].get("PC-B"), "offline_verdict": "NO-GO",
                     "evidence_path": f"{R}/positive_control_analysis.json#comparison"})
    FT = _ld(f"{R}/ft_analysis.json")   # position fine-tune (finetune_position_preregistration.md §14)
    if FT:
        for blk, ctx in (("T1", "fine-tune vs old, start +3 cm (held out, primary)"), ("T2", "fine-tune vs old, start -3 cm (held out, symmetry)")):
            p = FT[blk]["primary"]
            rows.append({"candidate": "FT-FP16", "context": ctx, "success": p["ft"], "reference": p["old"], "reference_name": "VC-025 (old policy)",
                         "e1_ci_pp": [round(x, 1) for x in p["newcombe95_pp"]], "comparison": "improvement (lower bound > 0)",
                         "verdict": "IMPROVEMENT_DETECTED" if p["improvement_detected"] else "NOT_DETECTED", "e2e_ms": None,
                         "evidence_path": f"{R}/ft_analysis.json#{blk}.primary"})
        q = FT["T0"]["secondary"]
        rows.append({"candidate": "FT-FP16", "context": "fine-tune vs old, training start mark (secondary)", "success": q["test_k_n"], "reference": q["ref_k_n"],
                     "reference_name": "VC-025 (old policy)", "e1_ci_pp": [round(x, 1) for x in q["E1"]["ci_pp"]], "e2": q["E2"]["decision"],
                     "verdict": q["verdict"], "evidence_path": f"{R}/ft_analysis.json#T0.secondary"})
    cost = {"VC-025": 11.6, "VC-002": 16.8, "VC-020": 16.8, "VC-005": 17.1, "VC-000": 53.4, "FT-FP16": 11.6}
    for r in rows:   # next actions are decided by code, not by the model
        if r["candidate"] == "PC-B" and r["context"] == "positive control real arm":
            r["next_action"] = ("Offline warning not confirmed on the arm in 12 trials (unresolved, not 'tolerated'); keep rejecting this build at the "
                                "calibration-input check; do not read the offline audit as a predictor of closed-loop failure")
        elif r["verdict"] == "IMPROVEMENT_DETECTED":
            r["next_action"] = "Use the fine-tuned policy where the start position varies; confirm at more positions and objects before relying on it"
        elif r["candidate"] == "FT-FP16" and r["verdict"] == "INSUFFICIENT_EVIDENCE":
            r["next_action"] = ("Check that the fine-tune keeps nominal performance: 10/12 vs 12/12 at the training mark is undecided; plan more trials at the "
                                "training mark before replacing the old policy there")
        elif r["verdict"] == "INSUFFICIENT_EVIDENCE":
            r["next_action"] = ("Settle success against FP32 at 10 pp: plan about 110-120 trials per arm (planning estimate, assumes equal true rates near 96-97 percent; not a guarantee)"
                                + ("; also validate start-position changes before deployment" if r["candidate"] == "VC-025" else ""))
        elif r["verdict"] == "FLAGGED":
            r["next_action"] = "Do not deploy; fix the calibration input (a simple input check catches it); see the real-arm check of PC-B"
        elif r["verdict"] == "NO-GO":
            r["next_action"] = "Reject this build"
        elif r["verdict"] == "GO":
            r["next_action"] = "Eligible for approval within the validated conditions only"
    for r in rows:
        if r["candidate"] in cost: r["gpu_ms_trtexec"] = cost[r["candidate"]]
    return {"rows": rows, "notes": {
        "recommendation_vs_approval": ("FP16 is the recommended precision to validate first (cheapest on the device). The position fine-tune (FT-FP16, same FP16 engine "
                                       "cost) fixed the start-position weakness at both held-out shifts (IMPROVEMENT_DETECTED at +3 cm and -3 cm), so FT-FP16 is the "
                                       "candidate to validate next where start positions vary. Approval is a separate status: on hold, because every comparison "
                                       "against full precision is INSUFFICIENT_EVIDENCE and the fine-tune's nominal performance is undecided."),
        "gpu_ms_source": f"{R}/power_bench/SUMMARY.md (trtexec, 15 W)",
        "simple_checks_scope": "The action-MSE and audit-score thresholds were set on the same 24 normal cells, so '0 normal cells flagged' holds by construction; only the input check is independent of that set.",
        "ai_judge": ("Cosmos-Reason2 end-of-trial judge, held-out eval of 273 recorded trials (artifacts/cosmos_judge/eval_scores.jsonl): "
                     "first setup 1/21 failures caught; validated prompt C1 p1 20/21 caught, 5/252 false alarms, 4 of them on the unseen yellow can (4/33). "
                     "Wording-sensitive; end state only. Re-checked live and prospectively in the fine-tune evaluation (72 new trials): 21/23 failures caught, "
                     "1/49 false alarms (artifacts/reports/ft_cosmos_live_judge.json).")}}


SYSTEM = """You explain a robotics deployment review. The verdicts and numbers are already decided by code.
RULES: 1) Never change or re-derive a verdict. Use exactly: GO, NO-GO, INSUFFICIENT_EVIDENCE, FLAGGED.
2) Use only numbers that appear in the table, attached to the candidate they belong to. 3) Name candidates by code (VC-025 etc.).
4) Keep recommendation (what to validate first) separate from approval. 5) Concise, factual, English, no marketing words.
6) Write for a robot developer in plain words. Never print JSON field names (no "e2e_ms", "gpu_ms_trtexec", "e1_ci_pp"):
say "end-to-end latency", "GPU time on the device", "success interval". 7) Do not write next actions; code appends them."""
USER = """Decided verdict table:
```json
{table}
```
Write exactly three sections: ## 1. Recommendation ## 2. Approval status ## 3. Flagged candidates
(Section 4, the next actions, is written by code from each row's next_action; do not write it.)"""

CODE = re.compile(r"\b(VC-\d{3}|PC-[NB])\b"); FRAC = re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b")
VERD = re.compile(r"\b(INSUFFICIENT_EVIDENCE|INSUFFICIENT EVIDENCE|NO-GO|GO|FLAGGED)\b")
MS = re.compile(r"(\d+(?:\.\d+)?)\s*ms\b")


CONTEXT_WORDS = {"G6": ("g6", "nominal"), "S4": ("s4", "unseen", "yellow"), "FP16 run": ("fp16 run", "fp16 block"),
                 "positive control": ("positive control", "real arm"), "offline": ("offline",)}
DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")


def check_report(text, table):
    text = text.translate(DASHES)   # models write VC\u2011025 etc.; normalize so candidate-bound checks still apply
    by = {}
    for r in table["rows"]: by.setdefault(r["candidate"], []).append(r)
    allnums = set()
    def walk(o):
        if isinstance(o, dict): [walk(v) for v in o.values()]
        elif isinstance(o, list): [walk(v) for v in o]
        elif isinstance(o, (int, float)) and not isinstance(o, bool): allnums.add(round(float(o), 2))
        elif isinstance(o, str): allnums.update(round(float(x), 2) for x in re.findall(r"\d+(?:\.\d+)?", o))
    walk(table)
    issues = []
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
        codes = set(CODE.findall(sent)); s_clean = CODE.sub(" ", sent)
        if len(codes) == 1:
            c = codes.pop(); rows = by.get(c, [])
            low = s_clean.lower()
            ctx = [k for k, v in CONTEXT_WORDS.items() if any(w in low for w in v)]
            if ctx:   # restrict to the rows of the named context(s), so values cannot be borrowed across experiments
                rows = [r for r in rows if any(k in r["context"] for k in ctx)] or rows
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
    bad = ["VC-025 succeeded 20/20.", "VC-025 is GO.", "VC-025 took 34.3 ms end to end.", "VC-002 is NO-GO.", "VC\u2011025 is GO.",
           "On the unseen can VC-002 succeeded 24/25."]
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
    text, dt = call(T)
    acts = {}
    for r in T["rows"]: acts.setdefault(r["next_action"], []).append(f"{r['candidate']} ({r['context']})")
    text = text.rstrip() + "\n\n## 4. Next actions (decided by code)\n\n" + "".join(f"- **{a}** — {', '.join(c)}\n" for a, c in acts.items())
    issues = check_report(text, T)
    head = (f"# QuantGate — deployment report v2 (auto-generated)\n\n> Verdicts are decided by code (`d3_v2_verdicts.json`, hash `{h[:16]}`); "
            f"Nemotron 3 Super (Token Factory) wrote the explanation. A structured validator checked every candidate's verdict, success "
            f"fractions and latency in the prose. v1 is kept as history (`d3_final_report.md`).\n\n| Item | Value |\n|---|---|\n"
            f"| Latency | {dt:.1f} s |\n| **Validator findings** | **{len(issues)}** |\n\n"
            + ("".join(f"- {i}\n" for i in issues) + "\n" if issues else "") + "---\n\n")
    import d3_figures
    figs = d3_figures.make_all(T, f"{a.out}/figures")
    caps = {"fig_e1_forest.png": "Success vs FP32 per candidate: every Newcombe interval crosses the 10 pp tolerance, so no GO yet.",
            "fig_cost_evidence.png": "GPU time on the device vs real-arm success: FP16 is cheapest; success intervals overlap.",
            "fig_frames.png": "The frames behind two verdicts: a success, and a failure that Cosmos called a success."}
    figmd = "\n\n## Figures (drawn by code from the verdict table)\n\n" + "".join(f"![{caps[f]}](figures/{f})\n\n*{caps[f]}*\n\n" for f in figs)
    open(f"{a.out}/d3_report_v2.md", "w").write(head + text + figmd)
    json.dump({"verdict_hash": h, "issues": issues, "latency_sec": round(dt, 1), "selftest": st, "text": text}, open(f"{a.out}/d3_report_v2_run.json", "w"), indent=1)
    print("written", f"{a.out}/d3_report_v2.md", "issues", len(issues))
