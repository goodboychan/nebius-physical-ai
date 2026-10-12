# `D7` audit board

Published at https://claude.ai/artifact/2tUAoJHBeT8uLU96BmgPNK (version 2, 2026-10-12, after LOCK-3).

`audit_gate.html` is a single page with no build step and no external scripts. Charts are inline SVG drawn from
numbers embedded in the page. Every embedded per-cell number was checked against
`artifacts/reports/g6_analysis.json` before publishing (cell counts, Wilson intervals, placement means).

| Panel | Source |
|---|---|
| Order locks | `artifacts/freeze/*.json`, `docs/decision_log.md` |
| Per-cell success, contrasts | `artifacts/reports/g6_analysis.json` |
| Offline rank vs placement | `g6_analysis.json` EX-4, `artifacts/freeze/lock2.json` rankings |
| Engine cost | `artifacts/reports/power_bench/SUMMARY.md` |
| What moved the success rate | G6 + public stress tallies (`docs/sessions/stress_operator_notes.md`) |
| Agent layer | `g6_supplement.json` EX-3, `d4_retro_judge_g6.json`, `d3_final_report.md` |

Stress v2 and FP16 per-cell results are sealed and are not on the board until they are unsealed.

Design: the calibration-certificate identity of version 1 is kept: IBM Plex families, the same tokens, and plates
ordered by real dependency.

## Trial footage (version 3)

`dashboard/clips/*.mp4` are full 60 s overhead trial videos, re-encoded from AV1 to H.264 by
`scripts/make_dashboard_clips.py` with no edits or speed change. They are published as supporting files next to the
page, not through the `assets` capability, because a page that declares `assets` cannot be shared publicly. The clips
name trial numbers only, never engines.
