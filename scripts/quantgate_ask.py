"""Ask the deployment review a question. Nemotron 3 Super (Nebius Token Factory) picks the verdict-table rows that bear on
the question and explains them in words. Code prints every verdict, number and next action from those rows.

Contract, as in report v3:
  - the model returns structured JSON (Token Factory structured output): the row ids it relies on, an explanation, and
    the checks still missing;
  - code rejects unknown row ids and any explanation or check that contains a digit, a verdict label, approval or
    safety words, or a known misreading (d3_report_v3.check_explanation);
  - on findings the model is asked once more with them; if it still fails, its text is withheld and only the rows are shown;
  - the answer is never a deployment approval: the closing line is always written by code.
Usage: python scripts/quantgate_ask.py "<question>" [...]     env: NEBIUS_API_KEY
       python scripts/quantgate_ask.py --examples              (writes artifacts/reports/ask_examples.md)"""
import http.client, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from d3_report_v2 import verdict_table
from d3_report_v3 import check_explanation, fmt_pp

MODEL = "nvidia/nemotron-3-super-120b-a12b"
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["row_ids", "explanation", "missing_checks"],
          "properties": {"row_ids": {"type": "array", "items": {"type": "integer"}}, "explanation": {"type": "string"},
                         "missing_checks": {"type": "array", "items": {"type": "string"}}}}
SYSTEM = """You answer a robot developer's question about a deployment review. Code has decided every verdict and number.
You get the review as numbered rows. Return JSON: row_ids (the rows that bear on the question), explanation (two to four
sentences in plain words), missing_checks (one to three short checks still needed). In explanation and missing_checks use
NO digits, NO verdict labels (GO, NO-GO, INSUFFICIENT_EVIDENCE, FLAGGED, IMPROVEMENT_DETECTED, NOT_DETECTED), and none of:
approve, approved, approval, safe, pass, ready, guarantee, proven, equivalent, harmless, certify, ship, trusted, reliable,
better than. Never say anything is cleared for deployment. Refer to candidates by role ("the FP16 build", "the fine-tuned
policy"). Facts you must not misstate: FP16 has the lowest energy per inference but draws more power while running than
INT8; more trials aim to show a difference stays within a tolerance; the AI judge was re-checked on new live trials and
held up, but other objects and scenes are open. If rows exist for something, never say there is no evidence for it; say what
they show and what they do not settle. Cite every row the question names. Do not claim in the explanation that anything is missing,
untested or unmeasured; put open items only in missing_checks."""


# measured engines only: power_bench/SUMMARY.md (VC-000, VC-025, VC-002, VC-005, VC-020) and power_bench_ft/SUMMARY.md (FT-FP16).
# The other INT8 cells share the architecture but were never benched, so they get no number.
ENERGY_MJ = {"VC-025": 82, "FT-FP16": 82, "VC-000": 403, "VC-002": 101, "VC-005": 101, "VC-020": 101}
KEYWORDS = {"int8": lambda r: r["candidate"].startswith("VC-0") and r["candidate"] not in ("VC-025", "VC-000"),
            "fp16": lambda r: r["candidate"] in ("VC-025", "FT-FP16"), "fine-tun": lambda r: r["candidate"] == "FT-FP16",
            "position": lambda r: r["candidate"] == "FT-FP16", "judge": lambda r: r["candidate"] == "AI-JUDGE", "cosmos": lambda r: r["candidate"] == "AI-JUDGE",
            "calibration": lambda r: r["verdict"] == "FLAGGED", "miscalibrat": lambda r: r["verdict"] == "FLAGGED"}


def all_rows(T):
    """The verdict-table rows plus the AI judge record (from the table notes), so every claim has a row to cite."""
    R = [dict(r) for r in T["rows"]]
    for r in R:
        if r["candidate"] in ENERGY_MJ: r["energy_mj_per_inference"] = ENERGY_MJ[r["candidate"]]
    R.append({"candidate": "AI-JUDGE", "context": "Cosmos-Reason2 end-of-trial success judge", "verdict": "CONDITIONAL", "record": T["notes"]["ai_judge"] + (" It HAS been evaluated on one object not seen in training (the yellow can): 4 of its 33 trials "
              "were false alarms, the highest rate of any condition. Other objects and other scenes have not been evaluated."),
              "next_action": "Re-validate the exact prompt on other objects and scenes before relying on it"})
    return R


def rows_text(R):
    out = []
    for i, r in enumerate(R):
        out.append({"id": i, "candidate": r["candidate"], "context": r["context"], "verdict": r["verdict"],
                    **{k: r[k] for k in ("success", "reference", "interval", "e2", "e2e_ms", "gpu_ms_trtexec", "energy_mj_per_inference", "flagged_by", "reference_name", "record") if r.get(k) is not None},
                    "next_action": r["next_action"]})
    return out


def call(messages):
    body = json.dumps({"model": MODEL, "max_tokens": 4096, "temperature": 0, "messages": messages,
                       "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": SCHEMA, "strict": True}}})
    conn = http.client.HTTPSConnection("api.studio.nebius.com", timeout=300); t0 = time.time()
    conn.request("POST", "/v1/chat/completions", body=body, headers={"Authorization": f"Bearer {os.environ['NEBIUS_API_KEY']}", "Content-Type": "application/json"})
    r = conn.getresponse(); raw = r.read(); conn.close()
    if r.status != 200: raise RuntimeError(f"HTTP {r.status}")
    d = json.loads(raw); return d["choices"][0]["message"]["content"] or "", time.time() - t0, d.get("usage", {})


