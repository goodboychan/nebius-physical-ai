# Orin engine bench, fine-tuned engine (2026-10-15, robot idle, nvpmodel 15W)

Exploratory follow-up to `power_bench/SUMMARY.md` (external review 6: the FT engine had no measurement of its own).
Same protocol (`scripts/orin_power_bench_ft.sh`): 30 s idle baseline, then each engine back-to-back on trtexec for 30 s
after a 2 s warm-up while tegrastats samples every 100 ms. VC-025 is re-run in the same session as a drift reference.

| Engine | sha256 | GPU ms (median / p99) | Throughput | VDD_IN | ΔEnergy / inference |
|---|---|---|---|---|---|
| idle | — | — | — | 4.85 W | — |
| FT-FP16 | `4affc06d…` (the engine used in T1/T0/T2) | **11.6 / 11.7** | 86.1 qps | 11.89 W | **82 mJ** |
| VC-025 (re-run) | `3b19f7eb…` | 11.6 / 11.6 | 86.2 qps | 11.97 W | 83 mJ (10/11: 82 mJ) |

- FT-FP16 costs the same as VC-025 on this device, as expected for the same architecture and build cache; now measured
  rather than assumed.
- Only VC-000, VC-025, VC-002, VC-005, VC-020 (10/11) and FT-FP16 (10/15) were benched. The other 21 INT8 cells were not;
  the review shows no cost number for them.
