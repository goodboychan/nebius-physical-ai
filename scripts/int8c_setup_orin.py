"""On the Orin: build ~/.edgeqgate_sealed/stress_int8c/engines from the sealed FP16-block folder (amendment 3, fp16 prereg §9).
For each new Q8 token it hard-links the engine of the same cell (VC-002 or VC-025) from stress_fp16/engines, copies that
folder's normalization file (both cells are the original policy) and writes a norm_manifest.json, which the runner requires.
It prints counts and hashes only, never the token-to-cell mapping.
Usage: python3 int8c_setup_orin.py"""
import hashlib, json, os, shutil
S = os.path.expanduser("~/.edgeqgate_sealed"); A, B = f"{S}/stress_fp16", f"{S}/stress_int8c"
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
old = json.load(open(f"{A}/stress_sealed.json"))["token_to_cell"]; new = json.load(open(f"{B}/stress_sealed.json"))["token_to_cell"]
cell_tok = {c: t for t, c in old.items()}
os.makedirs(f"{B}/engines", exist_ok=True); man = {}
for t, c in new.items():
    src = f"{A}/engines/{cell_tok[c]}.engine"; dst = f"{B}/engines/{t}.engine"
    if not os.path.exists(dst): os.link(src, dst)
    shutil.copy(f"{A}/engines/norm_stats.npz", f"{B}/engines/{t}.norm_stats.npz")
    man[t] = {"file": f"{t}.norm_stats.npz", "sha256": sha(f"{B}/engines/{t}.norm_stats.npz")}
    assert sha(dst) == sha(src)
json.dump(man, open(f"{B}/engines/norm_manifest.json", "w"), indent=1)
print("Q8 engines linked:", len(new), "| engine sha256 (sorted):", sorted(sha(f"{B}/engines/{t}.engine")[:8] for t in new),
      "| norm sha256:", sorted({v["sha256"][:8] for v in man.values()}), "| manifest sha256:", sha(f"{B}/engines/norm_manifest.json")[:16])
