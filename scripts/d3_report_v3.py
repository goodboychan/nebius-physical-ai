"""`D3` deployment report v3 (2026-10-14, external review 5): **code writes every verdict, number and status; the model
writes only the explanation and the open questions.**

Why v3: the v2 validator checked numbers sentence by sentence, and three wrong sentences passed it
("VC-025 is GO and VC-002 is GO.", "VC-025 succeeded 10/10.", "VC-025 took 11.6 ms end-to-end."). v2 is kept as history.

1. `verdict_table()` (from d3_report_v2) builds the decided verdicts from committed artifacts.
2. Sections 1–4 are rendered by code from that table: the recommendation, one line per candidate (verdict, success
   against its reference, success interval, end-to-end latency and GPU time, each labelled), flagged builds and next
   actions.
3. Nemotron 3 Super (Token Factory) writes section 5 only: why the verdicts look like this and what to resolve before
   approval. `check_explanation()` rejects the section if it contains
   - any digit (so it cannot state or misattribute a number, fraction or latency),
   - any verdict label (GO, NO-GO, INSUFFICIENT_EVIDENCE, FLAGGED),
   - approval or safety vocabulary (approve, safe, pass, ready, guarantee, proven, equivalent, harmless, certify, ship).
   On findings the model is asked once more with the findings; both attempts are recorded. If the second attempt still
   fails, section 5 is replaced by a notice and the findings are shown.
   Residual risk, stated in the report: a qualitative misreading in plain words cannot be excluded by these rules. Section 5 is
   labelled as model-written and is never a source of verdicts or numbers.
Usage: python scripts/d3_report_v3.py [--out artifacts/reports] [--dry]"""
import argparse, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "src")
from edgeqgate.hashing import hash_obj
from d3_report_v2 import verdict_table, R

SYSTEM = """You explain a robot deployment review to a robot developer. Code has already decided every verdict, number and status
and prints them above your text. Your text must contain NO digits at all, NO verdict labels (GO, NO-GO, INSUFFICIENT_EVIDENCE,
FLAGGED), and none of these words: approve, approved, approval, safe, pass, passed, ready, guarantee, proven, equivalent, harmless,
certify, ship. Refer to candidates by role ("the FP16 candidate", "the INT8 builds", "the black-frame build"), not by numbers.
Plain English, concise, no marketing words."""
USER = """The decided review (for your understanding only; do not repeat its numbers):
```json
{table}
```
Write exactly two sections, in words only:
## Why the review looks like this
(three to five sentences: why the cheapest candidate is the one to validate first, why the success comparisons cannot be decided
yet, why the deliberately miscalibrated builds are rejected at the input check, and what the AI judge's record means for trusting it)
## Questions to resolve before deployment
(three to five bullet points, each a concrete question the developer must answer with more trials or checks)"""

FORBIDDEN = [("digit", re.compile(r"\d")),
             ("verdict label", re.compile(r"\bNO-GO\b|\bGO\b|INSUFFICIENT[ _]EVIDENCE|\bFLAGGED\b", re.I)),
             ("approval or safety word", re.compile(r"\b(approv\w*|safe\w*|pass(?:es|ed|ing)?|ready|guarantee\w*|prove[nd]?|equivalen\w*|harmless|certif\w*|ship(?:s|ped|ping)?)\b", re.I))]
DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")


def check_explanation(text):
    t = (text or "").translate(DASHES); issues = []
    for line in t.splitlines():
        body = re.sub(r"^#+\s*", "", line).strip()
        if not body: continue
        for name, rx in FORBIDDEN:
            for m in rx.finditer(body):
                issues.append(f"{name} '{m.group(0)}' — \"{body[:90]}\"")
    return sorted(set(issues))


def selftest():
    good = ("## Why the review looks like this\nThe FP16 candidate is the cheapest engine on the device, so it is the one to "
            "validate first. Its success comparison with full precision rests on too few trials to decide either way.\n"
            "## Questions to resolve before deployment\n- How many more interleaved trials settle the comparison at the chosen tolerance?")
    bad = ["VC-025 is GO and VC-002 is GO.", "VC-025 succeeded 10/10.", "VC-025 took 11.6 ms end-to-end.",   # external review 5
           "The FP16 candidate is approved.", "The INT8 builds are safe to ship.", "It passes the gate.", "The FP16 candidate is go."]
    res = {"good_issues": check_explanation(good), "bad_caught": {b: bool(check_explanation(b)) for b in bad}}
    assert not res["good_issues"] and all(res["bad_caught"].values()), res
    return res


def fmt_pp(ci): return f"[{ci[0]:+.1f}, {ci[1]:+.1f}] pp" if ci else "—"


