# 영상 내레이션 대본 v2 (2026-10-13)

v2: scenes 4 and 6 are restructured around the developer's three decisions (validate first / distrust / approve), and the
position-shift wording is softened. Voice: **am_michael** (user's choice).

The plan is `docs/video_plan.md` v2: 2:50 in total, with one continuous 60 s real-arm shot. Lengths assume about 2.5
words per second, with short pauses. Every number is taken from the dashboard, the README or the report files. The
`[PC]` lines are filled in after the positive-control real-arm block, which is planned for the evening of 10/14.

| # | Time | Words (target) | Narration |
|---|---|---|---|
| 1 | 0:00–0:11 | ~27 | Same robot. Same task. One run succeeds, one fails. Before I ship this policy to a tiny Jetson, how do I know which model I can trust? |
| 2 | 0:11–1:07 | ~105 | This is an SO-101 arm running an ACT policy on a Jetson Orin Nano Super. We taught it with one hundred and twenty teleoperated demonstrations, and trained it on Nebius. From that one policy, we built twenty-six candidate engines with TensorRT: full precision, half precision, and twenty-four int eight builds that differ only in how they were calibrated. QuantGate scores every candidate offline first, then checks the arm. Every real trial is blinded. The operator never knows which engine is running, and the results stay sealed until all the trials are logged. That way, no candidate gets picked after we have seen how it did. |
| 3 | 1:07–1:26 | ~46 | QuantGate puts three things side by side for every candidate: what it costs on the real device, how it scored offline, and what it did on the real arm. Training and the offline audit ran on Nebius Jobs. The engines run as TensorRT on the Jetson. |
| 4 | 1:26–2:06 | ~105 | Measuring changed the decision. On this Jetson, half precision was the cheapest engine, not int eight, and on the arm it went nineteen for twenty. The audit's top picks did no better than random picks. A new can worked forty-eight out of forty-eight. But with the start moved three centimeters, the arm failed. So we recorded fifty demonstrations at shifted positions, fine-tuned on Nebius, and tested it blinded, at a position it never saw. There, it went twelve for twelve, where the old policy went three for twelve, and ten for twelve on the other side. At the trained spot, more trials are still needed. |
| 5 | 2:06–2:31 | ~57 | The AI layers get checked too. In its first setup, Cosmos Reason, on a Nebius endpoint, caught one failure in twenty-one. We tested it like any other component, on held-out recordings, and a validated question caught twenty of twenty-one. Nemotron Super on Token Factory explains the review in words, while every verdict and number comes from code. |
| 5b | — | — | Dropped in v3 to keep the video under 3 minutes. The positive-control result (PC-B 11/12 vs FP32 10/12, warning unresolved) stays on the dashboard and in the submission. |
| 6 | 2:31–2:53 | ~51 | So QuantGate answers three questions. Which candidate do I validate first? Half precision. Which do I distrust? Broken calibrations, which a simple input check catches, and any engine whose files no longer match what was audited. Can I approve deployment? Not yet. The review lists exactly which trials are still missing. |
| 7 | 2:53–2:57 | ~4 | QuantGate. Evidence before deployment. |

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

## 음성 합성 v3 (2026-10-14)

- Voice `am_michael`, speed 1.0. v3.1 (2026-10-15): scene 4 now has the fine-tune result. Speech totals 161 s, and the track runs **2:57** (`scripts/make_narration_track.py`). Scene 2's slot is 56 s; the real-hardware footage passes 1 minute together with the scene 4 clips.
- Files:
  - `docs/narration/narration_v3_am_michael.m4a` is the full track, with each scene at its slot start.
  - `docs/narration/narration_v3.srt` holds the subtitles, timed by sentence.
- Scene 4's outcome sentence was added after unsealing (10/15) and the track regenerated.

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
