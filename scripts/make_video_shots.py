"""Capture dashboard sections as PNGs for scripts/make_video.py and make_deck.py (Playwright + the local headless shell).
Usage: <venv with playwright> python scripts/make_video_shots.py <headless_shell path> <out dir>"""
import sys
from playwright.sync_api import sync_playwright

exe, out = sys.argv[1:3]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1.5)
    pg.goto("file://" + __import__("os").path.abspath("dashboard/audit_gate.html")); pg.wait_for_timeout(2000)
    sec = lambda t: pg.locator("section.panel", has=pg.locator(".plate h2", has_text=t)).first
    shots = {"review_decisions": pg.locator("#review .decisions"), "review_compare": pg.locator("#review .tbl-scroll").first,
             "review_rows": pg.locator("#review .rows"), "preflight": sec("Deployment preflight"), "cost": sec("Engine cost on the deployment target"),
             "success": sec("Closed-loop success by cell"), "moved": sec("What moved the success rate"), "contrasts": sec("Pre-registered contrasts"),
             "report_meta": pg.locator("#report"), "pos_strip": pg.locator("#setup .pos"), "agents": sec("Agent layer")}
    for k, l in shots.items():
        l.scroll_into_view_if_needed(); pg.wait_for_timeout(300); l.screenshot(path=f"{out}/{k}.png")
    b.close()
