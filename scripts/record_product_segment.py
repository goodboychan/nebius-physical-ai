"""Product segment for video v10 (scene 8): the dashboard at 2x, highlights timed to the narration sentences. Usage: CHROME=<chromium> python record_product_segment.py <frames dir> <seconds>"""
import asyncio, os, sys
from playwright.async_api import async_playwright
OUT, FPS, DUR = sys.argv[1], 15, float(sys.argv[2])
HL = """window.hl=(sel,txt,on=true)=>{for(const e of document.querySelectorAll(sel)){if(txt&&!e.textContent.includes(txt))continue;
  e.style.transition='background .3s, box-shadow .3s'; e.style.background=on?'rgba(255,205,0,.30)':''; e.style.boxShadow=on?'0 0 0 3px #d9a400':''; e.style.borderRadius='4px'; if(txt) return e;}};
window.yof=(sel,txt)=>{for(const e of document.querySelectorAll(sel)){if(txt&&!e.textContent.includes(txt))continue; return e.getBoundingClientRect().top+scrollY;}return scrollY};"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
        pg = await (await b.new_context(viewport={"width": 960, "height": 540}, device_scale_factor=2, color_scheme="light")).new_page()
        await pg.goto("file:///home/chanseok/workspace/neubius/dashboard/audit_gate.html"); await pg.wait_for_timeout(1200); await pg.evaluate(HL)
        y0 = await pg.evaluate("yof('#nexttest')") - 10; await pg.evaluate(f"scrollTo(0,{y0})")
        btn = (await pg.query_selector_all("#nt-pick button"))[0]
        # (time, js) events and (t0, dur, target-y js) scrolls, relative to the scene start
        ev = [(2.8, "document.querySelector('#nt-pick button').click()"), (2.9, "hl('#nt-pick button','VC-025')"),
              (5.0, "hl('#nt-pick button','VC-025',false); hl('#nt-body li','cheapest engine'); hl('#nt-body li','real arm 19/20')"),
              (8.8, "hl('#nt-body li','cheapest engine',false); hl('#nt-body li','real arm 19/20',false); hl('#nt-body p','approval on hold'); hl('#nt-body li','INSUFFICIENT_EVIDENCE')"),
              (10.6, "hl('#preflight tr','as measured')"),
              (14.1, "hl('#nt-body p','approval on hold',false); hl('#nt-body li','INSUFFICIENT_EVIDENCE',false); hl('#preflight tr','as measured',false); hl('#nt-body li','compare:'); hl('#nt-body li','rule:'); hl('#nt-body li','trials per arm')"),
              (18.1, "hl('#nt-body li','compare:',false); hl('#nt-body li','rule:',false); hl('#nt-body li','trials per arm',false); hl('#preflight tr','engine replaced after the audit')")]
        sc = [(4.8, 1.0, "yof('#nt-body h3','Confirmed')-110"), (8.3, 0.8, "yof('#nt-body p','approval on hold')-90"),
              (10.3, 0.3, "yof('#preflight tr','as measured')-150"), (13.8, 0.3, "yof('#nt-body li','compare:')-130"),
              (17.8, 0.3, "yof('#preflight tr','engine replaced after the audit')-170")]
        n = int(DUR * FPS); done = set(); cur = None; fin = set()
        for i in range(n):
            t = i / FPS
            for k, (te, js) in enumerate(ev):
                if k not in done and t >= te: await pg.evaluate(js); done.add(k)
            for (ts, d, tgt) in sc:
                if ts <= t and ts not in fin:
                    if cur is None or cur[0] != ts: cur = (ts, await pg.evaluate("scrollY"), await pg.evaluate(tgt))
                    u = min(1, (t - ts) / d); e = u * u * (3 - 2 * u); await pg.evaluate(f"scrollTo(0,{cur[1] + (cur[2] - cur[1]) * e})")
                    if u >= 1: fin.add(ts)
            await pg.screenshot(path=f"{OUT}/f{i:04d}.png")
        await b.close(); print("frames", n)
asyncio.run(main())
