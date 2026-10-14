# QuantGate — deployment report v3 (auto-generated)

> Sections 1–4 are written by code from the verdict table (`d3_v3_verdicts.json`, hash `f9797c7025fbc880`). Sections 5–6 are written by Nemotron 3 Super (Token Factory) and checked by code: no digits, no verdict labels, no approval or safety words. They are never a source of verdicts or numbers; a qualitative misreading in plain words cannot be excluded by these rules. v2 is kept as history (`d3_report_v2.md`).

| Item | Value |
|---|---|
| Model attempts | 1 |
| Latency | 12.1 s |
| **Wording findings (final attempt)** | **0** |

---

## 1. Recommendation (written by code)

FP16 is the recommended precision to validate first (cheapest on the device). The position fine-tune (FT-FP16, same FP16 engine cost) fixed the start-position weakness at both held-out shifts (IMPROVEMENT_DETECTED at +3 cm and -3 cm), so FT-FP16 is the candidate to validate next where start positions vary. Approval is a separate status: on hold, because every comparison against full precision is INSUFFICIENT_EVIDENCE and the fine-tune's nominal performance is undecided.

## 2. Verdict per candidate (written by code)

Success intervals are Newcombe intervals for candidate minus reference, in percentage points, against a 10 pp tolerance. End-to-end latency is the runner's per-chunk time on the arm; GPU time is trtexec on the device (15 W).

- **VC-002** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 24/25 against reference 24/25 · success interval [-28.5, +28.5] pp · placement: tolerance compatible · end-to-end 34.3 ms · GPU time on device 16.8 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-002`)
- **VC-020** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 24/25 against reference 24/25 · success interval [-28.5, +28.5] pp · placement: tolerance compatible · end-to-end 34.3 ms · GPU time on device 16.8 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-020`)
- **VC-010** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 25/25 against reference 24/25 · success interval [-32.3, +23.0] pp · placement: tolerance compatible · end-to-end 34.3 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-010`)
- **VC-011** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 24/25 against reference 24/25 · success interval [-28.5, +28.5] pp · placement: tolerance compatible · end-to-end 34.6 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-011`)
- **VC-012** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 24/25 against reference 24/25 · success interval [-28.5, +28.5] pp · placement: tolerance compatible · end-to-end 34.3 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-012`)
- **VC-015** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 25/25 against reference 24/25 · success interval [-32.3, +23.0] pp · placement: indeterminate · end-to-end 34.6 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-015`)
- **VC-005** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 14/15 against reference 24/25 · success interval [-26.2, +41.7] pp · placement: tolerance compatible · end-to-end 34.5 ms · GPU time on device 17.1 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-005`)
- **VC-007** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 15/15 against reference 24/25 · success interval [-32.3, +34.0] pp · placement: tolerance compatible · end-to-end 34.6 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-007`)
- **VC-022** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 10/10 against reference 24/25 · success interval [-32.3, +43.9] pp · placement: indeterminate · end-to-end 34.3 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-022`)
- **VC-024** · G6 nominal, pads · `INSUFFICIENT_EVIDENCE` · success 9/10 against reference 24/25 · success interval [-23.7, +53.4] pp · placement: tolerance compatible · end-to-end 34.1 ms (`artifacts/reports/g6_q2_sensitivity.json#Q2.VC-024`)
- **VC-025** · FP16 run, rubber bands · `INSUFFICIENT_EVIDENCE` · success 19/20 against reference 10/10 · success interval [-28.7, +27.3] pp · placement: tolerance compatible · end-to-end 24.7 ms · GPU time on device 11.6 ms (`artifacts/reports/fp16_analysis.json#primary_fp16_vs_fp32`)
- **VC-002** · stress S4 unseen can · `INSUFFICIENT_EVIDENCE` · success 12/12 against reference 12/12 · success interval [-40.6, +40.6] pp · placement: tolerance compatible · GPU time on device 16.8 ms (`artifacts/reports/stress_v2_analysis.json#S4.secondary_vs_fp32.VC-002`)
- **VC-005** · stress S4 unseen can · `INSUFFICIENT_EVIDENCE` · success 12/12 against reference 12/12 · success interval [-40.6, +40.6] pp · placement: tolerance compatible · GPU time on device 17.1 ms (`artifacts/reports/stress_v2_analysis.json#S4.secondary_vs_fp32.VC-005`)
- **VC-020** · stress S4 unseen can · `INSUFFICIENT_EVIDENCE` · success 12/12 against reference 12/12 · success interval [-40.6, +40.6] pp · placement: tolerance compatible · GPU time on device 16.8 ms (`artifacts/reports/stress_v2_analysis.json#S4.secondary_vs_fp32.VC-020`)
- **PC-B** · positive control real arm · `INSUFFICIENT_EVIDENCE` · success 11/12 against reference 10/12 · success interval [-41.5, +25.8] pp · placement: tolerance compatible · end-to-end 34.5 ms (`artifacts/reports/positive_control_analysis.json#comparison`)
- **FT-FP16** · fine-tune vs old, start +3 cm (held out, primary) · `IMPROVEMENT_DETECTED` · success 12/12 against VC-025 (old policy) 3/12 · success interval [+37.8, +91.1] pp · GPU time on device 11.6 ms (`artifacts/reports/ft_analysis.json#T1.primary`)
- **FT-FP16** · fine-tune vs old, start -3 cm (held out, symmetry) · `IMPROVEMENT_DETECTED` · success 10/12 against VC-025 (old policy) 2/12 · success interval [+26.9, +83.6] pp · GPU time on device 11.6 ms (`artifacts/reports/ft_analysis.json#T2.primary`)
- **FT-FP16** · fine-tune vs old, training start mark (secondary) · `INSUFFICIENT_EVIDENCE` · success 10/12 against VC-025 (old policy) 12/12 · success interval [-15.4, +49.0] pp · placement: indeterminate · GPU time on device 11.6 ms (`artifacts/reports/ft_analysis.json#T0.secondary`)

