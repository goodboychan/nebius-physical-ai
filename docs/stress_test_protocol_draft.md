# Stress test protocol — DRAFT (not locked, not run)

Status: draft for the user's decisions, 2026-10-10. It is locked (hash committed) before the first stress trial and
after QuantGate `LOCK-3`. It does not change any G6 analysis.

## Why

G2 FP32 was 20/20 and G6 is 135/136 so far (aggregate). The nominal task is near ceiling, so binary success may not
separate artifacts (`K2` risk, AEP ceiling rule). Quantization error often shows up when the input moves away from the
training distribution. The stress test asks:

> Under conditions the policy never saw in its demonstrations, do the worst-fidelity INT8 artifacts degrade more
> than the best-fidelity INT8 artifact and the FP32 reference?

## Artifacts (fixed from LOCK-2, no new builds)

| Role | Cell | Why |
|---|---|---|
| reference | `VC-000` (Orin FP32 engine) | same as G6 `ARM-FP32` |
| best fidelity | `VC-002` | top of `score_align` and `score_mag` |
| worst fidelity | `VC-005` | bottom of both |
| (optional) practical default | `VC-020` | top of `score_cheap_A` (calib 1024, per-channel) |

## Conditions (choose 1–2)

| Code | Change | Effort | Expected effect |
|---|---|---|---|
| S1 | Can start spot shifted **3 cm** sideways (new tape mark), same orientation | tape only | the grasp approach has to generalize — failure 49 showed that the policy does not recover from a displaced can |
| S2 | Can start spot shifted **5 cm** toward the arm base | tape only | stronger shift, more failures |
| S3 | Room lighting changed (blinds open in daytime, or one lamp off), camera settings stay locked | none | image brightness and white balance out of distribution |
| S4 | Different can (beer can, 66 mm, filled with rice to about 268 g) | can prep | object appearance and size out of distribution |

**Chosen (user, 2026-10-10): S1 + S4.** S3 dropped — opening the window does not change the light enough in this room.
S4 needs a judge recalibration for the new can before any stress trial: the top-to-base perspective offset (0, +32) px
and the top-circle radius range (17–28 px) were measured for the cola can's height and lid. Measure both with the new can
standing centered on the empty coaster, then lock them in this protocol. This is a measurement made before any policy outcome.

## Size and order

- 3 artifacts × 2 conditions × **12 trials** = 72 trials (about 1.5 h). With the optional 4th artifact: 96.
- Blocks are run by condition (the scene has to be changed physically). Within a block, artifacts are interleaved from
  a committed seed, and the operator is blinded (same runner, sealed tokens).
- The execution settings are the same as G6: 30 Hz, chunk 100, prefetch 10 + blend 4, 60 s.

## Endpoints and decisions (same semantics as `docs/aep_physical_registration_v1.md`)

- E1 binary success (`docs/success_criterion.md`, unchanged). E2 placement error (px).
- Primary per condition: worst (`VC-005`) vs best (`VC-002`). Degradation = best − worst for E1 and worst − best for
  E2. Tolerances: E1 10 pp, E2 5 px. Unpaired bootstrap, 10,000 draws, family = 2 conditions × 2 endpoints,
  Bonferroni.
- Secondary: each INT8 artifact vs `VC-000` per condition.
- `falsified_if` (for the AEP-direction claim in this regime): `materially_degraded` on either endpoint in either
  condition.
- The ceiling rule applies as in the AEP registration.

## D4 supervisor

Shadow mode, as in G6, so that the outcome is not affected. Record whether Cosmos flags failures (EX-3). Optional
add-on: ask one end-of-trial question ("Is the can standing on the coaster?") and compare it with the judge (AI-judge
agreement, the first step toward RLAIF). It is descriptive only.

## Decisions needed

1. Conditions: **S1 + S4 (decided)**. S4 can: unopened, ≤ 66 mm diameter, ≤ 400 g, clearly different appearance — to be chosen
2. Include the optional 4th artifact `VC-020`? (+24 trials)
3. 12 trials per artifact per condition (recommended) or 10 / 15.
4. Add the end-of-trial AI-judge question? (recommended: yes, descriptive)
