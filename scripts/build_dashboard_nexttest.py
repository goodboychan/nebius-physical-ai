"""Dashboard section "From evidence to the next test" (external review 7), injected between <!--NEXTTEST:BEGIN--> and
<!--NEXTTEST:END--> first, before the deployment review (moved to the top on 2026-10-18 so a reader can try it first). Data: artifacts/reports/next_test_plans.json (written by code).
Pick a candidate -> status, confirmed, open, evidence (with the counted clip where there is one) and the next test's plan,
with a Copy button for the plan as Markdown.
Usage: python scripts/build_dashboard_nexttest.py [dashboard/audit_gate.html]"""
import html, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import next_test_plan as ntp
page = sys.argv[1] if len(sys.argv) > 1 else "dashboard/audit_gate.html"
P = json.load(open("artifacts/reports/next_test_plans.json"))
CLIP = {"FT-FP16": "clips/t1_old_vs_ft.mp4"}
data = {k: {**v, "md": ntp.md({k: v}), "clip": CLIP.get(k)} for k, v in P.items()}
sec = '''<!--NEXTTEST:BEGIN-->
  <section class="panel" id="nexttest">
    <div class="plate"><h2>Try it: from evidence to the next test</h2><span class="ref">scripts/next_test_plan.py · written by code</span></div>
    <p class="note"><b>No robot needed, about 30 seconds.</b> Pick a candidate: what is confirmed, what is still open, the evidence behind both, and the plan for the next test,
      with trials per arm from a simulated power calculation under the same Newcombe rule. Copy the plan to pre-register it.</p>
    <div id="nt-pick" style="display:flex;gap:8px;flex-wrap:wrap"></div>
    <div id="nt-body"></div>
  </section>
  <script>
  (function(){
    const D = ''' + json.dumps(data) + ''';
    const pick = document.getElementById("nt-pick"), body = document.getElementById("nt-body");
    const esc = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
    const list = (t, xs) => "<h3 style='margin:14px 0 6px;font-size:14px'>" + t + "</h3><ul>" + xs.map(x => "<li>" + esc(x) + "</li>").join("") + "</ul>";
    function show(k){
      const p = D[k]; [...pick.children].forEach(b => b.style.outline = b.dataset.k === k ? "2px solid var(--acc, #12a0a8)" : "none");
      const nt = p.next_test, tpa = Object.entries(nt.trials_per_arm).map(([a, v]) => (/power at|block size/.test(a) ? a : "trials per arm for 80% power on the success criterion (not the chance of a final GO), " + a) + ": " + v);
      body.innerHTML = "<p><b>" + esc(p.candidate) + "</b> · " + esc(p.status) + "</p>" + list("Confirmed", p.confirmed) + list("Open", p.open) +
        list("Evidence", p.evidence) + (p.clip ? "<video src='" + p.clip + "' controls muted playsinline preload='metadata' style='max-width:100%;border-radius:8px'></video>" : "") +
        list("Next test", ["compare: " + nt.compare, "conditions: " + nt.conditions, "measure: " + nt.measure, "schedule: " + nt.schedule, "rule: " + nt.rule].concat(tpa)) +
        "<button id='nt-copy' style='margin-top:8px;padding:6px 12px;border-radius:8px;border:1px solid var(--rule,#999);background:transparent;color:inherit;cursor:pointer'>Copy plan as Markdown</button>" +
        "<textarea id='nt-md' readonly style='display:none;width:100%;height:220px;margin-top:8px'>" + esc(p.md) + "</textarea>";
      document.getElementById("nt-copy").onclick = () => {
        const ta = document.getElementById("nt-md");
        navigator.clipboard.writeText(p.md).then(() => { document.getElementById("nt-copy").textContent = "Copied"; })
          .catch(() => { ta.style.display = "block"; ta.select(); });
      };
    }
    Object.keys(D).forEach(k => { const b = document.createElement("button"); b.dataset.k = k; b.textContent = k;
      b.style.cssText = "padding:6px 12px;border-radius:999px;border:1px solid var(--rule,#999);background:transparent;color:inherit;cursor:pointer;font:inherit";
      b.onclick = () => show(k); pick.appendChild(b); });
    show("FT-FP16");
  })();
  </script>
<!--NEXTTEST:END-->
'''
s = open(page).read()
if "<!--NEXTTEST:BEGIN-->" in s:
    s = s[:s.index("<!--NEXTTEST:BEGIN-->")] + sec.lstrip() + s[s.index("<!--NEXTTEST:END-->") + len("<!--NEXTTEST:END-->\n"):]
else:
    anchor = '  <section class="panel" id="review">'; assert anchor in s; s = s.replace(anchor, sec + anchor, 1)
open(page, "w").write(s); print("next-test section written:", list(P))
