# From evidence to the next test (written by code)

## VC-025 (FP16, old policy)
**Status**: recommended to validate first; approval on hold

Confirmed:
- cheapest engine on the device: 11.6 ms and 82 mJ per inference (power_bench/SUMMARY.md)
- real arm 19/20 against FP32 10/10 (fp16_analysis.json)

Open:
- success against FP32 within 10 pp: INSUFFICIENT_EVIDENCE, and both arms are at or above 95%, so the pre-registered ceiling rule keeps it undecided

Evidence:
- `artifacts/reports/fp16_analysis.json#primary_fp16_vs_fp32`
- `artifacts/freeze/fp16_post.json`
- `artifacts/trials/fp16_unsealed/stress_fp16_F0_sealed.jsonl`

Next test:
- compare: VC-025 (FP16) vs VC-000 (FP32), same old policy
- conditions: training start mark, rubber-band gripper, cola can
- measure: success (consensus re-judge), placement error, gripper chatter
- schedule: sealed, interleaved, new tokens
- rule: pre-register a revised E1 (success) rule without the ceiling clause: the success criterion is met if the 97.5% Newcombe upper bound of the degradation is below 10 pp; a final GO also needs placement (E2, 5 px) and the preflight
- trials per arm for 80% power on the success criterion (not the chance of a final GO), under the revised rule, if equal at 96%: 120
- with the current ceiling rule, power at 200/arm: 0.32

## FT-FP16 (position fine-tune)
**Status**: next candidate where the start varies between -6 and +3 cm with the cola can; not a replacement at the trained spot, not an object or +6 cm fix

Confirmed:
- fine-tune vs old, start +3 cm (held out, primary): 12/12 vs old 3/12, IMPROVEMENT_DETECTED
- fine-tune vs old, start -3 cm (held out, symmetry): 10/12 vs old 2/12, IMPROVEMENT_DETECTED
- start -6 cm (beyond the demonstrations): 8/12 vs old 0/12, IMPROVEMENT_DETECTED

Open:
- training mark, T0 + T0R pooled: 22/24 vs old 23/24, INSUFFICIENT_EVIDENCE
- yellow can at +3 cm (held-out object, primary): 0/12 vs old 3/12, NOT_DETECTED
- start +6 cm (beyond the demonstrations): 0/12 vs old 0/12, NOT_DETECTED

Evidence:
- `artifacts/reports/ft3_analysis.json#pooled_T0_T0R`
- `artifacts/freeze/ft_post.json`
- `artifacts/freeze/ft3_post.json`
- `artifacts/finetune/T0R_modes.json`
- `artifacts/reports/ft4_analysis.json`
- `artifacts/freeze/ft4_post.json`
- `artifacts/finetune/GEN_modes.json`
- T0 failures: trials 18 and 22 (placement disturbance, docs/sessions/ft_operator_notes.md); clip: dashboard/clips/t1_old_vs_ft.mp4

Next test:
- compare: FT-FP16 vs VC-025 (old FP16 policy) at the training mark; for the gaps, a new fine-tune with demonstrations at +6 cm and with the yellow can, re-tested at TYP/T6P under a new pre-registration
- conditions: training start mark (nominal); +6 cm and the yellow can at +3 cm (generalization gaps, amendment 7)
- measure: success, failure mode (placement disturbance), gripper chatter
- schedule: sealed, interleaved, new tokens (operator blinding stays partial: the motions differ)
- rule: success non-inferiority at 10 pp (97.5% Newcombe), pre-registered without the ceiling clause (if both arms land at or above 95%, the current ceiling clause would hold it undecided); a final GO also needs placement (E2, 5 px) and the preflight
- trials per arm for 80% power on the success criterion (not the chance of a final GO), under the revised rule, if truly equal (95.8%): 120
- trials per arm for 80% power on the success criterion (not the chance of a final GO), under the revised rule, if the observed 4 pp gap is real: 400
- with the current ceiling rule, power at 120/arm if truly equal: 0.32

## INT8 builds (24 calibration variants)
**Status**: not first: slower and costlier per inference than FP16 on this device

Confirmed:
- 16.8-17.1 ms and 101 mJ per inference for the 3 benched builds
- audit-picked cells 73/75 vs random 73/75: the offline score did not predict the arm

Open:
- success against FP32: INSUFFICIENT_EVIDENCE for every cell, under the ceiling rule
- post hoc: VC-002 chatters about twice as much as FP16 (hypothesis)

Evidence:
- `artifacts/reports/g6_analysis.json`
- `artifacts/freeze/lock3.json`
- `artifacts/reports/ft_chatter.json`

Next test:
- compare: one INT8 cell (VC-002) vs FP16 (VC-025), only if memory or power forces INT8
- conditions: training start mark
- measure: success and gripper chatter (pre-registered as the primary)
- schedule: sealed, interleaved
- rule: chatter: two-sided MWU at alpha 0.05, registered before the block; success as for FP16
- chatter, as in the earlier blocks (block size, not a power calculation): 24

## PC-B (black-frame calibration)
**Status**: rejected

Confirmed:
- flagged offline by the input check, action error and audit score

Open:
- the offline warning was not confirmed on the arm in 12 trials (unresolved)

Evidence:
- `artifacts/reports/simple_checks_vs_audit.json`
- `artifacts/reports/positive_control_analysis.json`

Next test:
- compare: none: block it at the calibration-input check
- conditions: -
- measure: -
- schedule: -
- rule: preflight BLOCK (FLAGGED)
