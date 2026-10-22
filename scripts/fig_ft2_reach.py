"""Figure: the fine-tune's reach (prereg §14, §16, §18) and fine-tune v2 (§21-22). Left: FT-FP16 against the old FP16 policy per
condition, with the pre-registered reading. Right: FT2-FP16 against FT-FP16 in the amendment 9 session. The two panels are
separate sessions and are not pooled. Data: ft_analysis.json, ft3_analysis.json, ft4_analysis.json, ft6_analysis.json.
Usage: python scripts/fig_ft2_reach.py artifacts/reports/figures/fig_ft2_reach.png"""
import json, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
F = json.load(open("artifacts/reports/ft_analysis.json")); F3 = json.load(open("artifacts/reports/ft3_analysis.json"))
G = json.load(open("artifacts/reports/ft4_analysis.json")); V = json.load(open("artifacts/reports/ft6_analysis.json")); P = F3["pooled_T0_T0R"]
C = {"improved": "#00808c", "undecided": "#a87810", "no gain shown": "#a0322d", "no drop": "#505a5c"}
left = [("−6 cm", G["T6M"]["test"]["ft"], G["T6M"]["test"]["old"], "improved"), ("−3 cm", F["T2"]["primary"]["ft"], F["T2"]["primary"]["old"], "improved"),
        ("0 cm\n(mark)", P["test_k_n"], P["ref_k_n"], "undecided"), ("+3 cm", F["T1"]["primary"]["ft"], F["T1"]["primary"]["old"], "improved"),
        ("+6 cm", G["T6P"]["test"]["ft"], G["T6P"]["test"]["old"], "no gain shown"), ("yellow can\n+3 cm", G["TYP"]["test"]["ft"], G["TYP"]["test"]["old"], "no gain shown")]
right = [("yellow can\n+3 cm", V["TYP2"]["test"]["ft2"], V["TYP2"]["test"]["ft"], "improved"), ("+6 cm", V["T6P2"]["test"]["ft2"], V["T6P2"]["test"]["ft"], "improved"),
         ("0 cm\n(guard)", V["T0G"]["test"]["ft2"], V["T0G"]["test"]["ft"], "no drop")]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2), dpi=160, gridspec_kw={"width_ratios": [6, 3]}); w = 0.38
def panel(ax, rows, c1, c2, title):
    for i, (lab, x, y, rd) in enumerate(rows):
        a, b = x[0] / x[1] * 100, y[0] / y[1] * 100
        ax.bar(i - w / 2, a, w, color=c1); ax.bar(i + w / 2, b, w, color=c2)
        ax.text(i - w / 2, a + 2, f"{x[0]}/{x[1]}", ha="center", fontsize=9.5, fontweight="bold"); ax.text(i + w / 2, b + 2, f"{y[0]}/{y[1]}", ha="center", fontsize=9.5, color="#505a5c")
        ax.text(i, 112, rd, ha="center", fontsize=10, color=C[rd], fontweight="bold")
    ax.set_xticks(range(len(rows))); ax.set_xticklabels([r[0] for r in rows], fontsize=10); ax.set_ylim(0, 120); ax.set_yticks([0, 25, 50, 75, 100])
    ax.spines[["top", "right"]].set_visible(False); ax.set_title(title, fontsize=11.5, loc="left")
panel(a1, left, "#00808c", "#b8c2c4", "First fine-tune vs old policy (blinded, 12 vs 12; 24 vs 24 at the mark)")
panel(a2, right, "#6B4C9A", "#00808c", "Fine-tune v2 vs first fine-tune (one session)")
a1.set_ylabel("success (%)"); a2.set_yticklabels([])
fig.legend(handles=[Patch(color="#6B4C9A", label="fine-tune v2 (FT2-FP16)"), Patch(color="#00808c", label="first fine-tune (FT-FP16)"), Patch(color="#b8c2c4", label="old policy (FP16)")],
           loc="lower center", ncol=3, frameon=False, fontsize=10)
fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(sys.argv[1]); print("wrote", sys.argv[1])
