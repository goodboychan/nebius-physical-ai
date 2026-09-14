import json, pandas as pd, pathlib
root = pathlib.Path("/data/so101_pickplace")
df = pd.read_parquet(root / "data/chunk-000/file-000.parquet")
print("컬럼:", list(df.columns))
print("행 수:", len(df))
print(df.head(3).to_string()[:600])
if "episode_index" in df:
    print("\n에피소드 수:", df.episode_index.nunique())
    print("에피소드별 길이(앞 5):", df.groupby("episode_index").size().head().tolist())
info = json.load(open(root / "meta/info.json"))
print("\nvideo_path 템플릿:", info.get("video_path"))
print("data_path 템플릿:", info.get("data_path"))
for k, v in info.get("features", {}).items():
    if k.startswith("observation.images"):
        print(f"  {k}: {v.get('shape')} info={v.get('info',{}).get('video.fps')}fps")
# 비디오 디코더 가용성
for mod in ("torchvision.io", "av", "cv2", "decord"):
    try:
        __import__(mod); print(f"  디코더 OK: {mod}")
    except Exception as e:
        print(f"  디코더 없음: {mod} ({type(e).__name__})")
