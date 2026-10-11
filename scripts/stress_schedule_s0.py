"""Stress protocol amendment 1 (docs/stress_test_protocol.md §7): add block S0 (nominal scene, gripper pads removed),
run before S1. The S1/S4 blocks and the anonymous tokens of v1 are kept unchanged; only the "S0" key is added.
Run on Orin (the sealed v1 file lives only there). Prints only hashes, never the token map.
Usage: python3 stress_schedule_s0.py <repo src dir>"""
import hashlib, json, os, sys
import numpy as np
sys.path.insert(0, sys.argv[1])
from edgeqgate.hashing import seed_from

D = os.path.expanduser("~/.edgeqgate_sealed/stress"); N = 6
sb1 = open(f"{D}/stress_sealed.json", "rb").read()
assert hashlib.sha256(sb1).hexdigest().startswith("9549b96b"), "sealed v1 changed"
S = json.loads(sb1); P = json.load(open(f"{D}/stress_schedule_public.json"))
assert "S0" not in S
rng = np.random.default_rng(seed_from("PREREG-SEED-2026-09-14", "STRESS/schedule/v1/amend1/S0", S["lock2_record_hash"]))
cells = sorted(S["token_to_cell"].values()); tok = {c: t for t, c in S["token_to_cell"].items()}
ts = [{"cell": c, "key": (k + rng.uniform()) / N} for c in cells for k in range(N)]
ts.sort(key=lambda t: (t["key"], rng.uniform()))
S["S0"] = [{"trial": i + 1, "cell": t["cell"]} for i, t in enumerate(ts)]
S["block_order"] = ["S0"] + S["block_order"]; S["amendment"] = "1: S0 added before S1 (gripper pads removed)"
sb2 = json.dumps(S, indent=1, sort_keys=True).encode()
open(f"{D}/stress_sealed.json.v1", "wb").write(sb1); open(f"{D}/stress_sealed.json", "wb").write(sb2)
P["S0"] = [{"trial": i + 1, "engine_token": tok[t["cell"]]} for i, t in enumerate(ts)]
P["block_order"] = S["block_order"]; P["sealed_sha256_v1"] = P["sealed_sha256"]; P["sealed_sha256"] = hashlib.sha256(sb2).hexdigest()
json.dump(P, open(f"{D}/stress_schedule_public.json", "w"), indent=1)
print("S0", len(ts), "sealed v2 sha256", P["sealed_sha256"])
