"""Product segment for video v12 (scene 8) on the Review panel: 2x, highlights timed to the narration v9 sentences. Usage: CHROME=<chromium> python record_product_segment.py <frames dir> <seconds>"""
import asyncio, os, sys
from playwright.async_api import async_playwright
OUT, FPS, DUR = sys.argv[1], 15, float(sys.argv[2])
HL = """window.hl=(sel,txt,on=true)=>{for(const e of document.querySelectorAll(sel)){if(txt&&!e.textContent.includes(txt))continue;
  e.style.transition='background .3s, box-shadow .3s'; e.style.background=on?'rgba(255,205,0,.30)':''; e.style.boxShadow=on?'0 0 0 3px #d9a400':''; e.style.borderRadius='6px'; if(txt) return e;}};
window.yof=(sel,txt)=>{for(const e of document.querySelectorAll(sel)){if(txt&&!e.textContent.includes(txt))continue; return e.getBoundingClientRect().top+scrollY;}return scrollY};
window.pk=(t)=>{for(const b of document.querySelectorAll('#nt-pick button')) if(b.textContent.includes(t)) b.click()};"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
        pg = await (await b.new_context(viewport={"width": 960, "height": 540}, device_scale_factor=2, color_scheme="light")).new_page()
        await pg.goto("file:///home/chanseok/workspace/neubius/dashboard/audit_gate.html"); await pg.wait_for_timeout(1200); await pg.evaluate(HL)
        await pg.evaluate("pk('Fine-tune v2')"); await pg.wait_for_timeout(200)
        y0 = await pg.evaluate("yof('#nexttest')") - 8; await pg.evaluate(f"scrollTo(0,{y0})")
        ev = [(2.76, "pk('original policy')"), (2.86, "hl('#nt-pick button','original policy')"),
              (4.9, "hl('#nt-pick button','original policy',false); hl('.rv-tiles',null)"),
              (8.6, "hl('.rv-tiles',null,false); hl('.rv-dec',null); hl('.rv-why',null)"),
              (13.85, "hl('.rv-dec',null,false); hl('.rv-why',null,false); document.getElementById('nt-view').click()"),
              (14.2, "hl('#nt-plan .rv-grid > div','Comparison'); hl('.rv-est',null)"),
              (17.0, "hl('#nt-copy',null)"), (17.4, "try{document.getElementById('nt-copy').click()}catch(e){}"),
              (19.1, "hl('#nt-plan .rv-grid > div','Comparison',false); hl('.rv-est',null,false); hl('#nt-copy',null,false); hl('#preflight tr','engine replaced after the audit')")]
        sc = [(4.6, 0.8, "yof('.rv-tiles')-150"), (8.2, 0.6, "yof('.rv-top')-40"), (14.0, 0.8, "yof('#nt-plan')-60"),
              (18.8, 0.3, "yof('#preflight tr','engine replaced after the audit')-170")]
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
