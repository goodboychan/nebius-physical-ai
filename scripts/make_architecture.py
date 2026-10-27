"""The architecture diagram: what runs where, and what moves between the systems (2026-10-27, presentation only).
One SVG serves three places:
  - inline in the dashboard, where the colours come from the page's theme tokens (light and dark);
  - docs/assets/architecture.svg, the same drawing with the light colours as fallbacks;
  - docs/assets/architecture.png, rendered from it (with --png; needs the playwright package and its Chromium).
The process view (the eleven steps) is the dashboard's workflow panel; this is the system view.
Usage: python scripts/make_architecture.py [--png]"""
import html, os, sys

W, H = 1280, 770
C = {"ink": "#14181C", "ink-2": "#3C464E", "ink-3": "#5A646C", "paper": "#F1F3F2", "plate": "#FAFBFA", "rule": "#D3D9D7",
     "signal": "#00909B", "ember": "#A8430F", "plum": "#6B4C9A"}
v = lambda k: f"var(--{k}, {C[k]})"
out = []
esc = lambda t: html.escape(t, quote=False)


def zone(x, y, w, h, title, sub, kind):
    out.append(f'<rect class="zone {kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="10"/>')
    out.append(f'<text class="zt" x="{x + 14}" y="{y + 24}">{esc(title)}</text><text class="zs" x="{x + 14}" y="{y + 41}">{esc(sub)}</text>')


def box(x, y, w, h, title, lines=(), kind="code"):
    out.append(f'<rect class="box {kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="6"/>')
    out.append(f'<rect class="bar {kind}" x="{x}" y="{y}" width="4" height="{h}" rx="2"/>')
    out.append(f'<text class="bt" x="{x + 14}" y="{y + 21}">{esc(title)}</text>')
    for i, l in enumerate(lines): out.append(f'<text class="bl" x="{x + 14}" y="{y + 39 + 15 * i}">{esc(l)}</text>')


def arrow(pts, label=None, lx=None, ly=None, anchor="start", kind="flow"):
    d = "M" + " L".join(f"{a},{b}" for a, b in pts)
    out.append(f'<path class="ar {kind}" d="{d}" marker-end="url(#ah-{kind})"/>')
    if label:
        for i, l in enumerate(label.split("\n")):
            out.append(f'<text class="al" x="{lx}" y="{ly + 13 * i}" text-anchor="{anchor}">{esc(l)}</text>')


# layout: Nebius as a top band (with the workstation at its left), the bench lower left with the Jetson next to the
# repository, public outputs along the bottom. Vertical runs use their own lanes (x 612, 620, 632) so lines never cross.
zone(16, 16, 248, 176, "Workstation", "quantization (NGC container)", "work")
zone(272, 16, 992, 176, "Nebius AI Cloud", "training, audit fan-out, the AI models", "cloud")
zone(16, 216, 608, 384, "On the bench", "real arm and the edge device", "arm")
zone(664, 216, 600, 384, "Repository · code decides", "", "repo")
zone(16, 616, 1248, 132, "Public", "open data, code, review and video", "pub")

box(32, 64, 216, 112, "TensorRT Model Optimizer", ["FP32 checkpoint → ONNX:", "FP16 and 24 INT8", "calibration variants"], "code")
for k, (t, ls, kind) in enumerate((("Nebius Jobs · L40S", ["ACT 51.6M training and", "the fine-tunes, on the", "HF datasets"], "model"),
                                   ("Nebius Jobs · CPU", ["audit: 25 cells,", "2,000 held-out states,", "ranking frozen (LOCK-2)"], "code"),
                                   ("AI Endpoint", ["Cosmos-Reason2-2B judges", "each trial from frames;", "validated first"], "model"),
                                   ("Token Factory", ["Nemotron 3 Super: words", "only; code rejects any", "number or verdict"], "model"),
                                   ("Managed MLflow", ["experiment record from", "committed artifacts"], "code"))):
    box(288 + 194 * k, 64, 182, 112, t, ls, kind)

