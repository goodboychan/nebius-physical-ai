# 데모 영상 계획 v2 (2026-10-12, 스토리텔링 검토 반영)

- **Length: 2:50.** The official rule recommends under 3 minutes, and the Physical AI track requires at least 1 minute
  of real hardware in operation. This plan has one **continuous 60 s** real-arm shot.
- **Main character: the developer who has to ship the robot.** The story asks the developer's question ("Can I ship
  this, and as what?") and ends on the deployment review card.
- **Story arc**: problem → how QuantGate gathers evidence → the measurements change the decision → what the developer
  takes away.
- Narration is in English. All experiments are analyzed (2026-10-13); the narrative is fixed at `LOCK-4`.

## 장면 구성

> v3.1 timing (2026-10-15), from the synthesized narration: 1 0:00–0:11 · 2 0:11–1:07 · 3 1:07–1:26 · 4 1:26–2:06 ·
> 5 2:06–2:31 · 6 2:31–2:53 · 7 2:53–2:57.
> - Scene 4 clips: `video/edit/t1_old_vs_ft_counted.mp4` (counted T1 trials 2 and 1), then the dashboard
>   `fig_ft_position.png`. Scene 2: `video/edit/demo_ft.mp4`, the 60 s continuous take, cut to 56 s.
> - Scene 4 now ends on the position fine-tune: the 50 shifted demos, then the blinded +3 cm test. The picture is the
>   dashboard position strip, then the post-block demonstration clip (labelled "demonstration, not counted"), then
>   the T1 result (now: the counted T1 pair clip replaces the demonstration clip, since both demos succeeded).
> - Scene 6 adds the deployment preflight card (BLOCK / HOLD).
> - Narration text: `docs/narration/tts_input.json`; audio: `docs/narration/narration_v3_am_michael.m4a`;
>   subtitles: `docs/narration/narration_v3.srt`.

| # | Time | Picture | Narration (draft) | Material |
|---|---|---|---|---|
| 1 | 0:00–0:10 | 3 s success clip → 3 s failure clip (knocked over) → black screen with the question | "Same robot, same task. Can I ship this to a tiny Jetson, and as which model?" | `clips/g6_success.mp4`, `clips/g6_fail_knock.mp4` |
| 2 | 0:10–1:10 | **Continuous 60 s real-arm shot** (phone, side view), with small captions: task, device, candidate engines, blinded trial | "The arm runs an ACT policy on a Jetson Orin Nano Super, trained on Nebius from 120 demonstrations (re-enactment shown). We built 26 candidate engines: FP32, FP16 and 24 INT8 calibrations. Every real trial is blinded: the operator never knows which engine is running." | New shot: phone 30–40 cm beside the follower, 16:9, leader out of frame, one full trial. A 5 s insert of the re-enactment plus `clips/demos_top_wrist.mp4`, captioned "re-enactment" |
| 3 | 1:10–1:35 | Dashboard: engine cost bars → per-cell success chart | "QuantGate puts cost measured on the device next to real-arm results. Training and the offline audit ran on Nebius Jobs; the engines are TensorRT on the Jetson." | D7 board "Engine cost" and "Closed-loop success" |
| 4 | 1:35–2:00 | Three findings, one caption each: FP16 cost → audit vs random 73/75 vs 73/75 → no-pad slip and 3 cm shift clips | "Measuring changed the decision. FP16 was the cheapest engine here, not INT8, and on the arm it went 19 for 20. The audit's top picks did no better than random picks. What moved success was grip and position." | `clips/v1_nopad_drop.mp4`, `clips/v2_shift_regrasp.mp4`, then 3 s of `clips/v2_s0_vs_s4.mp4` (unseen can: 48/48) |
| 5 | 2:00–2:20 | Failure 186 final frame with Cosmos's "Yes" overlaid (the operator's hand at the desk edge is the real use case) → Nemotron report v2 with "Validator findings: 0" highlighted (code-decided verdicts, structured check) | "The AI layers get checked too. In its first setup, Cosmos Reason, served on a Nebius endpoint, caught one failure in twenty-one. So we tested it like any other component: we tuned the question on one set of recorded trials, then checked it on another. It then caught twenty of twenty-one, with a few false alarms on the new can. Nemotron Super on Token Factory writes the report from verdicts the code has already decided." (synced with `docs/narration/tts_input.json`) | `clips/g6_fail_knock.mp4` last frame, `d3_final_report.md` |
| 6 | 2:20–2:45 | Dashboard deployment review card, line by line, then a click into a failure video | "What you take away is a review: FP16 is the cheapest engine here and went 19 for 20 on the arm with placement matching FP32, but the success comparison still needs more trials; the weak spots are grip and position; and here is what to test next." | D7 board "Deployment review" |
| 7 | 2:45–2:50 | Logo + repository URL | "QuantGate. Evidence before deployment." | `docs/assets/quantgate_logo.png` |

## 문구 규칙 (편집 전 확인)

| Do not say | Say instead |
|---|---|
| "Calibration tuning bought nothing" | "In this experiment, no success advantage from calibration choice was detected" |
| "The real risk was not INT8" | "The experiment revealed conditions you must check before deploying" |
| "Cosmos watches every run" | "215 trials watched live, 245 final frames judged afterwards" |
| "FP16 is the answer" | "FP16 is the cost-favored candidate" (until the FP16 analysis is in) |
| Mixing completed and planned trials | "245 completed trials" and "stress tests in progress", stated separately |

## 촬영할 것 (사용자)

- **The continuous 60 s side-view shot** (most important):
  - Run one extra trial just for the camera, separate from the blinded blocks. Keep the phone and hands out of the
    overhead camera's view.
  - Shoot with the gripper in its current configuration, and caption that configuration.
- **Re-enactment**: `lerobot-teleoperate` only, never `lerobot-record`. Run it after the S4 and FP16 blocks.
- **Screen recordings**: the dashboard (scroll and clicks) and the Nebius console (Jobs, Endpoint). Mask keys, tokens
  and the account area.
- **Optional**: a cold can from the fridge, as an atmosphere shot. No success-rate claim goes with it.

## 편집 메모

- Every number in the narration must come from the dashboard, the README or the report files. Check them once
  against their sources after editing.
- Captions must say which results are blinded and pre-registered (precision) and which are observations (gripper,
  position).
- Do not name engine cells in the narration. Use "audit top" or "random".
