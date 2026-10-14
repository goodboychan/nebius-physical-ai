# 영상 내레이션 대본 v2 (2026-10-13)

v2: scenes 4 and 6 are restructured around the developer's three decisions (validate first / distrust / approve), and the
position-shift wording is softened. Voice: **am_michael** (user's choice).

The plan is `docs/video_plan.md` v2: 2:50 in total, with one continuous 60 s real-arm shot. Lengths assume about 2.5
words per second, with short pauses. Every number is taken from the dashboard, the README or the report files. The
`[PC]` lines are filled in after the positive-control real-arm block, which is planned for the evening of 10/14.

| # | Time | Words (target) | Narration |
|---|---|---|---|
| 1 | 0:00–0:10 | ~22 | Same robot. Same task. One run succeeds, one fails. Before I ship this policy to a tiny Jetson, how do I know which model I can trust? |
| 2 | 0:10–1:10 | ~115 | This is an SO-101 arm running an ACT policy on a Jetson Orin Nano Super. We taught it with one hundred and twenty teleoperated demonstrations, and trained it on Nebius. *(pause)* From that one policy we built twenty-six candidate engines with TensorRT: full precision, half precision, and twenty-four INT8 builds that differ only in how they were calibrated. *(pause)* QuantGate scores every candidate offline first, then checks the arm. Every real trial is blinded. The operator never knows which engine is running, and the results stay sealed until all the trials are logged. *(pause)* That way, no candidate gets picked after we have seen how it did. |
| 3 | 1:10–1:35 | ~55 | QuantGate puts three things side by side for every candidate: what it costs on the real device, how it scored offline, and what it did on the real arm. Training and the offline audit ran on Nebius Jobs. The engines run as TensorRT on the Jetson. |
| 4 | 1:35–2:00 | ~65 | Measuring changed the decision. On this Jetson, half precision was the cheapest engine, not int eight, and on the arm it went nineteen for twenty. The audit's top picks did no better than random picks. A new can, never seen in training, worked forty-eight out of forty-eight. But in a small test with the start moved three centimeters, the arm failed, so position changes still need checking. |
| 5 | 2:00–2:20 | ~50 | The AI layers get checked too. In its first setup, Cosmos Reason, served on a Nebius endpoint, caught one failure in twenty-one. So we tested it like any other component: we tuned the question on one set of recorded trials, then checked it on another. It then caught twenty of twenty-one, with a few false alarms on the new can. Nemotron Super on Token Factory writes the report from verdicts the code has already decided. |
| 5b | (merged into 5) | — | Merged into scene 5: "We also fed the gate a deliberately broken engine. It was flagged offline, yet on the arm it went eleven for twelve, so that warning stays unresolved." (PC-B 11/12 against FP32 10/12) |
| 6 | 2:20–2:45 | ~55 | So QuantGate answers three questions. Which candidate do I validate first? Half precision. Which candidates do I distrust? Broken calibrations, which even a simple input check catches. Can I approve deployment? Not yet. The success comparison needs more trials, and the review lists exactly what to test next. |
| 7 | 2:45–2:50 | ~6 | QuantGate. Evidence before deployment. |

## 읽기 메모

- Write the numbers out in words in the TTS input (for example "seventy-three out of seventy-five"), so that the voice
  does not read digits one by one.
- Read "INT8" as "int eight", "TensorRT" as "tensor R T", "Cosmos Reason" as written, and "Nemotron" as
  "NEE-mo-tron". The phonetic spellings are listed in the TTS input file.
- If scene 2 runs long, cut its last sentence first.
- Scene 5b: once the positive-control result is in, either use the sentence for that result or drop it. With it,
  scene 5 runs 26 s, so trim scene 6 to about 50 words.

## 자막 (화면 하단, 짧게)

| # | Caption |
|---|---|
| 2 | `Re-enactment` (teleop scene only) · `120 demos` · `26 engines: FP32 · FP16 · 24× INT8` · `Blinded trial` |
| 3 | `Nebius Jobs: training + offline audit` · `TensorRT on Jetson Orin Nano Super` |
| 4 | `FP16: 11.6 ms · 82 mJ / inference` · `Audit top 3 vs random 3: 73/75 vs 73/75` · `No pads 8/24 · rubber bands 23/24 · start +3 cm 0/3` |
| 5 | `Cosmos-Reason2 (Nebius Endpoint), held-out eval: first setup 1/21 → validated prompt 20/21 · false alarms 5/252 (yellow can 4/33)` · `Nemotron 3 Super (Token Factory): explains code-decided verdicts, checked` |
| 6 | `Deployment review: a review aid, not an automatic approval` |

## 음성 합성 (2026-10-13)

- Model: **Kokoro-82M** (Apache-2.0), running locally on the GX10 GPU. Script: `scripts/make_narration.py`. Input:
  `docs/narration/tts_input.json` (numbers spelled out, pronunciations given).
- espeak-ng cannot be used on this host, so words missing from the dictionary would be dropped silently. Five of them
  (Jetson, Orin, Nebius, Nemotron, int) get explicit phonemes in the input. Check other new words the same way before
  rendering.
- Sample renders at speed 1.0, with the target length in brackets:

  | Scene | am_michael | af_heart | Target |
  |---|---|---|---|
  | 1 | 11.0 s | 10.0 s | 10 s |
  | 2 | 42.1 s | 38.5 s | 60 s |
  | 3 | 17.9 s | 16.0 s | 25 s |
  | 4 | 20.9 s | 19.3 s | 25 s |
  | 5 | 19.1 s | 17.5 s | 20 s |
  | 6 | 19.0 s | 17.8 s | 25 s |
  | 7 | 3.2 s | 2.8 s | 5 s |
  | **Total** | **133 s** | **122 s** | |

  The spare time leaves room for pauses and the arm's own sound.
- The generated audio is not stored in the repository; it can be regenerated from the script and the input. Disclose
  in the video description that the narration is synthesized.

- v2 render (am_michael, speed 1.0): scenes 1–7 run 11.0 / 42.1 / 17.9 / 25.4 / 19.1 / 21.9 / 3.2 s, 140.7 s in total.
  Scene 2 has about 18 s spare, so scenes 1 and 4 can borrow a second or two from it.
