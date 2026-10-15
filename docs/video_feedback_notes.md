# Video v7 feedback notes (collected first, applied together)

Base: video v6 (`video/final/quantgate_v6.mp4`, `scripts/make_video.py`, narration v3, am_michael). Notes are
numbered in the order the user gave them.

## Note 1 — opening order (2026-10-16)

- **Order**:
  1. Open on the **"Same robot, same task" success/failure clips**, which is scene 1's first 4.1 s now. No logo first.
  2. Then the card **"Before I ship this policy to a tiny Jetson, how do I know which model I can trust?"**
     - **Centre-aligned**, appearing with a **brightness fade-in**.
  3. **Then** the QuantGate logo explanation (scene 0 now). It moves after the question.
- **Logo segment**:
  - Use the user's animation `video/assets/quantgate_logo_intro.mp4`. It is 14.5 s, 1536×1024 (3:2), 30 fps, silent:
    the Q is drawn, then "Quantization", then the small square "candidate", then the "QuantGate" wordmark.
  - It must fit a 1920×1080 frame: scale to 1080 high (1620×1080) on the same dark background (#0F151C-ish), with
    no crop.
- **Narration for the logo**: the user's idea, to be voiced:
  - User's draft: "For the Quantization We need to select the candidate that has earned its next test, not an
    approval. That's why robot researcher needs quantgate."
  - Proposed wording (grammar only, same meaning): **"For quantization, we need to pick the candidate that has earned
    its next test — not an approval. That's why robot researchers need QuantGate."**
  - Replaces scene 0's current lines ("Quant Gate. The Q stands for quantization. The gap at its corner is the
    gate…"). Check the timing: about 6–7 s of speech against the 14.5 s animation. Either align each phrase to the
    animation's beats (quantization → candidate → QuantGate), or trim the animation. Decide when applying.
- **Knock-on**:
  - Scene 1's narration currently covers the clips and the question card. Keep it with the clips, but move the card's
    line so it lands on the centred card.
  - Re-time `narration_v3_timing.json` (the scene order changes: 1 → 0), and update the subtitles and the scene plan.

## Note 2 — scene 2, data collection and terms (2026-10-16)

- Keep the data-collection footage (demo and teleop clips) as it is.
- **Spell out ACT once**, the first time it is said. Current: "running an A C T policy". Proposed: "running an
  A C T policy — Action Chunking with Transformers — on a Jetson Orin Nano Super". Optionally also as an on-screen
  caption the first time.
- **Name the Nebius service precisely** (the user asked to call it "Endpoint"):
  - Accuracy check: in scene 2 the line is "trained it on Nebius". Training ran on **Nebius Jobs** (L40S), not on an
    endpoint. The **Nebius AI Endpoint** is where Cosmos-Reason2 runs (scene 5).
  - Proposed, scene 2: "and trained it with Nebius Jobs on an L40S GPU".
  - Proposed, scene 5: "Cosmos Reason, on a Nebius AI Endpoint, …". It now says "a Nebius endpoint".
  - **Approved by the user** (2026-10-16): Jobs in scene 2, AI Endpoint in scene 5.

## Available insert — Isaac Sim twin clip (not yet placed)

- `~/edgeqgate_data/sim_out/t0001_twin_side_by_side.mp4`, 15 s: real overhead next to the Isaac Sim twin replaying
  the same joint trajectory (T0 trial 1, success).
- The grasp is assisted and labelled so on screen. Where it goes is to be decided with the scene feedback; it needs
  one new narration line.

## Note 3 — engine cost, scene 3 (2026-10-16)

- **Problem**: the current shot (the dashboard "Engine cost" capture, 11.4 s) carries too much at once.
- **Replace** it with a code-drawn, animated chart that shows only the key point, in two beats:
  1. **GPU compute time per inference**: the bars grow, then the caption **"FP16 is the fastest"** appears.
  2. **Energy per inference**: the bars grow, then the caption **"FP16 is the cheapest"** appears.
- **Data** (`video/scene_plan/data/01_engine_cost.csv`, trtexec, 15 W, measured engines only):

  | Engine | GPU ms | mJ / inference |
  |---|---|---|
  | FP32 (VC-000) | 53.4 | 403 |
  | FP16 (VC-025) | **11.6** | **82** |
  | INT8, 3 benched builds (VC-002/005/020) | 16.8–17.1 | 101 |

  - Proposed: three bars (FP32, FP16, INT8). INT8 is shown as 16.8 ms and 101 mJ, labelled "3 builds measured".
- **Wording check**:
  - "cheapest" here means energy per inference. INT8 draws less power while it runs (10.85 W against 11.97 W) but
    takes longer, so it costs more per inference.
  - Proposed small subtitle under the caption: "energy per inference". This keeps "FP16 is the cheapest" true.
- **Timing**: scene 3's 11.4 s first segment. Fast-path: GPU bars about 0–4 s, caption 1 at about 4 s; energy bars
  about 5.5–9 s, caption 2 at about 9 s. Align with the narration lines when applying ("what it costs on the real
  device …").
- **Decided** (2026-10-16): build the chart as proposed. Visual reference: the user's
  `video/assets/engine_cost_reference.mp4` (6.5 s, 1920×1088).
  - Style from the reference: light background; horizontal bars; title "Engine cost on the deployment target"; panel
    titles "GPU Compute" (median ms per 100-step chunk) and then "Energy" (energy per inference above idle, mJ); FP16
    bar in green with a soft highlight; others teal and grey; values at the bar ends; the caption as a green pill at
    the lower right.
  - Content as proposed: **three bars**, FP16, INT8 ("3 builds measured", 16.8 ms and 101 mJ) and FP32. Captions
    "FP16 is the fastest", then "FP16 is the cheapest", with "energy per inference" under the second.
  - Render at 1920×1080, 30 fps (the reference is 1088 high and 20 fps).

## Note 4 — "Closed-loop success by cell", scene 3 second shot (2026-10-16)

- Too much on screen (the dashboard capture). Replace it with an **animated chart only**, plus one key line.
- Data: `02_g6_success_by_cell.csv` (G6, 245 blinded trials; 10 cells at 24–25/25 and FP32 24/25; VC-005 14/15
  after its stop).
- Proposed: the bars (success with Wilson 95% ticks) grow left to right, sorted by cell, with FP32 as a grey
  reference line. Key line: **"Every cell succeeded 92–100% of the time on the arm"**, then a sub-line **"25 trials
  per cell cannot separate them"**. The exact range comes from the CSV when built.

## Note 5 — "FP16: cheapest engine", scene 4 first shot (2026-10-16)

- `fig_cost_evidence.png`: the labels inside the graph overlap and look messy. Rebuild it as a clean animation.
- Data: `03_cost_vs_success.csv` (GPU ms against real-arm success, Wilson 95%).
- Proposed: the points appear one by one (FP32 grey, INT8 teal, FP16 green) on a GPU-ms × success plot, with no
  in-plot text except a short label per group, placed without overlap. Key line: **"FP16: cheapest engine,
  19/20 on the arm"**.

## Note 6 — "Audit-picked vs random INT8 cells", scene 4 second shot (2026-10-16)

- Animate it and make it clean.
- Data: `04_audit_vs_random.csv` (73/75 against 73/75; difference Newcombe 95% [−6.8, +6.8] pp).
- Proposed: two bars grow together to the same height. Key line: **"Audit's top picks: 73/75. Random picks: 73/75."**
  Sub-line: **"The offline score did not predict the arm."**

## Common style for notes 3–6

- Same look as the user's engine-cost reference: light panel, one chart per shot, values at the bar ends, FP16 in
  green where present, a key line as a pill at the lower right.
- Drawn by code from the committed CSVs, so the numbers cannot drift.

## Note 7 — position fine-tune result, scene 4 (2026-10-16)

- The other demo clips are fine as they are.
- "+3 cm 12/12 vs 3/12 · −3 cm 10/12 vs 2/12 · training mark undecided" (`fig_ft_position.png`): show it as an
  animation as well. Data: `05_position_finetune.csv`.
- Proposed: the old-policy and fine-tuned bars grow, per position, in narration order: +3 cm, then −3 cm, then the
  training mark (T0 + T0R pooled, 22/24 against 23/24). Key line: **"Fixed where it failed: +3 cm 12/12 vs 3/12,
  −3 cm 10/12 vs 2/12"**, then **"training mark: still undecided"**.

## Note 8 — deployment report, scene 5 third shot (2026-10-16)

- Show the **whole** deployment report, **sliding from top to bottom** (a slow vertical scroll), instead of a cropped
  static capture (`report_meta.png`, rows 0–1100).
- Source: a full-height capture of the dashboard report section. The scroll speed is set so the whole report passes
  in the shot's 7.9 s.

## Note 9 — ending: logo with a kick line (2026-10-16)

- End on the logo together with a **kick line**, shown and spoken.
- Proposed kick (calls back to the logo's meaning at the start): **"Earn the next test, not the approval."**
  - Scene 7 narration: "Quant Gate. Earn the next test, not the approval." (now "QuantGate. Evidence before
    deployment.").
  - Picture: the final frame of the user's logo animation (Q + wordmark), the kick line under it, and the repository
    URL small.
  - Alternatives, if wanted: "Measure it on the device. Seal the trials. Then decide." / "Trust the evidence, not the
    precision label."
- Follow-up (2026-10-16): the outro uses the user's **logo-only animation** (`video/assets/quantgate_logo_outro.mp4`,
  14.5 s). Its wordmark build (9 s to the end) plays, fitted to the 4.2 s slot, and the kick line fades in under it.
