"""Errata grounding with Nemotron (docs/errata_grounding_preregistration.md). Committed before any Nemotron call.
Nemotron labels each Tavily result against our measured facts; code validates every quote and number.
Usage: python d5_errata_grounding.py [--config configs/errata_grounding_v1.json] [--out artifacts/reports] [--selftest]
env: NEBIUS_API_KEY (Token Factory)"""
import argparse, http.client, json, os, re, sys, time

MODEL = "nvidia/nemotron-3-super-120b-a12b"
SYSTEM = ("You check whether a field report about TensorRT or Jetson concerns a specific deployment that has already "
          "been measured. You only use the text you are given. You answer with one JSON object and nothing else.")
USER = """Build profile:
{profile}

Measured facts on this build:
{facts}

Labels:
{labels}

Field report (one web search result):
TITLE: {title}
URL: {url}
CONTENT:
<<<
{content}
>>>

Answer with one JSON object:
{{"label": one of {label_names}, "fact_id": the fact id for MATCHES or CONTRASTS, otherwise null,
  "quote": a verbatim excerpt of 20 to 300 characters copied exactly from CONTENT that supports the label,
  "explanation": one or two sentences}}"""

def norm(s): return re.sub(r"\s+", " ", (s or "")).strip().lower()
NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")

def results(cfg):
    snap = json.load(open(cfg["snapshot"])); assert snap["snapshot_hash"] == cfg["snapshot_hash"], "snapshot changed"
    out, i = [], 0
    for q in snap["queries"]:
        for r in snap["results"][q]:
            i += 1; out.append({"id": f"R{i:02d}", "query": q, **{k: r[k] for k in ("title", "url", "content")}})
    return out

def validate(ans, res, cfg):
    """Return a list of rule violations (empty = accepted)."""
    F, L = cfg["facts"], cfg["labels"]; bad = []
    if not isinstance(ans, dict): return ["R1: no JSON object"]
    lab, fid, quote, expl = ans.get("label"), ans.get("fact_id"), ans.get("quote") or "", ans.get("explanation") or ""
    if lab not in L: bad.append(f"R1: label {lab!r} not allowed")
    needs = lab in ("MATCHES", "CONTRASTS")
    if needs and fid not in F: bad.append(f"R2: fact_id {fid!r} missing or unknown")
    if not needs and fid not in (None, "", "null"): bad.append(f"R2: fact_id {fid!r} given for {lab}")
    if len(quote.strip()) < 20: bad.append("R3: quote shorter than 20 characters")
    elif norm(quote) not in norm(res["content"]): bad.append("R3: quote not found in the content")
    allowed = set(NUM.findall(res["content"])) | set(NUM.findall(quote))
    if fid in F: allowed |= {f"{x:g}" for x in F[fid]["numbers"]} | {str(x) for x in F[fid]["numbers"]}
    for n in NUM.findall(expl):
        if n not in allowed and not re.fullmatch(r"F?\d", n) and n not in ("10.3", "10.3.0"):
            bad.append(f"R4: number {n} not in the quote, content or fact")
    return bad

def parse(text):
    m = re.findall(r"\{.*\}", text or "", flags=re.S)
    for cand in reversed(m):
        try: return json.loads(cand)
        except json.JSONDecodeError: continue
    return None

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["label", "fact_id", "quote", "explanation"],
          "properties": {"label": {"type": "string", "enum": ["MATCHES", "CONTRASTS", "APPLIES_UNVERIFIED", "NOT_APPLICABLE"]},
                         "fact_id": {"type": ["string", "null"]}, "quote": {"type": "string"}, "explanation": {"type": "string"}}}

def call(prompt, max_tokens=4096, structured=True):
    # amendment 1 (v1.1): structured output, because v1 broke JSON in 14/25 answers (unquoted explanation values)
    extra = {"response_format": {"type": "json_schema", "json_schema": {"name": "erratum", "schema": SCHEMA, "strict": True}}} if structured else {}
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "temperature": 0, **extra,
                       "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]})
    for attempt in range(3):
        try:
            conn = http.client.HTTPSConnection("api.studio.nebius.com", timeout=300); t0 = time.time()
            conn.request("POST", "/v1/chat/completions", body=body, headers={"Authorization": f"Bearer {os.environ['NEBIUS_API_KEY']}", "Content-Type": "application/json"})
            r = conn.getresponse(); raw = r.read(); conn.close()
            if r.status != 200: raise RuntimeError(f"HTTP {r.status}")
            d = json.loads(raw); return d["choices"][0]["message"]["content"] or "", time.time() - t0, d.get("usage", {})
        except Exception as e:
            err = e; time.sleep(3)
    raise err

