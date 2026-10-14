"""Figures for the D3 v2 report and the dashboard Report section, drawn by code from `d3_v2_verdicts.json`, so they
always match the verdicts. The model never draws or edits them.
  fig_e1_forest.png    success comparison vs FP32 per candidate/context: Newcombe CI and the 10 pp tolerance
  fig_cost_evidence.png on-device GPU time (trtexec) vs real-arm success with a Wilson 95% CI, coloured by verdict
  fig_frames.png       the final overhead frames behind two verdict examples (one success, one failure), with the
                       criterion outcome and Cosmos's answer
  fig_ft_position.png  position fine-tune: success of FT vs OLD at -3, 0 and +3 cm with Wilson 95% intervals (§14)
Usage: python scripts/d3_figures.py <verdicts.json> <out dir>"""
import json, math, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

COL = {"GO": "#2E6B4F", "NO-GO": "#99332F", "INSUFFICIENT_EVIDENCE": "#8C6A15", "FLAGGED": "#99332F"}

def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return (c - h) / d, (c + h) / d

def forest(T, out):
    rows = [r for r in T["rows"] if r.get("e1_ci_pp") and r["candidate"] != "FT-FP16"]   # FT rows are FT-vs-OLD improvements: own figure
    fig, ax = plt.subplots(figsize=(8, 0.34 * len(rows) + 1.3), dpi=150)
    for i, r in enumerate(rows):
        lo, hi = r["e1_ci_pp"]; y = len(rows) - 1 - i; c = COL[r["verdict"]]
        ax.plot([lo, hi], [y, y], color=c, lw=2.2, solid_capstyle="round")
        k, n = r["success"]; kr, nr = r["reference"]; d = (kr / nr - k / n) * 100
        ax.plot([d], [y], "s", color=c, ms=5)
        ax.text(57, y, f"{k}/{n} vs {kr}/{nr}", va="center", fontsize=7.5, color="#3C464E")
    ax.axvline(0, color="#5A646C", lw=0.8); ax.axvline(10, color="#99332F", lw=1, ls="--")
    ax.text(10.5, len(rows) - 0.4, "10 pp tolerance", color="#99332F", fontsize=7.5)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([f"{r['candidate']} · {r['context']}" for r in rows][::-1], fontsize=7.5)
    ax.set_xlim(-45, 75); ax.set_xlabel("success degradation vs FP32 (pp), Newcombe CI", fontsize=8)
    ax.set_title("GO needs the whole interval left of the dashed line; every interval crosses it", fontsize=9)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{out}/fig_e1_forest.png"); plt.close(fig)

def cost_evidence(T, out):
    pts = {}
    for r in T["rows"]:
        if r.get("gpu_ms_trtexec") and r.get("success") and r["context"].startswith(("G6", "FP16")): pts[r["candidate"]] = r
    g6ref = next(r for r in T["rows"] if r["context"].startswith("G6"))["reference"]
    pts["VC-000"] = {"success": g6ref, "gpu_ms_trtexec": 53.4, "verdict": "REF", "context": "G6 FP32 reference"}
    jitter = {"VC-002": -0.7, "VC-020": 0.0, "VC-005": 0.7}; lab = {"VC-025": (6, -18), "VC-002": (-30, 14), "VC-020": (10, 6), "VC-005": (8, -14)}
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=150)
    for c, r in pts.items():
        k, n = r["success"]; lo, hi = wilson(k, n); p = k / n; x = r["gpu_ms_trtexec"] + jitter.get(c, 0)
        col = COL.get(r["verdict"], "#5A646C")
        ax.errorbar(x, p * 100, yerr=[[max(0, (p - lo) * 100)], [max(0, (hi - p) * 100)]], fmt="o", color=col, capsize=3)
        ax.annotate(f"{c} {k}/{n}", (x, p * 100), textcoords="offset points", xytext=lab.get(c, (8, -4)), fontsize=7.5)
    ax.set_xlim(5, 62); ax.set_ylim(55, 103); ax.set_xlabel("GPU time per chunk on Jetson Orin Nano Super (ms, trtexec)", fontsize=8)
    ax.set_ylabel("real-arm success (%), Wilson 95%", fontsize=8)
    ax.set_title("Cheaper is to the left; success intervals overlap, so approval stays on hold", fontsize=9)
    ax.text(6, 57, "FP16: its own block (rubber bands). INT8 and FP32: G6 (pads). Grey = FP32 reference.", fontsize=6.5, color="#5A646C")
    for s_ in ("top", "right"): ax.spines[s_].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{out}/fig_cost_evidence.png"); plt.close(fig)

def frames(out, clips="dashboard/clips"):
    import av
    def last(p):
        c = av.open(p); f = None
        for f in c.decode(c.streams.video[0]): pass
        c.close(); return f.to_ndarray(format="rgb24")
    items = [("g6_success.mp4", "G6 trial 12: criterion SUCCESS"), ("g6_fail_knock.mp4", "G6 trial 186: criterion FAILURE · Cosmos answered \"Yes\"")]
    fig, axs = plt.subplots(1, 2, figsize=(8, 3.2), dpi=150)
    for ax, (f, t) in zip(axs, items):
        ax.imshow(last(os.path.join(clips, f))); ax.set_title(t, fontsize=8); ax.axis("off")
    fig.tight_layout(); fig.savefig(f"{out}/fig_frames.png"); plt.close(fig)

def ft_position(T, out):
    by = {}
    for r in T["rows"]:
        if r["candidate"] != "FT-FP16": continue
        pos = "+3 cm" if "+3" in r["context"] else ("-3 cm" if "-3" in r["context"] else "0 cm (training mark)")
        by[pos] = r
    if not by: return False
    order = [k for k in ("-3 cm", "0 cm (training mark)", "+3 cm") if k in by]
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=150)
    for i, k in enumerate(order):
        r = by[k]
        for j, (lab, (kk, nn), col) in enumerate((("old policy", r["reference"], "#8A9492"), ("fine-tuned", r["success"], "#00909B"))):
            x = i + (j - 0.5) * 0.34; p = kk / nn; lo, hi = wilson(kk, nn)
            ax.bar(x, p, width=0.32, color=col, label=lab if i == 0 else None)
            ax.errorbar(x, p, yerr=[[max(p - lo, 0)], [max(hi - p, 0)]], color="#14181C", capsize=3, lw=1)
            ax.text(x, hi + 0.03, f"{kk}/{nn}", ha="center", fontsize=8)
        ax.text(i, -0.2, r["verdict"].replace("_", " ").lower(), ha="center", fontsize=7.5, color="#3C464E")
    ax.set_xticks(range(len(order))); ax.set_xticklabels([f"start {k}" for k in order], fontsize=8.5)
    ax.set_ylim(-0.25, 1.18); ax.set_yticks([0, 0.5, 1]); ax.set_yticklabels(["0%", "50%", "100%"], fontsize=8)
    ax.set_ylabel("real-arm success", fontsize=8.5); ax.legend(fontsize=8, frameon=False, loc="upper center", ncol=2)
    ax.set_title("Position fine-tune, blinded and interleaved, 12 vs 12 per position (Wilson 95%)", fontsize=9)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{out}/fig_ft_position.png"); plt.close(fig); return True

def make_all(T, out):
    os.makedirs(out, exist_ok=True); forest(T, out); cost_evidence(T, out); frames(out)
    return ["fig_e1_forest.png", "fig_cost_evidence.png", "fig_frames.png"] + (["fig_ft_position.png"] if ft_position(T, out) else [])

if __name__ == "__main__":
    print(make_all(json.load(open(sys.argv[1])), sys.argv[2]))
