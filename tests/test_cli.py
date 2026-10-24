"""Developer usability review (2026-10-24): bad commands and options fail loudly, plan takes user-facing names,
a candidate card of your own runs through the preflight, and ask without a key explains itself."""
import json, os, pathlib, shutil, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "scripts/quantgate.py")]


def q(*a, env=None):
    e = {k: v for k, v in os.environ.items() if k != "NEBIUS_API_KEY"} | (env or {})
    return subprocess.run([*CLI, *a], cwd=ROOT, capture_output=True, text=True, env=e)


def test_bad_input_exits_2():
    for a in (["verfiy"], [], ["preflight", "--bogus"], ["preflight", "--card", "nonexistent.json"], ["plan", "nope"], ["preflight", "--json", "x.json"]):
        r = q(*a); assert r.returncode == 2, (a, r.returncode, r.stdout, r.stderr)
        assert "Traceback" not in r.stderr


def test_plan_user_names():
    for name, head in (("FP16", "## VC-025"), ("fine-tune v2", "## FT2-FP16"), ("ft1", "## FT-FP16"), ("black-frame", "## PC-B"), ("VC-025", "## VC-025")):
        r = q("plan", name); assert r.returncode == 0 and head in r.stdout, (name, r.stderr)


def test_ask_without_key_is_friendly():
    r = q("ask", "is FP16 approved?")
    assert r.returncode == 1 and "NEBIUS_API_KEY" in r.stderr and "Traceback" not in r.stderr


def test_example_card_and_broken_cards(tmp_path):
    r = q("preflight", "--card", "examples/candidate/candidate.json")
    assert r.returncode == 3 and "preflight: HOLD" in r.stdout          # INSUFFICIENT_EVIDENCE holds
    d = tmp_path / "c"; shutil.copytree(ROOT / "examples/candidate", d); card = json.load(open(d / "candidate.json"))
    def run(c):
        json.dump(c, open(d / "candidate.json", "w")); return q("preflight", "--card", str(d / "candidate.json")).returncode
    assert run({**card, "verdict": "GO"}) == 0
    assert run({**card, "latency_ms": 264}) == 4                         # misses the 200 ms chunk deadline
    assert run({**card, "engine_sha256": "0" * 64}) == 4                 # engine is not the audited build
    assert run({k: v for k, v in card.items() if k != "latency_ms"}) == 2  # missing field
    (d / "norm_manifest.json").unlink(); assert run(card) == 4           # runner refuses without a manifest


def test_dashboard_links_known_files_only():
    sys.path.insert(0, str(ROOT / "scripts")); import dash_links as L
    doc = "<p>see artifacts/freeze/fp16_post.json and artifacts/nope.json</p><script>x='artifacts/freeze/fp16_post.json'</script>"
    out = L.link_html(doc)
    assert out.count('class="gh"') == 1 and "/blob/" in out and "nope.json</p>" in out and "x='artifacts" in out
    assert L.link_html(out) == out
