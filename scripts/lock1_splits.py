"""`LOCK-1` — 데모 120개의 분할 확정 (§3.2). 이후 정책 학습 시작.

시드는 9/14부터 커밋돼 있던 `PREREG-SEED-2026-09-14`. 에피소드 id는 LeRobot episode_index를 `ep000` 형식으로.
데이터셋 파일 전체의 SHA-256을 함께 기록해, 분할이 가리키는 데이터가 나중에 바뀌지 않았음을 확인할 수 있게 한다.
사용: python scripts/lock1_splits.py <데이터셋 경로>"""
import glob, hashlib, json, os, sys
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from edgeqgate.splits import determine_splits, write_manifest
from edgeqgate.hashing import hash_obj

SEED = "PREREG-SEED-2026-09-14"
root = os.path.expanduser(sys.argv[1])
files = {}
for p in sorted(glob.glob(f"{root}/**/*", recursive=True)):
    if os.path.isfile(p):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
        files[os.path.relpath(p, root)] = h.hexdigest()
ds_hash = hash_obj(files)
e = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{root}/meta/episodes/chunk-*/file-*.parquet"))])
idx = sorted(int(i) for i in e["episode_index"])
assert idx == list(range(120)), f"에피소드가 0..119가 아니다: {len(idx)}개"
m = determine_splits([f"ep{i:03d}" for i in idx], seed=SEED)
m.notes.append(f"dataset so101_demo (LeRobot v3.0, 2026-10-06~07 수집), files sha256 hash_obj = {ds_hash}")
m.notes.append("과제: 콜라캔 268g을 시작 표시에서 집어 컵받침 위에 세우기 (사전등록 §2.1 2026-10-06 개정)")
h = write_manifest(m, "artifacts/manifests/lock1_split_manifest.yaml")
json.dump({"dataset_root": "so101_demo", "dataset_hash": ds_hash, "files": files},
          open("artifacts/manifests/lock1_dataset_files.json", "w"), indent=1)
print("manifest_hash", h)
print("dataset_hash", ds_hash)
for k, v in m.assignment.items(): print(k, len(v), v[:6], "...")
