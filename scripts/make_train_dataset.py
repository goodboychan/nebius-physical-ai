"""LOCK-1 manifest의 `train` 80개만 남긴 학습용 LeRobot 데이터셋을 만든다 (`IG-1`).
val·audit 에피소드는 학습 데이터셋 파일에 아예 들어가지 않는다. 정규화 통계도 train만으로 다시 계산한다.
사용: EDGEQ_REPO=<리포 경로> python make_train_dataset.py <원본> <출력>
녹화와 같은 PyAV(15, libsvtav1)가 필요해 Orin의 lerobot-env에서 돌린다(컨테이너의 PyAV 13은 AV1 인코딩 불가)."""
import json, os, sys
REPO = os.path.expanduser(os.environ.get("EDGEQ_REPO", "/repo"))
sys.path.insert(0, f"{REPO}/src")
from edgeqgate.splits import load_manifest, assert_allowed
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.datasets.dataset_tools import delete_episodes

src, dst = sys.argv[1:3]
m = load_manifest(f"{REPO}/artifacts/manifests/lock1_split_manifest.yaml")
print("manifest_hash", m.manifest_hash)
assert m.manifest_hash == "acf51781c3940f89e94b8573cff618818deeb128940f57aa00de6c654806401c"
train = assert_allowed(m, m.ids("train"), "policy_training")
keep = sorted(int(e[2:]) for e in train)
drop = sorted(set(range(m.n_episodes)) - set(keep))
assert len(keep) == 80 and len(drop) == 40
ds = LeRobotDataset("local/so101_demo", root=src)
lengths = {int(r["episode_index"]): int(r["length"]) for r in ds.meta.episodes}
out = delete_episodes(ds, episode_indices=drop, output_dir=dst, repo_id="local/so101_train")
new_len = [int(r["length"]) for r in out.meta.episodes]
assert new_len == [lengths[i] for i in keep], "에피소드 길이 대응이 맞지 않는다"
json.dump({"manifest_hash": m.manifest_hash, "new_index_to_original": {i: f"ep{o:03d}" for i, o in enumerate(keep)}},
          open(os.path.join(dst, "meta", "lock1_mapping.json"), "w"), indent=1)
print("train dataset:", out.meta.total_episodes, "episodes,", out.meta.total_frames, "frames ->", dst)
