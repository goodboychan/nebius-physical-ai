"""The full deployment review as one self-contained HTML file, with no robot, no GPU and no API key (external review 7):
  1. sections 1-4 written by code from the verdict table (d3_report_v3.code_sections);
  2. "From evidence to the next test" (scripts/next_test_plan.py);
  3. the figures (committed PNGs, drawn by scripts/d3_figures.py; `pip install -e .[report]` to redraw them);
  4. Nemotron's explanation (sections 5-6), only if d3_report_v3_run.json was generated for this same verdict table
     (hash match); otherwise it is left out and the page says so.
Usage: python scripts/build_review_html.py [--out artifacts/reports/review_report.html]"""
import argparse, base64, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, "src")
from edgeqgate.hashing import hash_obj
from d3_report_v3 import code_sections
R = "artifacts/reports"

def inline(t):
    t = html.escape(t, quote=False); t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t); t = re.sub(r"(?<!\*)\*(?!\s)(.+?)\*(?!\*)", r"<i>\1</i>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)

def md2html(md):
    out, lst = [], False
    for line in md.splitlines():
        l = line.rstrip()
        if lst and not l.startswith("- "): out.append("</ul>"); lst = False
        if not l.strip(): continue
        if l.startswith("# "): out.append(f"<h2>{inline(l[2:])}</h2>"); continue
        if l.startswith("## "): out.append(f"<h3>{inline(l[3:])}</h3>"); continue
        if l.startswith("- "):
            if not lst: out.append("<ul>"); lst = True
            out.append(f"<li>{inline(l[2:])}</li>"); continue
        out.append(f"<p>{inline(l)}</p>")
    if lst: out.append("</ul>")
    return "\n".join(out)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=f"{R}/review_report.html"); a = ap.parse_args()
    T = json.load(open(f"{R}/d3_v3_verdicts.json")); h = hash_obj(T)
    parts = [md2html(code_sections(T))]
    plans = f"{R}/next_test_plans.md"
    parts.append(md2html(open(plans).read()) if os.path.exists(plans) else "<p><i>Run scripts/next_test_plan.py for the next-test plans.</i></p>")
    run = json.load(open(f"{R}/d3_report_v3_run.json")) if os.path.exists(f"{R}/d3_report_v3_run.json") else {}
    if run.get("verdict_hash") == h and os.path.exists(f"{R}/d3_report_v3.md"):
        md = open(f"{R}/d3_report_v3.md").read(); m = re.search(r"\n(## 5\..*?)(?=\n## Figures)", md, re.S)
        if m: parts.append("<h2>Explanation (Nemotron 3 Super on Nebius Token Factory; words only, checked by code)</h2>" + md2html(m.group(1)))
    else:
        parts.append("<p class=note>The Nemotron explanation is left out: it was generated for a different verdict table, or not at all. "
                     "Run <code>quantgate.py review</code> with <code>NEBIUS_API_KEY</code> to add it.</p>")
    figs = []
    for f in ("fig_ft_position.png", "fig_e1_forest.png", "fig_cost_evidence.png", "fig_frames.png"):
        p = f"{R}/figures/{f}"
        if os.path.exists(p): figs.append(f'<figure><img alt="{f}" src="data:image/png;base64,{base64.b64encode(open(p, "rb").read()).decode()}"><figcaption>{f}</figcaption></figure>')
    css = """:root{--bg:#f7f8f8;--fg:#16191c;--mut:#5d666e;--card:#fff;--line:#dfe3e6;--acc:#00808c}
@media (prefers-color-scheme:dark){:root{--bg:#121516;--fg:#e6eaea;--mut:#9aa4aa;--card:#1a1f20;--line:#2c3436;--acc:#5fc7cf}}
body{background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,sans-serif;margin:0;padding:24px 16px}main{max-width:980px;margin:auto}
h1{font-size:26px}h2{font-size:20px;margin-top:32px;border-bottom:1px solid var(--line);padding-bottom:6px}h3{font-size:16px;color:var(--acc)}
code{font:13px ui-monospace,monospace;background:var(--card);border:1px solid var(--line);border-radius:4px;padding:0 4px}
li{margin:4px 0}.note{color:var(--mut)}figure{margin:16px 0;background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px}
img{max-width:100%;height:auto;display:block}figcaption{color:#5d666e;font-size:12px}"""
    page = (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>QuantGate review</title><style>{css}</style><main>"
            f"<h1>QuantGate — deployment review</h1><p class=note>Built by <code>scripts/build_review_html.py</code> from the verdict table "
            f"(hash <code>{h[:16]}</code>). Every verdict and number is written by code; no robot, GPU or API key is needed to rebuild this page.</p>"
            + "\n".join(parts) + "<h2>Figures (drawn by code)</h2>" + "\n".join(figs) + "</main>")
    open(a.out, "w").write(page); print("written", a.out, round(len(page) / 1e6, 2), "MB")
