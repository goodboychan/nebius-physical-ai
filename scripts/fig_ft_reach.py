"""Figure: where the position fine-tune reaches (prereg §14, §16, §18). Success per condition, FT-FP16 against the old FP16
policy, with the pre-registered reading. Data: ft_analysis.json, ft3_analysis.json, ft4_analysis.json.
Usage: python scripts/fig_ft_reach.py artifacts/reports/figures/fig_ft_reach.png"""
import json, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
F = json.load(open("artifacts/reports/ft_analysis.json")); F3 = json.load(open("artifacts/reports/ft3_analysis.json")); G = json.load(open("artifacts/reports/ft4_analysis.json"))
P = F3["pooled_T0_T0R"]
rows = [("−6 cm\n(beyond demos)", G["T6M"]["test"]["ft"], G["T6M"]["test"]["old"], "improved"),
        ("−3 cm\n(held out)", F["T2"]["primary"]["ft"], F["T2"]["primary"]["old"], "improved"),
        ("0 cm\n(training mark,\nT0+T0R)", P["test_k_n"], P["ref_k_n"], "undecided"),
        ("+3 cm\n(held out)", F["T1"]["primary"]["ft"], F["T1"]["primary"]["old"], "improved"),
        ("+6 cm\n(beyond demos)", G["T6P"]["test"]["ft"], G["T6P"]["test"]["old"], "no gain shown"),
        ("yellow can\nat +3 cm", G["TYP"]["test"]["ft"], G["TYP"]["test"]["old"], "no gain shown")]
fig, ax = plt.subplots(figsize=(11, 5.2), dpi=160); w = 0.38
for i, (lab, ft, old, rd) in enumerate(rows):
    a, b = ft[0] / ft[1] * 100, old[0] / old[1] * 100
    ax.bar(i - w / 2, a, w, color="#00808c"); ax.bar(i + w / 2, b, w, color="#b8c2c4")
    ax.text(i - w / 2, a + 2, f"{ft[0]}/{ft[1]}", ha="center", fontsize=10, color="#00505a", fontweight="bold")
    ax.text(i + w / 2, b + 2, f"{old[0]}/{old[1]}", ha="center", fontsize=10, color="#505a5c")
    ax.text(i, 112, rd, ha="center", fontsize=10.5, color={"improved": "#00808c", "undecided": "#a87810", "no gain shown": "#a0322d"}[rd], fontweight="bold")
ax.set_xticks(range(len(rows))); ax.set_xticklabels([r[0] for r in rows], fontsize=10)
ax.set_ylim(0, 120); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_ylabel("success (%)")
ax.spines[["top", "right"]].set_visible(False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#00808c", label="fine-tuned (FT-FP16)"), Patch(color="#b8c2c4", label="old policy (FP16)")],
          loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, frameon=False, fontsize=10)
ax.set_title("Where the position fine-tune reaches (blinded, pre-registered; 12 vs 12, 24 vs 24 at the mark)", fontsize=12, loc="left")
fig.tight_layout(); fig.savefig(sys.argv[1]); print("wrote", sys.argv[1])