def selftest(cfg, R):
    r = R[10]  # R11, the 2.7x regression thread
    good = {"label": "MATCHES", "fact_id": "F1", "quote": r["content"][r["content"].find("$ /usr/src"):][:60], "explanation": "INT8 is slower here too."}
    bads = [{**good, "quote": "INT8 is three times slower on every Jetson ever made"},          # fabricated quote
            {**good, "fact_id": "F9"},                                                          # unknown fact
            {**good, "explanation": "INT8 took 99.9 ms against FP16."},                         # invented number
            {**good, "label": "NOT_APPLICABLE"}]                                                # fact_id on a non-match
    res = {"good": validate(good, r, cfg), "bad_caught": [bool(validate(b, r, cfg)) for b in bads]}
    assert not res["good"] and all(res["bad_caught"]), res
    return res

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--config", default="configs/errata_grounding_v1.json")
    ap.add_argument("--out", default="artifacts/reports"); ap.add_argument("--selftest", action="store_true"); ap.add_argument("--v1-format", action="store_true"); a = ap.parse_args()
    cfg = json.load(open(a.config)); R = results(cfg); assert len(R) == 25 and set(cfg["reference_labels"]) == {r["id"] for r in R}
    st = selftest(cfg, R); print("selftest", st)
    if a.selftest: sys.exit(0)
    facts = "\n".join(f"{k}: {v['text']}" for k, v in cfg["facts"].items()); labels = "\n".join(f"{k}: {v}" for k, v in cfg["labels"].items())
    rows = []
    for r in R:
        prompt = USER.format(profile=cfg["build_profile"], facts=facts, labels=labels, label_names=list(cfg["labels"]), **{k: r[k] for k in ("title", "url", "content")})
        text, dt, usage = call(prompt, structured=not a.v1_format); ans = parse(text); bad = validate(ans, r, cfg)
        ref = cfg["reference_labels"][r["id"]]
        rows.append({"id": r["id"], "title": r["title"], "url": r["url"], "answer": ans, "violations": bad, "accepted": not bad,
                     "reference": ref, "latency_s": round(dt, 2), "usage": usage, "raw_tail": (text or "")[-400:]})
        print(r["id"], (ans or {}).get("label"), (ans or {}).get("fact_id"), "ref", ref, "OK" if not bad else bad, f"{dt:.1f}s", flush=True)
    # metrics
    key = lambda x: tuple(x) if x else None
    refpos = [w for w in rows if w["reference"][0] in ("MATCHES", "CONTRASTS")]
    hit = [w for w in refpos if w["accepted"] and [w["answer"].get("label"), w["answer"].get("fact_id")] == w["reference"]]
    extra = [w["id"] for w in rows if w["accepted"] and w["answer"].get("label") in ("MATCHES", "CONTRASTS") and w["reference"][0] not in ("MATCHES", "CONTRASTS")]
    labs = list(cfg["labels"]); conf = {rl: {ml: 0 for ml in labs + ["REJECTED"]} for rl in labs}
    for w in rows: conf[w["reference"][0]][(w["answer"] or {}).get("label") if w["accepted"] else "REJECTED"] += 1
    viol = {}
    for w in rows:
        for v in w["violations"]: viol[v[:2]] = viol.get(v[:2], 0) + 1
    lat = sorted(w["latency_s"] for w in rows)
    M = {"model": MODEL, "n": len(rows), "primary_recall": [len(hit), len(refpos)], "extra_positive": extra, "accepted": sum(w["accepted"] for w in rows),
         "violations_by_rule": viol, "confusion_ref_x_model": conf, "latency_s_median": lat[len(lat) // 2],
         "tokens_total": {k: sum((w["usage"] or {}).get(k, 0) or 0 for w in rows) for k in ("prompt_tokens", "completion_tokens")}, "selftest": st}
    json.dump({"metrics": M, "rows": rows, "config": a.config, "snapshot_hash": cfg["snapshot_hash"]}, open(f"{a.out}/errata_grounded.json", "w"), indent=1)
    F = cfg["facts"]; L = ["# Field reports checked against our measurements (D5 + Nemotron)", "",
         f"Snapshot `{cfg['snapshot_hash'][:16]}…` (Tavily, 25 results). Labels by `{MODEL}`; every quote and number checked by code.",
         "Our numbers in the table come from the facts file, not from the model.", "",
         "| Field report | Label | Our measurement | Supporting quote (verbatim) |", "|---|---|---|---|"]
    for w in rows:
        if w["accepted"] and w["answer"]["label"] in ("MATCHES", "CONTRASTS"):
            f = F[w["answer"]["fact_id"]]
            L.append(f"| [{w['title'][:70]}]({w['url']}) | {w['answer']['label']} {w['answer']['fact_id']} | {f['text']} ([source]({f['source']})) | “{w['answer']['quote'][:200]}” |")
    L += ["", f"Primary: {len(hit)}/{len(refpos)} reference matches/contrasts recovered; extra positives: {extra or 'none'}; "
          f"accepted {M['accepted']}/25; rejected by rule: {viol or 'none'}; median latency {M['latency_s_median']} s."]
    open(f"{a.out}/errata_grounded.md", "w").write("\n".join(L) + "\n")
    print(json.dumps({k: M[k] for k in ("primary_recall", "extra_positive", "accepted", "violations_by_rule", "latency_s_median", "tokens_total")}))
