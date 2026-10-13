# QuantGate — deployment report v2 (auto-generated)

> Verdicts are decided by code (`d3_v2_verdicts.json`, hash `1041eb597810cc29`); Nemotron 3 Super (Token Factory) wrote the explanation. A structured validator checked every candidate's verdict, success fractions and latency in the prose. v1 is kept as history (`d3_final_report.md`).

| Item | Value |
|---|---|
| Latency | 4.2 s |
| **Validator findings** | **0** |

---



## 1. Recommendation
Validate VC-025 first; it has the lowest GPU time on the device (11.6 ms) among the candidates with reported trtexec times.

## 2. Approval status
No candidate carries a GO or NO‑GO verdict; all non‑flagged entries are INSUFFICIENT_EVIDENCE, so approval remains on hold pending sufficient evidence.

## 3. Flagged candidates
- PC‑N – context: offline, deliberately miscalibrated – verdict: FLAGGED  
- PC‑B – context: offline, deliberately miscalibrated – verdict: FLAGGED

## 4. Next actions (decided by code)

- **Settle success against FP32 at 10 pp: plan about 110-120 trials per arm (planning estimate, assumes equal true rates near 96-97 percent; not a guarantee)** — VC-002 (G6 nominal, pads), VC-020 (G6 nominal, pads), VC-010 (G6 nominal, pads), VC-011 (G6 nominal, pads), VC-012 (G6 nominal, pads), VC-015 (G6 nominal, pads), VC-005 (G6 nominal, pads), VC-007 (G6 nominal, pads), VC-022 (G6 nominal, pads), VC-024 (G6 nominal, pads), VC-002 (stress S4 unseen can), VC-005 (stress S4 unseen can), VC-020 (stress S4 unseen can)
- **Settle success against FP32 at 10 pp: plan about 110-120 trials per arm (planning estimate, assumes equal true rates near 96-97 percent; not a guarantee); also validate start-position changes before deployment** — VC-025 (FP16 run, rubber bands)
- **Do not deploy; fix the calibration input (a simple input check catches it); see the real-arm check of PC-B** — PC-N (offline, deliberately miscalibrated), PC-B (offline, deliberately miscalibrated)
- **Offline warning not confirmed on the arm in 12 trials (unresolved, not 'tolerated'); keep rejecting this build at the calibration-input check; do not read the offline audit as a predictor of closed-loop failure** — PC-B (positive control real arm)


## Figures (drawn by code from the verdict table)

![Success vs FP32 per candidate: every Newcombe interval crosses the 10 pp tolerance, so no GO yet.](figures/fig_e1_forest.png)

*Success vs FP32 per candidate: every Newcombe interval crosses the 10 pp tolerance, so no GO yet.*

![GPU time on the device vs real-arm success: FP16 is cheapest; success intervals overlap.](figures/fig_cost_evidence.png)

*GPU time on the device vs real-arm success: FP16 is cheapest; success intervals overlap.*

![The frames behind two verdicts: a success, and a failure that Cosmos called a success.](figures/fig_frames.png)

*The frames behind two verdicts: a success, and a failure that Cosmos called a success.*

