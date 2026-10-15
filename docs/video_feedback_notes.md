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