box(32, 262, 184, 60, "SO-101 leader arm", ["teleoperated demos"], "arm")
box(32, 334, 184, 60, "Cameras", ["overhead · wrist"], "arm")
box(32, 406, 184, 60, "SO-101 follower", ["driven by the policy"], "arm")
out.append('<rect class="dev" x="232" y="262" width="376" height="326" rx="8"/>')
out.append('<text class="dt" x="246" y="284">Jetson Orin Nano Super · 15 W · 30 Hz</text>')
box(246, 296, 348, 52, "TensorRT engine", ["FP32 · FP16 · 24 INT8 (26 candidates)"], "arm")
box(246, 358, 348, 52, "Trial runner", ["sealed, interleaved, operator-blind schedule"], "code")
box(246, 420, 348, 52, "Preflight", ["engine hash · norm manifest · 200 ms deadline"], "code")
box(246, 482, 348, 92, "Cost measurement", ["trtexec + tegrastats", "FP16 11.6 ms · 82 mJ per inference,", "faster than INT8 on this device"], "arm")

box(680, 262, 280, 56, "Sealed logs, post-lock hashes", ["22 logs · verify re-checks each hash"], "code")
box(680, 334, 280, 56, "Verdict table", ["Newcombe intervals, pre-registered rules"], "code")
box(680, 406, 280, 64, "Deployment decision", ["GO · HOLD · BLOCK, and the next", "test's trials per arm, by code"], "code")
box(680, 486, 280, 100, "Pre-registrations, decision log", ["rules locked before outcomes", "(LOCK-1 to LOCK-4); every", "amendment and error logged"], "code")
box(976, 262, 272, 56, "Review report", ["the report, with Nemotron's words"], "code")
box(976, 334, 272, 72, "QuantGate CLI", ["judge · tally · card · preflight", "for any team's logs; bad input exits 2"], "code")
box(976, 422, 272, 72, "GitHub Actions", ["tests; offline review rebuilt", "byte for byte; gate example"], "code")

box(32, 664, 296, 70, "Hugging Face datasets", ["3 LeRobot v3 datasets:", "120 + 50 + 50 demonstrations"], "pub")
box(344, 664, 296, 70, "GitHub repository", ["code, sealed logs, analyses,", "Apache 2.0"], "pub")
box(656, 664, 296, 70, "Dashboard", ["the review, evidence and", "audit record, in a browser"], "pub")
box(968, 664, 280, 70, "Video", ["3 min: the arm and", "the decision"], "pub")

# flows
arrow([(288, 120), (248, 120)], None, kind="data")
out.append('<text class="al" x="268" y="188" text-anchor="middle">FP32 checkpoint</text>')
arrow([(210, 176), (210, 236), (520, 236), (520, 296)], "26 engines (ONNX → TensorRT)", 300, 230, kind="data")
arrow([(594, 322), (612, 322), (612, 200), (564, 200), (564, 176)], "error vectors", 558, 214, anchor="end", kind="data")
arrow([(594, 376), (620, 376), (620, 206), (700, 206), (700, 176)], "frames", 640, 202, kind="model")
arrow([(594, 390), (632, 390), (632, 290), (680, 290)], "logs,\nvideos", 650, 270, anchor="middle", kind="data")
arrow([(858, 150), (864, 150), (864, 200), (910, 200), (910, 262)], "verdict per trial", 916, 238, kind="model")
arrow([(820, 318), (820, 334)])
arrow([(820, 390), (820, 406)])
arrow([(960, 362), (968, 362), (968, 290), (976, 290)])
arrow([(1052, 176), (1052, 262)], "words only", 1058, 238, kind="model")
arrow([(1150, 262), (1150, 176)], "record", 1156, 238, kind="flow")
arrow([(680, 446), (594, 446)], "GO only", 637, 440, anchor="middle", kind="flow")
arrow([(216, 364), (246, 384)], None)
arrow([(246, 400), (216, 436)], None)
out.append('<text class="al" x="224" y="356" text-anchor="middle">obs</text><text class="al" x="224" y="458" text-anchor="middle">act</text>')
arrow([(32, 292), (24, 292), (24, 700), (32, 700)], "demos", 28, 610, kind="data")
arrow([(1248, 290), (1256, 290), (1256, 644), (804, 644), (804, 664)], None)
arrow([(1256, 644), (492, 644), (492, 664)], None)

legend = [("arm", "real arm or device"), ("model", "an AI model"), ("code", "plain code"), ("pub", "public")]
lg = "".join(f'<rect class="bar {k}" x="{700 + 140 * i}" y="756" width="10" height="10" rx="2"/><text class="lg" x="{715 + 140 * i}" y="765">{t}</text>'
             for i, (k, t) in enumerate(legend))

