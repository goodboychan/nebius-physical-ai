# What one QuantGate review cost

From committed records (`scripts/review_cost.py`). List prices, on demand, checked 2026-10-15.

| Item | Use | Cost (USD) |
|---|---|---|
| Nebius Jobs · training (L40S) | 2 jobs · 2.45 h running, 2.51 h incl. provisioning | 3.88 |
| Nebius Jobs · smoke tests (L40S) | 4 jobs · 0.09 h running, 0.28 h incl. provisioning | 0.43 |
| Nebius Jobs · offline audit fan-out (CPU) | 48 jobs · 0.03 h running, 2.60 h incl. provisioning | 0.16 |
| Nebius AI Endpoint · Cosmos-Reason2 (L40S) | 11 sessions · 16.5 h up | 25.59 |
| Nebius Token Factory · Nemotron 3 Super | 69 calls · 166k in / 88k out tokens (7 estimated; a lower bound, since early report runs did not log usage) | 0.13 |
| Nebius Managed MLflow | 1.5 h | 0.72 |
| **Cloud total** | | **30.90** |

Real arm: **505 trials** in 10 sessions, **12.5 h** of operator time (about 1.5 min per trial).

For scale, not as a saving: settling approval for every candidate (25 candidates and FP32 at about 115 trials per arm) would be **2,990 trials, about 74 arm-hours**, before any stress or position test. The two numbers answer different goals, because this review did not settle approval.

What the 481 trials produced: a cost-favoured candidate to validate first (FP16), two miscalibrated builds blocked at the input check, two weak conditions found (grip, start position), the position weakness fixed and re-tested (+75 pp and +67 pp at ±3 cm), an AI judge validated live (22/24), and a list of the trials still missing before approval. It did not settle approval; that still needs the trials it lists.
