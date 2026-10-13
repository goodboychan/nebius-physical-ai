# QuantGate — deployment report v2 (auto-generated)

> Verdicts are decided by code (`d3_v2_verdicts.json`, hash `8ebbd4fedf61b71d`); Nemotron 3 Super (Token Factory) wrote the explanation. A structured validator checked every candidate's verdict, success fractions and latency in the prose. v1 is kept as history (`d3_final_report.md`).

| Item | Value |
|---|---|
| Latency | 5.5 s |
| **Validator findings** | **0** |

---



## 1. Recommendation  
Validate **VC-025** first. It has the lowest device‑level latency reported (e2e_ms = 24.7 ms) and the fastest GPU inference time (gpu_ms_trtexec = 11.6 ms) among the candidates with timing data, making it the cheapest to test on the hardware.

## 2. Approval status  
No candidate carries a **GO** or **NO‑GO** verdict. All non‑flagged entries are marked **INSUFFICIENT_EVIDENCE**; therefore, approval is pending pending further evidence.

## 3. Flagged candidates  
- **PC-N** – verdict **FLAGGED** (input_check, action_mse_flag, score_mag_flag, score_align_flag all true)  
- **PC-B** – verdict **FLAGGED** (same flag set as PC-N)

## 4. What is still missing  
For each **INSUFFICIENT_EVIDENCE** entry (e.g., VC-002, VC-020, VC-010, VC-011, VC-012, VC-015, VC-005, VC-007, VC-022, VC-024, VC-025 under its respective context), additional evidence is needed to tighten the confidence intervals (e1_ci_pp) or increase the success count relative to the reference so that the success comparison can be deemed conclusive. Likewise, the flagged PCs require resolution of the four flag conditions (input check, action MSE, score magnitude, score alignment) before they can be re‑evaluated. Until such data are supplied, the verdicts remain unchanged.