def code_sections(T):
    rows = T["rows"]; n = T["notes"]; L = []
    L += ["## 1. Recommendation (written by code)", "", n["recommendation_vs_approval"], ""]
    L += ["## 2. Verdict per candidate (written by code)", "",
          "Success intervals are Newcombe intervals for candidate minus reference, in percentage points, against a 10 pp tolerance. "
          "End-to-end latency is the runner's per-chunk time on the arm; GPU time is trtexec on the device (15 W).", ""]
    for r in rows:
        if r["verdict"] == "FLAGGED": continue
        parts = [f"**{r['candidate']}** · {r['context']} · `{r['verdict']}`"]
        if r.get("success"): parts.append(f"success {r['success'][0]}/{r['success'][1]} against reference {r['reference'][0]}/{r['reference'][1]}")
        parts.append(f"success interval {fmt_pp(r.get('e1_ci_pp'))}")
        if r.get("e2"): parts.append(f"placement: {r['e2'].replace('_', ' ')}")
        if r.get("e2e_ms") is not None: parts.append(f"end-to-end {r['e2e_ms']} ms")
        if r.get("gpu_ms_trtexec") is not None: parts.append(f"GPU time on device {r['gpu_ms_trtexec']} ms")
        L.append("- " + " · ".join(parts) + f" (`{r['evidence_path']}`)")
    L += ["", "## 3. Flagged builds (written by code)", ""]
    for r in rows:
        if r["verdict"] == "FLAGGED":
            L.append(f"- **{r['candidate']}** · {r['context']} · `FLAGGED` by {', '.join(r['flagged_by'])} (`{r['evidence_path']}`)")
    L += ["", n["simple_checks_scope"], "", f"AI judge: {n['ai_judge']}", ""]
    acts = {}
    for r in rows: acts.setdefault(r["next_action"], []).append(f"{r['candidate']} ({r['context']})")
    L += ["## 4. Next actions (written by code)", ""] + [f"- **{a}** — {', '.join(c)}" for a, c in acts.items()] + [""]
    return "\n".join(L)


def call(messages, max_tokens=8192):
    import http.client
    body = json.dumps({"model": "nvidia/nemotron-3-super-120b-a12b", "max_tokens": max_tokens, "temperature": 0.2, "messages": messages})
    conn = http.client.HTTPSConnection("api.studio.nebius.com", timeout=300); t0 = time.time()
    conn.request("POST", "/v1/chat/completions", body=body, headers={"Authorization": f"Bearer {os.environ['NEBIUS_API_KEY']}", "Content-Type": "application/json"})
    r = conn.getresponse(); raw = r.read(); conn.close()
    if r.status != 200: raise RuntimeError(f"HTTP {r.status}")
    return json.loads(raw)["choices"][0]["message"]["content"] or "", time.time() - t0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=R); ap.add_argument("--dry", action="store_true"); a = ap.parse_args()
    T = verdict_table(); st = selftest(); h = hash_obj(T)
    json.dump(T, open(f"{a.out}/d3_v3_verdicts.json", "w"), indent=1)
    print("rows", len(T["rows"]), "selftest", json.dumps(st)[:200])
    codes = code_sections(T)
    if a.dry: print(codes[:1500]); sys.exit(0)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER.format(table=json.dumps(T, indent=1))}]
    attempts = []
    for k in range(2):
        text, dt = call(msgs); issues = check_explanation(text); attempts.append({"text": text, "issues": issues, "latency_sec": round(dt, 1)})
        if not issues: break
        msgs += [{"role": "assistant", "content": text},
                 {"role": "user", "content": "Your text broke these rules; rewrite both sections without them:\n" + "\n".join(issues)}]
    final = attempts[-1]
    expl = final["text"].strip() if not final["issues"] else "*The model-written explanation was withheld: it broke the wording rules twice (see findings).*"
    expl = re.sub(r"^##\s*", "## 5. ", expl, count=1, flags=re.M); expl = re.sub(r"\n##\s*(?!5\.)", "\n## 6. ", expl, count=1)
    head = (f"# QuantGate — deployment report v3 (auto-generated)\n\n> Sections 1–4 are written by code from the verdict table "
            f"(`d3_v3_verdicts.json`, hash `{h[:16]}`). Sections 5–6 are written by Nemotron 3 Super (Token Factory) and checked by code: "
            f"no digits, no verdict labels, no approval or safety words. They are never a source of verdicts or numbers; a qualitative "
            f"misreading in plain words cannot be excluded by these rules. v2 is kept as history (`d3_report_v2.md`).\n\n| Item | Value |\n|---|---|\n"
            f"| Model attempts | {len(attempts)} |\n| Latency | {sum(x['latency_sec'] for x in attempts):.1f} s |\n"
            f"| **Wording findings (final attempt)** | **{len(final['issues'])}** |\n\n"
            + ("".join(f"- {i}\n" for i in final["issues"]) + "\n" if final["issues"] else "") + "---\n\n")
    import d3_figures
    figs = d3_figures.make_all(T, f"{a.out}/figures")
    caps = {"fig_e1_forest.png": "Success vs FP32 per candidate: every Newcombe interval crosses the 10 pp tolerance, so no GO yet.",
            "fig_cost_evidence.png": "GPU time on the device vs real-arm success: FP16 is cheapest; success intervals overlap.",
            "fig_frames.png": "The frames behind two verdicts: a success, and a failure that Cosmos's first setup called a success."}
    figmd = "\n\n## Figures (drawn by code from the verdict table)\n\n" + "".join(f"![{caps[f]}](figures/{f})\n\n*{caps[f]}*\n\n" for f in figs)
    open(f"{a.out}/d3_report_v3.md", "w").write(head + codes + "\n" + expl + "\n" + figmd)
    json.dump({"verdict_hash": h, "issues": final["issues"], "latency_sec": round(sum(x['latency_sec'] for x in attempts), 1), "selftest": st,
               "attempts": attempts}, open(f"{a.out}/d3_report_v3_run.json", "w"), indent=1)
    print("written", f"{a.out}/d3_report_v3.md", "attempts", len(attempts), "final findings", len(final["issues"]))
