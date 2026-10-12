# 영상 내레이션 대본 v1 (2026-10-13)

The plan is `docs/video_plan.md` v2: 2:50 in total, with one continuous 60 s real-arm shot. Lengths assume about 2.5
words per second, with short pauses. Every number is taken from the dashboard, the README or the report files. The
`[PC]` lines are filled in after the positive-control real-arm block, which is planned for the evening of 10/14.

| # | Time | Words (target) | Narration |
|---|---|---|---|
| 1 | 0:00–0:10 | ~22 | Same robot. Same task. One run succeeds, one fails. Before I ship this policy to a tiny Jetson, how do I know which model I can trust? |
| 2 | 0:10–1:10 | ~115 | This is an SO-101 arm running an ACT policy on a Jetson Orin Nano Super. We taught it with one hundred and twenty teleoperated demonstrations, and trained it on Nebius. *(pause)* From that one policy we built twenty-six candidate engines with TensorRT: full precision, half precision, and twenty-four INT8 builds that differ only in how they were calibrated. *(pause)* QuantGate scores every candidate offline first, then checks the arm. Every real trial is blinded. The operator never knows which engine is running, and the results stay sealed until all the trials are logged. *(pause)* That way, no candidate gets picked after we have seen how it did. |
| 3 | 1:10–1:35 | ~55 | QuantGate puts three things side by side for every candidate: what it costs on the real device, how it scored offline, and what it did on the real arm. Training and the offline audit ran on Nebius Jobs. The engines run as TensorRT on the Jetson. |
| 4 | 1:35–2:00 | ~60 | Measuring changed the decision. On this Jetson, half precision was the cheapest engine, not INT8, and on the arm it went nineteen for twenty. The audit's top picks did no better than random picks: seventy-three out of seventy-five both ways. What really moved success was grip and position. |
| 5 | 2:00–2:20 | ~50 | The AI layers get checked too. In our setup, Cosmos Reason, served on a Nebius endpoint, called this frame a success. It missed all seven failures. Nemotron Super on Token Factory writes the deployment report, and every number in it is checked against the evidence. |
| 5b | (inside 5, +6 s) | ~18 | `[PC]` And when we gave it a deliberately broken engine, the offline audit flagged it, and the arm `[agreed / did not]`. |
| 6 | 2:20–2:45 | ~58 | What you take away is a review, not a guess. Half precision is the cost-favored candidate. Its placement matched full precision, but the success comparison still needs more trials. The weak spots are grip and start position. And the review tells you exactly what to test next. |
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
| 5 | `Cosmos-Reason2 (Nebius Endpoint): 0 of 7 failures caught, single-frame setup` · `Nemotron 3 Super (Token Factory): numbers checked` |
| 6 | `Deployment review: a review aid, not an automatic approval` |
