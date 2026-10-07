"""Nebius Jobs 감사 점수 잡 (`G4`, §5.3). 작업 단위 = 셀 하나. S3 볼륨의 상태별 점수 벡터(mag, align)에서
점추정(CVaR@90)과 결정적 부트스트랩 200회를 낸다. GPU 불필요. 결과는 stdout `AUDIT_RESULT <json>`과 S3 json.
env: CELLS(쉼표 구분), PAYLOAD_DIR, OUT_DIR, AUDIT_SEED, N_REPLICATES"""
import json, os, sys, time
import numpy as np
sys.path.insert(0, "/app")
from edgeqgate.scores import upper_tail_stat
from edgeqgate.audit_buffer import bootstrap_indices

SEED = os.environ.get("AUDIT_SEED", "PREREG-SEED-2026-09-14"); N_REP = int(os.environ.get("N_REPLICATES", "200"))
os.makedirs(os.environ["OUT_DIR"], exist_ok=True)
for cell in os.environ["CELLS"].split(","):
    t0 = time.time(); z = np.load(f"{os.environ['PAYLOAD_DIR']}/{cell}.npz")
    out = {"cell": cell, "seed": SEED, "n_replicates": N_REP, "host": os.uname().nodename}
    for name in ("mag", "align"):
        v = z[name].astype(np.float64); n = len(v)
        boot = np.array([upper_tail_stat(v[bootstrap_indices(n, r, SEED)]) for r in range(N_REP)])
        out[f"score_{name}"] = {"point": upper_tail_stat(v), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                                "boot_sd": float(boot.std(ddof=1)), "n_states": n}
    out["compute_sec"] = round(time.time() - t0, 3)
    json.dump(out, open(f"{os.environ['OUT_DIR']}/{cell}.json", "w"), indent=1)
    print("AUDIT_RESULT " + json.dumps(out), flush=True)
