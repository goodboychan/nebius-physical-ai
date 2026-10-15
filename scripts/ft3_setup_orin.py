"""On the Orin: build ~/.edgeqgate_sealed/stress_ft3/engines from the sealed T1/T0 folder (amendment 6, §15).
For each new T0R token it hard-links the engine of the same cell from stress_ft/engines, copies that cell's normalization
file, and writes a new norm_manifest.json. It prints counts and hashes only, never the token-to-cell mapping.
Usage: python3 ft3_setup_orin.py"""
import hashlib, json, os, shutil
S = os.path.expanduser("~/.edgeqgate_sealed"); A, B = f"{S}/stress_ft", f"{S}/stress_ft3"
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
old = json.load(open(f"{A}/stress_sealed.json"))["token_to_cell"]; new = json.load(open(f"{B}/stress_sealed.json"))["token_to_cell"]
oman = json.load(open(f"{A}/engines/norm_manifest.json"))
cell_tok = {c: t for t, c in old.items()}
os.makedirs(f"{B}/engines", exist_ok=True); man = {}
for t, c in new.items():
    o = cell_tok[c]; src = f"{A}/engines/{o}.engine"; dst = f"{B}/engines/{t}.engine"
    if not os.path.exists(dst): os.link(src, dst)
    nf = f"{A}/engines/{oman[o]['file']}"; assert sha(nf) == oman[o]["sha256"]
    shutil.copy(nf, f"{B}/engines/{t}.norm_stats.npz"); man[t] = {"file": f"{t}.norm_stats.npz", "sha256": sha(f"{B}/engines/{t}.norm_stats.npz")}
    assert sha(dst) == sha(src)
json.dump(man, open(f"{B}/engines/norm_manifest.json", "w"), indent=1)
print("T0R engines linked:", len(new), "| engine sha256 (sorted):", sorted(sha(f"{B}/engines/{t}.engine")[:8] for t in new),
      "| manifest sha256:", sha(f"{B}/engines/norm_manifest.json")[:16])
