# Stress test — operator notes

Operator observations by block and trial number. The operator is blind to cells; these notes contain no cell information.
Gripper anti-slip pads are removed for the whole stress session (protocol §7).

## 2026-10-11

- S1 trial 1: success. Run before S0 (order deviation, decision_log 2026-10-11)
- S0 trial 1: success
- S0 trial 2: **failure** — not a slip. The gripper set the can down tilted while placing and it fell over
- S0 trial 5: **failure** — dropped the can while carrying it (during transport, not while placing)
- Operator remark after trial 5: the pad removal seems to matter
- S0 trials 6–16 (public tally after 16: 6 successes, 10 failures). Operator: **most failures are the can slipping out
  of the gripper**. Not every trial fails; successes still occur
- Cosmos end-of-trial answer: "Yes" on every trial up to 15, first "NO" on trial 16 (a failure)
- S0 trials 17–24 done. Final public tally S0 **8/24**. The stop rule fired, so stress v1 ends here
- Next (v2): rubber bands on the gripper fingers to raise friction

## 2026-10-11/12 — v2 (rubber bands on the gripper)

- S0 trials 1–6: the can was standing on the coaster in every trial, but the live screen showed failures for 3, 5 and
  6. This was a judge artifact (protocol §9); the offline re-judge gives 6/6
- S0 trial 7: success. S0 trial 8: live "moving" (judge artifact type, operator did not report a failure)
- S0 trial 9: **real failure** (operator): dropped the can while carrying it. Live judge: can top not found (fallen). Cosmos answered "No"
- S0 v2 complete (24). Operator: every trial except 9 succeeded
- Re-judge (§9): 22/24. Failures: 9 (real, dropped while carrying) and **19**. In 19 the operator saw a success, but the
  detector jumped to the same spurious circle near (399, 365) in 6 of the 15 frames, above the ≤ 3 limit. Under the
  fixed rule 19 is a failure. This is reported as a known judge false negative, and the rule is not changed again.
  Live screen: 16 trials showed "moving"
- S1 v2 trials 1–2: failures. Operator: the gripper first reaches for the **training start position** (as in S0),
  misses, then re-positions toward the shifted can and tries to grasp again. Both trials ended with the can not
  standing (live judge: can top not found)
- S1 v2 trial 1 detail: the first grasp closed on empty air at the training position. On the re-grasp attempt the
  gripper hit the can and knocked it over
- S1 v2 stopped by the user after trial 2 (decision_log 2026-10-12). Next: S4 can measurement, then S4
- S1 v2 trial 3 (in progress when S1 was stopped) is recorded and included
- S4 v2 trials 1–11 (2026-10-12): operator saw **no failures**. The live screen showed "moving" on 1, 4, 9 and 11
  (judge-artifact type, to be re-judged). Session paused here; S4 resumes at trial 12 on another day
