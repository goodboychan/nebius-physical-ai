## Inspiration

We had a robot policy that worked: an SO-101 arm picks up a cola can and stands it on a coaster, driven by a LeRobot
ACT (Action Chunking with Transformers) policy. Then we had to put it on a Jetson Orin Nano Super. That gave us
26 ways to ship the same checkpoint: FP32, FP16 and 24 INT8 builds that differ only in how they were calibrated.

Benchmarks told us speed, and open-loop metrics all looked fine. Neither told us whether the arm would still put the
can on the coaster, or how sure we could be. Same robot, same task: one run succeeds, one fails.

So we built the tool we wanted: a **deployment review** that puts cost, offline scores and real-arm evidence side by
side, and says plainly when the evidence is not enough.

## What it does

For every candidate engine, QuantGate answers three questions.

1. **Which candidate do I validate first?**
   - It measures cost on the target device itself (trtexec, 15 W): FP16 takes **11.6 ms and 82 mJ** per inference,
     INT8 16.8–17.1 ms and 101 mJ, FP32 53.4 ms and 403 mJ.
   - On this Jetson, FP16 is the fastest and the cheapest, not INT8.
2. **Which do I distrust?**
   - Broken calibrations: a deliberately black-frame-calibrated build is caught by a simple input check.
   - Builds that do not match what was audited: a preflight checks the engine hash, the normalization manifest and
     the runner's 200 ms chunk deadline. Only an explicit `GO` passes.
3. **Can I approve deployment?** Not yet, and the review says why.
   - Success against FP32 is compared as non-inferiority at a 10 pp tolerance, with a Newcombe interval. The
     **success criterion** is met when

     $$\text{lower bound of } \big(p_{\text{cand}} - p_{\text{FP32}}\big) > -10\ \text{pp}$$

   - That is one part of a final `GO`. A `GO` also needs placement error within its 5 px tolerance, the ceiling rule
     not holding the comparison undecided, and the deployment preflight passing.
   - With 25 trials per arm the success interval is about ±28 pp wide, so every comparison is
     `INSUFFICIENT_EVIDENCE`.
   - The review also says what would settle it. Our pre-registered ceiling rule keeps two arms that are both at or
     above 95% undecided at any sample size, so more trials alone are not enough. A revised, pre-registered rule is
     needed. Under it, about 120 trials per arm give 80% power **for the success criterion**; that is not the chance
     of a final GO.

A one-command CLI (`quantgate.py review | ask | preflight | cost | verify`) rebuilds the whole review from
committed, hashed evidence.

## How we built it

- **Data and training**:
  - 120 teleoperated demonstrations, recorded with LeRobot.
  - ACT (51.6M parameters, 100-step chunks) trained on **Nebius Jobs** with an L40S GPU.
  - 26 TensorRT engines built on the Jetson with a frozen timing cache, so the same file always behaves the same.
- **Offline audit**: 2,000 held-out states scored on 48 CPU jobs on Nebius Jobs. The ranking was frozen before any
  real trial.
- **Real arm**: **625 trials** in 14 sessions, all under sealed, interleaved schedules.
  - The operator saw trial numbers only. In the fine-tune blocks the two policies moved visibly differently, so
    operator blinding there was partial; outcomes come from an automatic judge and a blind video re-judge.
  - Logs are hashed before they are unsealed, so no rule can change after the results are seen.
  - The primary analyses were pre-registered. Rules set after aggregate results and post-hoc observations are
    labelled as such in the decision log.
- **AI layers on Nebius**:
  - **Cosmos-Reason2 on a Nebius AI Endpoint** judges the final frame of each trial.
  - **Nemotron 3 Super on Nebius Token Factory** explains the review in words.
  - Code writes every verdict and number. A validator rejects model text that contains digits, verdict labels or
    approval words.
- **Cost of one review**: about **\$31** of Nebius cloud.

## What we found

- **The offline audit did not predict the arm.**
  - Its top-ranked INT8 cells went 73/75, and randomly picked cells also went 73/75.
  - The offline rank did not track placement error either (Spearman 0.02–0.08).
- **The risk was in the deployment conditions, not the precision.**
  - Removing the gripper's anti-slip pads dropped success to 8/24.
  - Moving the start 3 cm gave 0/3.
- **We fixed the weakness with data and re-tested it under a rule fixed in advance.**
  - 50 new demonstrations at −4…+4 cm and a 25-minute fine-tune on Nebius Jobs.
  - At held-out positions: **12/12 vs 3/12 at +3 cm** (+75 pp, 95% CI [+38, +91]) and **10/12 vs 2/12 at −3 cm**.
  - We then mapped how far the fix reaches, under a new pre-registration: **8/12 vs 0/12 at −6 cm**, beyond the
    demonstrations, but **0/12 vs 0/12 at +6 cm** and **0/12 vs 3/12 with a smaller yellow can at +3 cm**. The review
    now states the range where the fine-tune is a candidate, and where it is not.
  - At the trained spot it is still undecided (22/24 vs 23/24, with a pre-registered replication), so the review
    does not approve it there.

## Challenges we ran into

- **Our own AI judge was wrong at first.**
  - Cosmos caught 1 of 21 failures with a one-word prompt. A validated prompt caught 20/21 on held-out recordings.
  - It then held up live on 96 new trials: 22/24 failures caught, 2/72 false alarms.
  - We learned to treat the judge as a component to test, not an oracle.
- **INT8 was slower than FP16 on this device.** That contradicts the usual assumption, and only on-device
  measurement showed it.
- **Small samples.** Honest intervals at 12–25 trials are wide. We had to design the review to say "not yet" instead
  of overclaiming.
- **Blinding a visible fix.** The fine-tuned policy moves visibly differently, so operator blinding was partial.
  Outcomes come from an automatic judge and a blind video re-judge, which agree.
- **Hardware is the unglamorous failure mode**: empty episodes, voltage errors and gripper friction. Each became a
  recorded deployment condition.

## What we learned

- Measure cost on the target device. The precision name does not tell you the cost.
- "No failure observed" is not safety evidence. A review should say how far the evidence goes.
- An AI supervisor or judge is a part to validate, with held-out data, before trusting it.
- Pre-registration and sealing are cheap, and they make every number defensible.

## What's next

- On-policy audit and distillation from the 500+ logged rollouts.
- Hailo-8, which today misses the 200 ms deadline and is blocked by the preflight, in a shadow-mode run.
- The same review on an Isaac Sim twin of this task for thousands of closed-loop trials. The twin is calibrated to
  the real arm on a GB10 desktop, and its candidates would be re-checked on the real arm.

**Earn the next test, not the approval.**
