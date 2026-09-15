"""Nebius Jobs에서 도는 감사 점수 잡 (§5.3).

구조: 작업 단위는 (variant cell)이다. **(cell x replicate)가 아니다.**
부트스트랩 replicate는 같은 오차 벡터 위의 재표집이므로 한 잡 안에서 200번 돈다.
attempt-007 실측: 잡당 오버헤드 261s. 5,200잡이면 약 35시간, 26잡이면 수 분이다.

GPU도 TensorRT도 필요 없다. 추론은 배포 대상(Jetson)에서 이미 끝났고,
이 잡은 그 결과인 오차 벡터 위에서 통계만 낸다.
"""
import base64, json, os, sys, time, zlib
import numpy as np

sys.path.insert(0, "/app")
from edgeqgate.scores import score_mag, score_align, diagnostics
from edgeqgate.audit_buffer import bootstrap_indices

CELL = os.environ["CELL"]
SEED = os.environ.get("AUDIT_SEED", "PREREG-SEED-2026-09-14")
N_REP = int(os.environ.get("N_REPLICATES", "200"))


def main():
    t0 = time.time()
    payload = json.load(open("/app/payload.json"))
    if CELL not in payload:
        print(json.dumps({"cell": CELL, "error": f"페이로드에 {CELL} 없음",
                          "available": sorted(payload)}))
        return 1
    p = payload[CELL]
    raw = zlib.decompress(base64.b64decode(p["b64_zlib"]))
    err = np.frombuffer(raw, dtype=np.dtype(p["dtype"])).reshape(p["shape"]).astype(np.float64)
    n = err.shape[0]

    point = score_mag(err, cell=CELL)

    # 부트스트랩: replicate 번호에서 결정적으로 인덱스를 만든다.
    # 잡이 중단되어 재실행돼도, 잡을 묶든 나누든 같은 값이 나온다 (preemptible 안전).
    vals = []
    for r in range(N_REP):
        idx = bootstrap_indices(n, r, SEED)
        vals.append(score_mag(err[idx], cell=CELL, replicate=r).value)
    v = np.asarray(vals)

    out = {
        "cell": CELL, "seed": SEED, "n_states": int(n), "n_replicates": N_REP,
        "score_mag_point": point.value,
        "score_mag_ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))],
        "score_mag_boot_mean": float(v.mean()), "score_mag_boot_sd": float(v.std(ddof=1)),
        "diagnostics": point.diag,
        "compute_sec": round(time.time() - t0, 3),
        "env": {"python": sys.version.split()[0], "numpy": np.__version__,
                "hostname": os.uname().nodename},
    }
    print("AUDIT_RESULT " + json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
