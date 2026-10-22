"""Dashboard section "Review" (top of the page since 2026-10-23, board review): pick a candidate -> what to validate first,
the deployment decision and why, three key numbers, the next step with the plan to view or copy, and the evidence behind it.
Injected between <!--NEXTTEST:BEGIN--> and <!--NEXTTEST:END-->. The plans (confirmed, open, evidence, next test) come from
artifacts/reports/next_test_plans.json, written by code; the decision text and key numbers below restate committed results
(sources in each card's evidence list) and change only with them.
Usage: python scripts/build_dashboard_nexttest.py [dashboard/audit_gate.html]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import next_test_plan as ntp
page = sys.argv[1] if len(sys.argv) > 1 else "dashboard/audit_gate.html"
P = json.load(open("artifacts/reports/next_test_plans.json"))
CLIP = {"FT-FP16": "clips/t1_old_vs_ft.mp4"}
# names first, ids second; the decision layer (deployment) is separate from the evidence finding
CARD = {
    "VC-025": {"name": "FP16", "role": "original policy", "priority": "Recommended to validate first", "decision": "HOLD",
               "finding": "INSUFFICIENT_EVIDENCE",
               "why": "<b>Success evidence is insufficient.</b> The comparison with FP32 does not establish the 10 pp tolerance, and both arms "
                      "reached at least 95%, so the current ceiling rule also keeps the result undecided.",
               "tiles": [("GPU compute", "11.6", "ms", "median per 100-step action chunk"), ("Inference energy", "82", "mJ", "above idle, per chunk"),
                         ("Real-arm successes", "19", "/ 20", "FP32: 10 / 10 · nominal session")],
               "next": "Pre-register a revised success rule.", "next_sub": "Plan a new FP16–FP32 comparison before collecting more trials."},
    "FT-FP16": {"name": "Fine-tune v1", "role": "start positions", "priority": "Candidate where the start varies (−6 to +3 cm, cola can)", "decision": "HOLD",
                "finding": "IMPROVEMENT_DETECTED off the mark · INSUFFICIENT_EVIDENCE at the mark",
                "why": "<b>An improvement is not an approval.</b> Off the training mark the fine-tune beat the old policy (+3 cm 12/12 vs 3/12, "
                       "−3 cm 10/12 vs 2/12, −6 cm 8/12 vs 0/12), but at the training mark it is still undecided (22/24 vs 23/24).",
                "tiles": [("At +3 cm", "12", "/ 12", "old policy 3 / 12"), ("At −6 cm", "8", "/ 12", "old policy 0 / 12"), ("At the training mark", "22", "/ 24", "old policy 23 / 24")],
                "next": "Settle the training mark against the old policy.", "next_sub": "A larger sealed block at the mark. The +6 cm and yellow-can gaps were completed by fine-tune v2."},
    "FT2-FP16": {"name": "Fine-tune v2", "role": "yellow can and far starts", "priority": "Candidate for the yellow can and starts to +6 cm", "decision": "HOLD",
                 "finding": "IMPROVEMENT_DETECTED against fine-tune v1",
                 "why": "<b>Fixed in one sealed session, not yet compared with the old policy.</b> Against fine-tune v1 it improved with the yellow can "
                        "and at +6 cm, and a 12-trial guard found no drop at the training mark.",
                 "tiles": [("Yellow can, +3 cm", "12", "/ 12", "fine-tune v1: 7 / 12"), ("Start +6 cm", "12", "/ 12", "fine-tune v1: 2 / 12"), ("Training mark (guard)", "12", "/ 12", "fine-tune v1: 12 / 12")],
                 "next": "Settle fine-tune v2 at the training mark.", "next_sub": "Compare with the old FP16 policy under the revised rule, then more objects and positions."},
    "INT8": {"name": "INT8", "role": "24 calibrations", "priority": "Not first on this device", "tone": "muted", "decision": "HOLD",
             "finding": "INSUFFICIENT_EVIDENCE for every cell",
             "why": "<b>Slower and costlier than FP16 here, and not separated on the arm.</b> Every INT8 cell is undecided against FP32, and the "
                    "offline audit's top picks did no better than random picks (73/75 vs 73/75).",
             "tiles": [("GPU compute", "16.8–17.1", "ms", "3 benched builds, per chunk"), ("Inference energy", "101", "mJ", "above idle, per chunk"),
                       ("Real-arm successes", "194", "/ 200", "10 cells, G6 nominal tests")],
             "next": "Only if memory or power forces INT8.", "next_sub": "Then compare one build with FP16 against FP32 under the revised rule."},
    "PC-B": {"name": "Black-frame calibration", "role": "control", "priority": "Rejected", "tone": "halt", "decision": "BLOCK",
             "finding": "FLAGGED offline",
             "why": "<b>A deliberately broken calibration.</b> The calibration-input check flags it and the preflight blocks it. On the arm it went "
                    "11/12 against FP32 10/12 in 12 trials, so the offline warning was not confirmed there (unresolved).",
             "tiles": [("Input check", "FLAGGED", "", "calibration frames are black"), ("Preflight", "BLOCK", "", "before it reaches the arm"),
                       ("Real arm", "11", "/ 12", "FP32: 10 / 12")],
             "next": "Keep blocking it at the calibration-input check.", "next_sub": "No real-arm test is planned for this build."},
}
assert set(CARD) == set(P), (set(CARD), set(P))
def evname(x):   # a readable name first, the path second
    for key, name in (("_analysis.json", "Analysis"), ("_post.json", "Committed evidence record (post-lock hash)"), ("_unsealed/", "Trial log"),
                      ("modes.json", "Failure-mode labels (blind)"), ("rejudge", "Blind video re-judge"), ("lock3.json", "Order lock record (LOCK-3)"),
                      ("SUMMARY.md", "Jetson cost benchmark"), ("prereg", "Pre-registration"), ("simple_checks", "Simple-checks comparison"),
                      ("ft_chatter", "Gripper chatter measurement"), ("T0R_modes", "Failure-mode labels (blind)")):
        if key in x: return name
    return "Note"
data = {k: {**v, "md": ntp.md({k: v}), "clip": CLIP.get(k), "card": CARD[k], "evn": [evname(x) for x in v["evidence"]]} for k, v in P.items()}
ORDER = ["VC-025", "FT-FP16", "FT2-FP16", "INT8", "PC-B"]
sec = '''<!--NEXTTEST:BEGIN-->
  <section class="panel" id="nexttest">
    <div class="plate"><h2>Review: what to validate, whether it can deploy, what to test next</h2><span class="ref">written by code from committed evidence · measured snapshot 2026-10-22</span></div>
    <div id="nt-pick" class="rv-pick" role="tablist" aria-label="Candidate"></div>
    <div id="nt-card" class="rv-card"></div>
    <div id="nt-body" hidden></div>
  </section>
  <script>
  (function(){
    const D = ''' + json.dumps(data) + ''', ORDER = ''' + json.dumps(ORDER) + ''';
    const pick = document.getElementById("nt-pick"), card = document.getElementById("nt-card"), body = document.getElementById("nt-body");
    const esc = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
    const li = xs => "<ul>" + xs.map(x => "<li>" + esc(x) + "</li>").join("") + "</ul>";
    function show(k){
      const p = D[k], c = p.card, nt = p.next_test;
      [...pick.children].forEach(b => { const on = b.dataset.k === k; b.classList.toggle("on", on); b.setAttribute("aria-selected", on); });
      const tiles = c.tiles.map(([l, v, u, s]) => "<div class='rv-tile'><span class='rv-tl'>" + esc(l) + "</span><span class='rv-tv'>" + esc(v) + (u ? " <small>" + esc(u) + "</small>" : "") + "</span><span class='rv-ts'>" + esc(s) + "</span></div>").join("");
      const tpa = Object.entries(nt.trials_per_arm).filter(([a]) => !/power at|block size/.test(a));
      const est = tpa.length ? "<div class='rv-est'><span class='rv-tl'>Planning estimate</span><span class='rv-tv'>" + esc(tpa[0][1]) + " <small>trials per arm</small></span>" +
          "<span class='rv-ts'>80% power on the success criterion, " + esc(tpa[0][0]) + ". A planning estimate, not a guarantee and not the chance of a final GO.</span></div>" : "";
      const done = (p.completed || []).length ? "<p class='rv-done'><b>Completed since this plan was made:</b> " + p.completed.map(esc).join("; ") + "</p>" : "";
      card.innerHTML =
        "<div class='rv-top'><div><span class='rv-tl'>Selected candidate</span><div class='rv-name'>" + esc(c.name) + " <small>" + esc(k) + "</small></div>" +
        "<span class='rv-prio " + (c.tone || "") + "'>" + esc(c.priority) + "</span></div><div class='rv-dec'><span class='rv-tl'>Deployment decision</span><span class='rv-badge " + c.decision.toLowerCase() + "'>" + c.decision + "</span>" +
        "<span class='rv-ts'>evidence finding: " + esc(c.finding) + "</span></div></div>" +
        "<div class='rv-why'><span class='rv-tl'>Why " + c.decision + "</span><p>" + c.why + "</p></div>" +
        "<div class='rv-tiles'>" + tiles + "</div>" +
        "<div class='rv-next'><div><span class='rv-tl'>Next step</span><b>" + esc(c.next) + "</b><span class='rv-ts'>" + esc(c.next_sub) + "</span></div>" +
        "<div class='rv-btns'><button id='nt-view' class='rv-btn'>View next-test plan ↓</button><button id='nt-copy' class='rv-btn ghost'>Copy test plan</button></div></div>" +
        "<div id='nt-plan' class='rv-plan' hidden><div class='rv-plan-h'><b>Proposed next test</b><span class='rv-status'>planned · not yet pre-registered</span></div>" +
        "<div class='rv-grid'><div><span class='rv-tl'>Comparison</span><p>" + esc(nt.compare) + " · " + esc(nt.conditions) + "</p></div>" + est +
        "<div><span class='rv-tl'>Before collecting data</span><p>" + esc(nt.rule) + "</p></div><div><span class='rv-tl'>Measure · schedule</span><p>" + esc(nt.measure) + " · " + esc(nt.schedule) + "</p></div></div>" + done +
        (p.clip ? "<video src='" + p.clip + "' controls muted playsinline preload='metadata' style='max-width:100%;border-radius:8px'></video>" : "") + "</div>" +
        "<details class='rv-ev'><summary>Evidence and provenance</summary><div class='rv-grid'><div><span class='rv-tl'>Confirmed</span>" + li(p.confirmed) + "</div><div><span class='rv-tl'>Still open</span>" + li(p.open) + "</div></div>" +
        "<span class='rv-tl'>Records</span><ul class='rv-files'>" + p.evidence.map((x, i) => "<li><b>" + esc(p.evn[i]) + "</b> <code>" + esc(x) + "</code></li>").join("") + "</ul></details>" +
        "<p class='rv-scope'>Scope: this recorded policy, device and test configuration. Validation priority is separate from deployment approval.</p>" +
        "<textarea id='nt-md' readonly hidden style='width:100%;height:200px;margin-top:8px'>" + esc(p.md) + "</textarea>";
      body.textContent = p.md;
      document.getElementById("nt-view").onclick = e => { const pl = document.getElementById("nt-plan"); pl.hidden = !pl.hidden; e.target.textContent = pl.hidden ? "View next-test plan ↓" : "Hide next-test plan ↑"; };
      document.getElementById("nt-copy").onclick = () => {
        const ta = document.getElementById("nt-md");
        const done_ = () => { document.getElementById("nt-copy").textContent = "Copied"; };
        try { navigator.clipboard.writeText(p.md).then(done_).catch(() => { ta.hidden = false; ta.select(); }); } catch (e) { ta.hidden = false; ta.select(); }
      };
    }
    ORDER.forEach(k => { const c = D[k].card, b = document.createElement("button"); b.dataset.k = k; b.setAttribute("role", "tab");
      b.innerHTML = "<b>" + esc(c.name) + "</b> <small>" + esc(c.role) + "</small>"; b.onclick = () => show(k); pick.appendChild(b); });
    show("VC-025");
  })();
  </script>
<!--NEXTTEST:END-->
'''
s = open(page).read()
if "<!--NEXTTEST:BEGIN-->" in s:
    s = s[:s.index("<!--NEXTTEST:BEGIN-->")] + sec.lstrip() + s[s.index("<!--NEXTTEST:END-->") + len("<!--NEXTTEST:END-->\n"):]
else:
    anchor = '  <section class="panel" id="review">'; assert anchor in s; s = s.replace(anchor, sec + anchor, 1)
open(page, "w").write(s); print("review section written:", ORDER)