import re
ABSENCE = re.compile(r"\bno\s+(?:\w+\s+){0,3}(?:evidence|measurements?|data|results?|assessment)\b|\b(?:not|never)\s+(?:been\s+)?(?:measured|tested|evaluated|assessed)\b|\bwithout\s+(?:any\s+)?(?:evidence|data)\b", re.I)


def check(ans, n_rows, forced=()):
    if not isinstance(ans, dict): return ["no JSON object"]
    bad = [f"unknown row id {i}" for i in ans.get("row_ids", []) if not (isinstance(i, int) and 0 <= i < n_rows)]
    if not ans.get("row_ids"): bad.append("no rows cited")
    if forced and not set(forced) & set(ans.get("row_ids", [])): bad.append(f"the rows the question names were not cited: {forced}")
    bad += check_explanation(ans.get("explanation", "")) + sum((check_explanation(c) for c in ans.get("missing_checks", [])), [])
    # claims that something was never measured belong to code, not to the model (first run said "no INT8 measurements": false)
    bad += [f"absence claim '{m.group(0)}' (put open items in missing_checks)" for m in ABSENCE.finditer(ans.get("explanation", ""))]
    return bad


def render_row(i, r):
    p = [f"[{i}] {r['candidate']} · {r['context']} · `{r['verdict']}`"]
    if r.get("success"): p.append(f"{r['success'][0]}/{r['success'][1]} against {r.get('reference_name', 'reference')} {r['reference'][0]}/{r['reference'][1]}")
    iv = r.get("interval")
    if iv: p.append(f"candidate − reference {iv['candidate_minus_reference_pp']:+.1f} pp, {iv['level_pct']:g}% interval {fmt_pp(iv['ci_pp'])} ({iv['rule']})")
    if r.get("e2e_ms") is not None: p.append(f"end-to-end {r['e2e_ms']} ms")
    if r.get("gpu_ms_trtexec") is not None: p.append(f"GPU time {r['gpu_ms_trtexec']} ms")
    if r.get("energy_mj_per_inference"): p.append(f"{r['energy_mj_per_inference']} mJ per inference")
    if r.get("flagged_by"): p.append("flagged by " + ", ".join(r["flagged_by"]))
    if r.get("record"): p.append(r["record"])
    return " · ".join(p) + f"\n    next: {r['next_action']}"


def ask(q, T):
    R = all_rows(T); rows = rows_text(R)
    forced = sorted({i for k, f in KEYWORDS.items() if k in q.lower() for i, r in enumerate(R) if f(r)})   # code-side: rows the question names
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Review rows:\n{json.dumps(rows, indent=1)}\n\nNotes:\n{json.dumps(T['notes'], indent=1)}\n\n"
             + (f"Rows the question names (cite them): {forced}\n\n" if forced else "") + f"Question: {q}"}]
    tries = []
    for k in range(2):
        text, dt, usage = call(msgs)
        try: ans = json.loads(text)
        except json.JSONDecodeError: ans = None
        bad = check(ans, len(rows), forced); tries.append({"answer": ans, "findings": bad, "latency_s": round(dt, 1), "usage": usage})
        if not bad: break
        msgs += [{"role": "assistant", "content": text}, {"role": "user", "content": "Your answer broke these rules; answer again without them:\n" + "\n".join(bad)}]
    ans = tries[-1]["answer"] if not tries[-1]["findings"] else None
    ids = sorted(set((ans or tries[-1]["answer"] or {}).get("row_ids", [])) | set(forced)) if (ans or tries[-1]["answer"]) else forced
    ids = [i for i in ids if 0 <= i < len(rows)]
    L = [f"**Q: {q}**", "", "Evidence (written by code from the verdict table):", ""] + ["- " + render_row(i, R[i]).replace("\n    ", "  \n  ") for i in ids]
    if ans:
        L += ["", "Explanation (Nemotron 3 Super, checked: no digits, no verdict labels, no approval words):", "", ans["explanation"], "",
              "Still missing:", ""] + [f"- {c}" for c in ans["missing_checks"]]
    else:
        L += ["", "*The model's explanation was withheld: it broke the wording rules twice.* Findings: " + "; ".join(tries[-1]["findings"])]
    L += ["", "*This is not a deployment approval. Approval stays on hold until the listed trials are run (code).*"]
    return "\n".join(L), tries


EXAMPLES = ["Can I use the fine-tuned policy where the can's start position varies by a few centimeters?",
            "Should I deploy an INT8 build instead of FP16 to save power?",
            "Which build should I validate first on the Jetson, and why?",
            "Can I rely on the AI judge's verdict for a new object?"]

if __name__ == "__main__":
    T = verdict_table()
    if sys.argv[1:] == ["--examples"]:
        out, log = ["# Asking the deployment review (examples)", "",
                    f"Generated by `scripts/quantgate_ask.py` with `{MODEL}` on Nebius Token Factory (structured output).",
                    "- Verdicts and numbers are printed by code from the verdict table. Rows the question names are added by code even if the model omits them.",
                    "- The model's words are checked for digits, verdict labels, approval words and known misreadings.",
                    "- Residual risk: a plain-word misreading of a new kind can still pass. In the first run the model said no INT8 evidence existed and that the "
                    "judge had never seen a new object. Both were false and are now covered by the code-added rows and the judge record. The text is an aid, "
                    "never the source of a verdict.", ""], []
        for q in EXAMPLES:
            md, tries = ask(q, T); out += [md, "", "---", ""]; log.append({"question": q, "tries": tries}); print(md, "\n", flush=True)
        open("artifacts/reports/ask_examples.md", "w").write("\n".join(out)); json.dump(log, open("artifacts/reports/ask_examples_run.json", "w"), indent=1)
    else:
        for q in sys.argv[1:]: print(ask(q, T)[0], "\n")