style = f"""
.zone{{fill:none;stroke:{v('rule')};stroke-width:1.2}} .zone.cloud{{stroke:{v('plum')};stroke-dasharray:5 4}} .zone.arm{{stroke:{v('ember')}}}
.zone.repo{{stroke:{v('signal')}}} .zone.pub{{stroke:{v('ink-3')};stroke-dasharray:2 4}}
.zt{{font:600 15px system-ui,sans-serif;fill:{v('ink')}}} .zs{{font:12px system-ui,sans-serif;fill:{v('ink-3')}}}
.box{{fill:{v('plate')};stroke:{v('rule')}}} .bar.arm{{fill:{v('ember')}}} .bar.model{{fill:{v('plum')}}} .bar.code{{fill:{v('signal')}}} .bar.pub{{fill:{v('ink-3')}}}
.bt{{font:600 13px system-ui,sans-serif;fill:{v('ink')}}} .bl{{font:11.5px system-ui,sans-serif;fill:{v('ink-2')}}}
.dev{{fill:none;stroke:{v('ember')};stroke-width:1.4}} .dt{{font:600 12.5px system-ui,sans-serif;fill:{v('ember')}}}
.ar{{fill:none;stroke:{v('ink-3')};stroke-width:1.4}} .ar.data{{stroke:{v('signal')}}} .ar.model{{stroke:{v('plum')}}}
.al{{font:italic 11px system-ui,sans-serif;fill:{v('ink-2')}}} .lg{{font:11px system-ui,sans-serif;fill:{v('ink-3')}}}
"""
defs = "".join(f'<marker id="ah-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
               f'<path d="M0,0 L10,5 L0,10 z" fill="{v(c)}"/></marker>' for k, c in (("flow", "ink-3"), ("data", "signal"), ("model", "plum")))
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H + 8}" role="img" aria-labelledby="arch-t arch-d" class="arch">'
       f'<title id="arch-t">QuantGate architecture</title><desc id="arch-d">The bench (SO-101 arms, cameras, a Jetson Orin Nano Super running the '
       f'TensorRT engine, trial runner and preflight), Nebius AI Cloud (training and fine-tunes on L40S, the CPU audit fan-out, Cosmos-Reason2 as '
       f'the trial judge, Nemotron 3 Super for words only, MLflow), the workstation that quantizes the checkpoint, and the repository where code '
       f'turns sealed logs into verdicts, decisions and next tests; datasets, code, dashboard and video are public.</desc>'
       f'<style>{style}</style><defs>{defs}</defs>' + "".join(out) + lg + "</svg>")

if __name__ == "__main__":
    os.makedirs("docs/assets", exist_ok=True)
    page_bg = f'<rect x="0" y="0" width="{W}" height="{H + 8}" fill="{C["paper"]}"/>'
    open("docs/assets/architecture.svg", "w").write(svg.replace("<defs>", page_bg + "<defs>", 1) + "\n")
    print("written docs/assets/architecture.svg")
    p = "dashboard/audit_gate.html"; s = open(p).read()
    if "<!--ARCH:BEGIN-->" in s:
        i, j = s.index("<!--ARCH:BEGIN-->"), s.index("<!--ARCH:END-->") + len("<!--ARCH:END-->")
        s = s[:i] + "<!--ARCH:BEGIN-->" + f'<div class="arch-wrap">{svg}</div>' + "<!--ARCH:END-->" + s[j:]
        open(p, "w").write(s); print("dashboard architecture updated")
    if "--png" in sys.argv:   # needs the playwright package and its Chromium (CHROME overrides the browser path)
        from playwright.sync_api import sync_playwright
        chrome = os.environ.get("CHROME", os.path.expanduser("~/.cache/ms-playwright/chromium-1217/chrome-linux/chrome"))
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=chrome if os.path.exists(chrome) else None)
            pg = b.new_page(viewport={"width": W, "height": H + 8}, device_scale_factor=2)
            pg.goto("file://" + os.path.abspath("docs/assets/architecture.svg")); pg.screenshot(path="docs/assets/architecture.png"); b.close()
        print("written docs/assets/architecture.png")
