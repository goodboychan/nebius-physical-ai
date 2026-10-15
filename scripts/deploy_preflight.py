"""Deployment preflight for one candidate card, with a fault-injection demo (external review 5, 2026-10-14).

For a candidate, four checks run in order. The first failing check decides the outcome:
  1. engine integrity  : the engine file's sha256 equals the recorded build hash          -> BLOCK if not
  2. normalization     : so101_trial.resolve_norm (the runner's own guard, manifest required) -> BLOCK if it refuses
  3. timing contract   : measured worst-case latency (p95 or max) <= the runner's chunk deadline (PREF-BLEND)/FPS -> BLOCK if over
  4. evidence          : the code-decided verdict (d3_v3_verdicts.json)
                         only an explicit GO -> OK; FLAGGED/NO-GO -> BLOCK; INSUFFICIENT_EVIDENCE, IMPROVEMENT_DETECTED and
                         NOT_DETECTED -> HOLD (with the next action); any other label -> BLOCK (external review 6)
The demo builds a scratch folder with stand-in engine and normalization files, then runs a nominal case and
deliberately broken cases. The broken cases are labelled FAULT INJECTION; they are not observed failures.
Usage: python scripts/deploy_preflight.py [--out artifacts/reports]"""
import argparse, ast, hashlib, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "so101_trial.py")).read()
TREE = ast.parse(SRC)
G = {"os": os, "sys": sys, "json": json}
exec(compile(ast.Module(body=[n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "resolve_norm"], type_ignores=[]), "so101_trial", "exec"), G)
CONST = {}
for n in TREE.body:   # PREF, BLEND and FPS exactly as the runner defines them
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Tuple) and isinstance(n.value, ast.Tuple):
                for a, b in zip(t.elts, n.value.elts):
                    if isinstance(a, ast.Name) and isinstance(b, ast.Constant): CONST[a.id] = b.value
            elif isinstance(t, ast.Name) and isinstance(n.value, ast.Constant): CONST[t.id] = n.value.value
DEADLINE_MS = (CONST["PREF"] - CONST["BLEND"]) / CONST["FPS"] * 1000
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()


# IMPROVEMENT_DETECTED says a fix worked where it was tested, not that the build may replace the old one
HOLD_VERDICTS = ("INSUFFICIENT_EVIDENCE", "IMPROVEMENT_DETECTED", "NOT_DETECTED")


def preflight(card):
    steps = []
    ok = os.path.exists(card["engine"]) and sha(card["engine"]) == card["engine_sha256"]
    steps.append(("engine integrity", ok, "hash matches the recorded build" if ok else "engine file differs from the recorded build"))
    if not ok: return "BLOCK", steps
    try:
        G["resolve_norm"](card["engine"], require_manifest=True); steps.append(("normalization", True, "manifest and hash match"))
    except SystemExit:
        steps.append(("normalization", False, "runner refuses: manifest missing or normalization file mismatched")); return "BLOCK", steps
    ok = card["latency_ms"] <= DEADLINE_MS
    steps.append(("timing contract", ok, f"{card['latency_label']} {card['latency_ms']} ms vs chunk deadline {DEADLINE_MS:.0f} ms"))
    if not ok: return "BLOCK", steps
    v = card["verdict"]   # only an explicit GO is approval; every other known label holds, anything unknown blocks
    if v == "GO": steps.append(("evidence", True, "GO within the validated conditions")); return "OK", steps
    if v in ("FLAGGED", "NO-GO"): steps.append(("evidence", False, f"{v}: {card['next_action']}")); return "BLOCK", steps
    if v in HOLD_VERDICTS: steps.append(("evidence", True, f"{v} is not approval: {card['next_action']}")); return "HOLD", steps
    steps.append(("evidence", False, f"unknown verdict {v!r}: refused")); return "BLOCK", steps


def demo(out):
    T = json.load(open(os.path.join(out, "d3_v3_verdicts.json")))
    row = lambda c, ctx: next(r for r in T["rows"] if r["candidate"] == c and ctx in r["context"])
    fp16, pcb, ft = row("VC-025", "FP16 run"), row("PC-B", "offline"), row("FT-FP16", "+3 cm")
    d = tempfile.mkdtemp(prefix="preflight_")
    def folder(name, manifest=True, tamper=False):
        f = os.path.join(d, name); os.makedirs(f)
        open(f"{f}/E.engine", "wb").write(b"stand-in engine bytes"); open(f"{f}/E.norm_stats.npz", "wb").write(b"stand-in normalization")
        if manifest: json.dump({"E": {"file": "E.norm_stats.npz", "sha256": sha(f"{f}/E.norm_stats.npz")}}, open(f"{f}/norm_manifest.json", "w"))
        if tamper: open(f"{f}/E.norm_stats.npz", "wb").write(b"normalization from another policy")
        return f"{f}/E.engine"
    rec = hashlib.sha256(b"stand-in engine bytes").hexdigest()
    tr = [json.loads(l) for l in open("artifacts/trials/fp16_unsealed/stress_fp16_F0_sealed.jsonl")]
    rtt = max(r["rtt_ms_max"] for r in tr if r["cell"] == "VC-025"); n = sum(r["cell"] == "VC-025" for r in tr)
    base = {"engine_sha256": rec, "latency_ms": rtt, "latency_label": f"max round trip over {n} FP16 trials", "verdict": fp16["verdict"], "next_action": fp16["next_action"]}
    cases = [("nominal", "FP16 (VC-025) as measured", {**base, "engine": folder("nominal")}),
             ("fault: normalization file swapped", "FAULT INJECTION", {**base, "engine": folder("swapped", tamper=True)}),
             ("fault: manifest missing", "FAULT INJECTION", {**base, "engine": folder("nomanifest", manifest=False)}),
             ("fault: engine replaced after the audit", "FAULT INJECTION", {**base, "engine": folder("replaced"), "engine_sha256": "0" * 64}),
             ("timing: Hailo-8 split pipeline", "measured offline (hailo_probe_v1.json, p95 264 ms)", {**base, "engine": folder("hailo"), "latency_ms": 264, "latency_label": "p95 on the Pi 5"}),
             ("evidence: fine-tuned policy, improvement at +3 cm", "FT-FP16, improvement detected; training mark undecided",
              {**base, "engine": folder("ft"), "verdict": ft["verdict"], "next_action": ft["next_action"]}),
             ("evidence: black-frame calibration", "PC-B, flagged offline", {**base, "engine": folder("pcb"), "verdict": pcb["verdict"], "next_action": pcb["next_action"]})]
    res = []
    for name, note, card in cases:
        outcome, steps = preflight(card)
        res.append({"case": name, "note": note, "outcome": outcome, "steps": [{"check": a, "pass": b, "detail": c} for a, b, c in steps]})
    shutil.rmtree(d)
    return {"deadline_ms": DEADLINE_MS, "runner_constants": {k: CONST[k] for k in ("PREF", "BLEND", "FPS")}, "cases": res}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="artifacts/reports"); a = ap.parse_args()
    R = demo(a.out)
    json.dump(R, open(os.path.join(a.out, "preflight_demo.json"), "w"), indent=1)
    for c in R["cases"]:
        last = c["steps"][-1]; print(f"{c['outcome']:5}  {c['case']:42} {last['check']}: {last['detail'][:90]}")
