"""Figure: what moved the real-arm success rate (README and video). Every count is from a committed artifact or the
public stress log, as listed in SOURCES. Stress counts are public operator-side totals. Per-cell stress results stay
sealed until stress v2 is complete. S4 is drawn only when --s4 k/n is given.
Usage: python scripts/fig_risk_magnitude.py <out.png> [--s4 k/n]"""
import sys, math
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return (c - h) / d, (c + h) / d

SOURCES = {
    "FP32\n(G6, pads)": (24, 25, "quant", "g6_analysis.json VC-000"),
    "INT8, 10 cells\n(G6, pads)": (194, 200, "quant", "g6_analysis.json, INT8 cells pooled"),
    "No pads\n(stress v1 S0)": (8, 24, "grip", "stress_operator_notes.md, public tally"),
    "Rubber bands\n(stress v2 S0)": (23, 24, "grip", "stress v2 consensus re-judge (protocol §11)"),
    "Start +3 cm\n(stress v2 S1)": (0, 3, "shift", "public log; stopped early by user"),
}
out = sys.argv[1]
if "--s4" in sys.argv:
    k, n = map(int, sys.argv[sys.argv.index("--s4") + 1].split("/")); SOURCES["Unseen can\n(stress v2 S4)"] = (k, n, "shift", "stress v2 re-judge")
col = {"quant": "#4C72B0", "grip": "#DD8452", "shift": "#C44E52"}
lab = {"quant": "precision (FP32 vs INT8)", "grip": "gripper friction", "shift": "distribution shift"}
fig, ax = plt.subplots(figsize=(9, 4.6), dpi=160)
for i, (name, (k, n, g, _)) in enumerate(SOURCES.items()):
    lo, hi = wilson(k, n); p = k / n
    ax.bar(i, p * 100, color=col[g], label=lab[g] if lab[g] not in ax.get_legend_handles_labels()[1] else None)
    ax.errorbar(i, p * 100, yerr=[[max(0, 100 * (p - lo))], [max(0, 100 * (hi - p))]], color="black", capsize=4, lw=1)
    ax.text(i, 3, f"{k}/{n}", ha="center", color="white" if p > 0.1 else "black", fontsize=9, fontweight="bold")
ax.set_xticks(range(len(SOURCES))); ax.set_xticklabels(SOURCES.keys(), fontsize=8.5)
ax.set_ylabel("real-arm success (%), Wilson 95% CI"); ax.set_ylim(0, 105)
ax.set_title("What moved the success rate on the real SO-101 arm", fontsize=11)
ax.legend(fontsize=8, loc="upper right", frameon=False)
fig.text(0.01, 0.005, "Same arm and ACT policy. Precision: blinded, interleaved, pre-registered (G6). Gripper and shift blocks are separate "
         "sessions, not randomized against each other (observational).", fontsize=6.5, color="#555")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(out); print("written", out)
