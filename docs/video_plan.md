# 데모 영상 계획 (초안, 2026-10-12)

Target length: **about 3 minutes**. Check the Devpost limit before editing. Narration is in English, for the judges,
with Korean subtitles optional.
Principle: per the `LOCK-4` rule, the story is fixed only after the stress v2 and FP16 analyses. This draft
leaves those slots empty (`[PENDING]`) and builds the rest around results that are already confirmed.

## 장면 구성

| # | Time | Picture | Narration (draft) | Material |
|---|---|---|---|---|
| 1 | 0:00–0:15 | The SO-101 picks up the can and stands it on the coaster (one clean success, normal speed) | "Edge robots run quantized policies. The usual question is whether INT8 is safe. We built a gate to find out on a real arm." | G6 main 12 (`main012_1008_004335`, 6.8 px) |
| 2 | 0:15–0:40 | Pipeline diagram → the 26-cell grid → the Nebius Jobs fan-out | "One ACT policy trained on Nebius Jobs, 24 INT8 variants from TensorRT Model Optimizer, plus FP16 and FP32, all built on a Jetson Orin. Five offline predictors score every variant on Nebius before any real trial." | README pipeline, `build_grid_lerobot.py` output, Jobs console capture |
| 3 | 0:40–1:00 | Scroll through the decision log and lock hashes, then the blinded runner screen (trial number only) | "Everything was pre-registered and hash-locked. The operator never knew which engine was running." | `docs/decision_log.md`, `artifacts/freeze/lock3.json`, runner terminal capture (latency hidden) |
| 4 | 1:00–1:30 | Dashboard: per-cell dot plot → forest plot | "245 blinded trials. FP32 24 of 25, INT8 194 of 200. Audit-picked against random cells: 73 against 73. No gap detected, and the offline ranking did not predict the arm." | D7 board "Closed-loop success by cell", "Pre-registered contrasts", "Did the offline rank predict" |
| 5 | 1:30–1:45 | Dashboard engine-cost bars | "On this Jetson, FP16 is faster and cheaper per inference than INT8. Calibration tuning bought nothing." | D7 board "Engine cost" (`[PENDING FP16 real-arm]` add one line) |
| 6 | 1:45–2:15 | Fast cuts: no-pad slip → rubber-band success → 3 cm shift air grasp and knock-over → `[PENDING S4 yellow can]` | "What did move the success rate was the margins: gripper friction, 33 to 92 percent. A 3 centimetre shift: the policy reaches for where the can used to be." | stress v1 S0 slip (operator picks one), stress v2 S0 success, stress v2 S1 trial 1, risk-magnitude figure |
| 7 | 2:15–2:40 | Failure 186 final frame, with Cosmos's "Yes" overlaid | "Cosmos-Reason2 watched every run on a Nebius endpoint. Shown this frame, it said the can was standing. It said yes to all 245. Validate your AI judge before you trust it." | `main186_1010_221517` last frame, `d4_retro_judge_g6.json` |
| 8 | 2:40–2:55 | Nemotron report on screen, with the validator line highlighted ("Numbers not in evidence") | "Nemotron 3 Super on Token Factory writes the deployment report, and every number is checked against the evidence." | `artifacts/reports/d3_final_report.md` |
| 9 | 2:55–3:00 | Logo + repository URL | "QuantGate. The real risk at the edge was not INT8." | `docs/assets/quantgate_logo.png` |

## 촬영할 것 (사용자)

- **New shots** (optional, better quality than the trial videos):
  - A side view of the arm doing one successful pick-and-place.
  - A close-up of the gripper with the rubber bands.
  - The yellow can.
- **Screen recordings**:
  - The blinded runner screen. Check that latency is not shown.
  - Starting or stopping the Cosmos endpoint, or the Nebius console.
  - The Jobs list.
- Do not capture keys, tokens or the account email on screen. In particular, mask the endpoint URL and token, and the
  profile area of the Nebius console.

## 편집 메모

- Every number in the narration must come from the dashboard, the README or the report files. After editing, check
  each number against its source once.
- Captions must say which results are blinded and pre-registered (precision) and which are observations (gripper,
  position).
- Trial-video cell names are public after unsealing, but the narration does not name cells. It talks in terms of
  "audit top" and "random".
