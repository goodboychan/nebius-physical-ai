"""On the Orin: build ~/.edgeqgate_sealed/stress_ft6/engines for amendment 9 (§21). FT-FP16 tokens hard-link the FT engine from the
sealed stress_ft folder (with its normalization file); FT2-FP16 tokens hard-link ~/edgeqgate/ft2/engines/FT2-FP16.engine, whose
sha256 and normalization file must match the recorded build. Writes norm_manifest.json and prints counts and hashes only, never the
token-to-cell mapping. Usage: python3 ft6_setup_orin.py"""
import hashlib, json, os, shutil
S = os.path.expanduser("~/.edgeqgate_sealed"); A, B = f"{S}/stress_ft", f"{S}/stress_ft6"; F2 = os.path.expanduser("~/edgeqgate/ft2/engines")
FT2_ENGINE, FT2_NORM = "cea6c0e367fce70c752eb855ad9253cfe57f5ba93759123744ebee49a9a29e84", "c79d64afc49fb2cd"
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
old = json.load(open(f"{A}/stress_sealed.json"))["token_to_cell"]; new = json.load(open(f"{B}/stress_sealed.json"))["token_to_cell"]
oman = json.load(open(f"{A}/engines/norm_manifest.json")); cell_tok = {c: t for t, c in old.items()}
assert sha(f"{F2}/FT2-FP16.engine") == FT2_ENGINE and sha(f"{F2}/norm_stats.npz").startswith(FT2_NORM)
os.makedirs(f"{B}/engines", exist_ok=True); man = {}
for t, c in new.items():
    if c == "FT-FP16":
        o = cell_tok[c]; src, nf = f"{A}/engines/{o}.engine", f"{A}/engines/{oman[o]['file']}"; assert sha(nf) == oman[o]["sha256"]
    else:
        assert c == "FT2-FP16"; src, nf = f"{F2}/FT2-FP16.engine", f"{F2}/norm_stats.npz"
    dst = f"{B}/engines/{t}.engine"
    if not os.path.exists(dst): os.link(src, dst)
    assert sha(dst) == sha(src)
    shutil.copy(nf, f"{B}/engines/{t}.norm_stats.npz"); man[t] = {"file": f"{t}.norm_stats.npz", "sha256": sha(f"{B}/engines/{t}.norm_stats.npz")}
json.dump(man, open(f"{B}/engines/norm_manifest.json", "w"), indent=1)
print("engines linked:", len(new), "| engine sha256 (sorted):", sorted(sha(f"{B}/engines/{t}.engine")[:8] for t in new),
      "| manifest sha256:", sha(f"{B}/engines/norm_manifest.json")[:16])