## 3. Flagged builds (written by code)

- **PC-N** · offline, deliberately miscalibrated · `FLAGGED` by simple input check, action error (MSE), audit score (magnitude), audit score (alignment) (`artifacts/reports/simple_checks_vs_audit.json#cells.PC-N`)
- **PC-B** · offline, deliberately miscalibrated · `FLAGGED` by simple input check, action error (MSE), audit score (magnitude), audit score (alignment) (`artifacts/reports/simple_checks_vs_audit.json#cells.PC-B`)

The action-MSE and audit-score thresholds were set on the same 24 normal cells, so '0 normal cells flagged' holds by construction; only the input check is independent of that set.

AI judge: Cosmos-Reason2 end-of-trial judge, held-out eval of 273 recorded trials (artifacts/cosmos_judge/eval_scores.jsonl): first setup 1/21 failures caught; validated prompt C1 p1 20/21 caught, 5/252 false alarms, 4 of them on the unseen yellow can (4/33). Wording-sensitive; end state only. Re-checked live and prospectively in the fine-tune evaluation (72 new trials): 21/23 failures caught, 1/49 false alarms (artifacts/reports/ft_cosmos_live_judge.json).

## 4. Next actions (written by code)

- **Settle success against FP32 at 10 pp: plan about 110-120 trials per arm (planning estimate, assumes equal true rates near 96-97 percent; not a guarantee)** — VC-002 (G6 nominal, pads), VC-020 (G6 nominal, pads), VC-010 (G6 nominal, pads), VC-011 (G6 nominal, pads), VC-012 (G6 nominal, pads), VC-015 (G6 nominal, pads), VC-005 (G6 nominal, pads), VC-007 (G6 nominal, pads), VC-022 (G6 nominal, pads), VC-024 (G6 nominal, pads), VC-002 (stress S4 unseen can), VC-005 (stress S4 unseen can), VC-020 (stress S4 unseen can)
- **Settle success against FP32 at 10 pp: plan about 110-120 trials per arm (planning estimate, assumes equal true rates near 96-97 percent; not a guarantee); also validate start-position changes before deployment** — VC-025 (FP16 run, rubber bands)
- **Do not deploy; fix the calibration input (a simple input check catches it); see the real-arm check of PC-B** — PC-N (offline, deliberately miscalibrated), PC-B (offline, deliberately miscalibrated)
- **Offline warning not confirmed on the arm in 12 trials (unresolved, not 'tolerated'); keep rejecting this build at the calibration-input check; do not read the offline audit as a predictor of closed-loop failure** — PC-B (positive control real arm)
- **Use the fine-tuned policy where the start position varies; confirm at more positions and objects before relying on it** — FT-FP16 (fine-tune vs old, start +3 cm (held out, primary)), FT-FP16 (fine-tune vs old, start -3 cm (held out, symmetry))
- **Check that the fine-tune keeps nominal performance: 10/12 vs 12/12 at the training mark is undecided; plan more trials at the training mark before replacing the old policy there** — FT-FP16 (fine-tune vs old, training start mark (secondary))

## 5. Why the review looks like this
The sixteen‑bit floating point candidate uses the least energy per inference and runs fastest, so it is the natural starting point for validation even though it draws more power while active than the eight‑bit integer builds.  
The position fine‑tune moved the success rate away from failure at both held‑out start shifts, showing improvement, but it has not yet demonstrated enough evidence at the training start mark to replace the old policy there.  
Success versus full precision remains undecided because the confidence intervals are still wide enough that the true difference could lie outside the tolerance, so more trials are needed to show the difference stays within the tolerance.  
The deliberately miscalibrated builds fail a simple input check that flags any deviation in the calibration signal, therefore they are rejected before any further testing.  
The AI judge’s record shows it catches most failures but also produces false alarms on novel objects, so its verdict must be re‑validated before it can be relied upon for decisions.  

## 6. Questions to resolve before deployment
- How many trials are needed to narrow the confidence interval for the sixteen‑bit candidate versus full precision to within ten percentage points?  
- Does the position fine‑tune achieve sufficient success at the training start mark after additional trials?  
- Can the eight‑bit integer builds meet latency and energy targets when tested under nominal pad conditions?  
- Does the AI judge maintain low false‑alarm rates when evaluated on a broader set of objects and scenes?  
- Are the calibration input checks robust enough to catch all miscalibrated variants before deployment?


## Figures (drawn by code from the verdict table)

![Success vs FP32 per candidate: every Newcombe interval crosses the 10 pp tolerance, so no GO yet.](figures/fig_e1_forest.png)

*Success vs FP32 per candidate: every Newcombe interval crosses the 10 pp tolerance, so no GO yet.*

![GPU time on the device vs real-arm success: FP16 is cheapest; success intervals overlap.](figures/fig_cost_evidence.png)

*GPU time on the device vs real-arm success: FP16 is cheapest; success intervals overlap.*

![The frames behind two verdicts: a success, and a failure that Cosmos's first setup called a success.](figures/fig_frames.png)

*The frames behind two verdicts: a success, and a failure that Cosmos's first setup called a success.*

![Position fine-tune: fine-tuned vs old policy at -3, 0 and +3 cm, blinded, 12 vs 12 each.](figures/fig_ft_position.png)

*Position fine-tune: fine-tuned vs old policy at -3, 0 and +3 cm, blinded, 12 vs 12 each.*

