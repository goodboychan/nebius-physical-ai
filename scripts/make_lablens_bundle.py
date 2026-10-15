"""Episode bundle for LabLens (an internal-hackathon tool that investigates recorded robot episodes).
Policy rollouts (real arm, QuantGate trials) with outcome labels and operator notes, plus two teleoperated demos.
One folder per episode: video (H.264 copy + original AV1), trajectory (parquet + csv), episode.json.
Usage: <venv with av, pandas, pyarrow> python scripts/make_lablens_bundle.py <raw dir> <pick.txt> <out dir>"""
import glob, json, os, shutil, sys
import av, numpy as np, pandas as pd
from PIL import Image

RAW, PICK, OUT = sys.argv[1:4]; os.makedirs(OUT, exist_ok=True)
J = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
CELL = {"VC-000": "FP32 (old policy)", "VC-002": "INT8, ModelOpt per-channel, 16 calibration frames (old policy)",
        "VC-020": "INT8, ModelOpt per-channel, 1024 calibration frames (old policy)", "VC-025": "FP16 (old policy)",
        "FT-FP16": "FP16, position-fine-tuned policy", "PC-B": "INT8 deliberately miscalibrated on black frames (positive control)"}
BLOCK = {"stress_ft_T1": ("Position fine-tune evaluation T1", "start +3 cm (not in training)", "rubber-band gripper"),
         "stress_ft_T0": ("Position fine-tune evaluation T0", "training start mark", "rubber-band gripper"),
         "stress_ft2_T2": ("Position fine-tune evaluation T2", "start -3 cm (not in training)", "rubber-band gripper"),
         "stress_pc_P0": ("Positive-control block", "training start mark", "rubber-band gripper"),
         "g6_main": ("G6 main study", "training start mark", "anti-slip pads on the gripper"),
         "stress_S0": ("Stress test v1, S0", "training start mark", "gripper pads removed")}
NOTES = {"T1002_1014_214044": "Can ended half on the coaster (tilted on the coaster edge); the arm kept moving.",
         "T1006_1014_214600": "Can ended half on the coaster.",
         "T2012_1014_231614": "The can was set down properly, then the gripper kept moving nearby and knocked it over.",
         "T2014_1014_231845": "The can was never grasped.",
         "T0018_1014_223141": "The can did not fall but was pushed far off the coaster.",
         "T0022_1014_223628": "The can was knocked over while being set down.",
         "P0016_1013_214101": "The grasp was off, and the can dropped while being carried.",
         "P0021_1013_214651": "The can was placed on the coaster and the arm went back; then it came back to the coaster and knocked the can over.",
         "main186_1010_221517": "The can was placed, then the gripper tipped it over while pulling back (overhead review).",
         "S0005_1011_223252": "Gripper pads removed; the can dropped while being carried (overhead review)."}
SEALED = {"stress_ft_T1": "artifacts/trials/ft_unsealed/stress_ft_T1_sealed.jsonl", "stress_ft_T0": "artifacts/trials/ft_unsealed/stress_ft_T0_sealed.jsonl",
          "stress_ft2_T2": "artifacts/trials/ft2_unsealed/stress_ft2_T2_sealed.jsonl", "stress_pc_P0": "artifacts/trials/pc_unsealed/stress_pc_P0_sealed.jsonl",
          "g6_main": "artifacts/trials/g6_unsealed/g6_main_sealed.jsonl", "stress_S0": "artifacts/trials/stress_unsealed/v1/stress_S0_sealed.jsonl"}
CONS = {}
for f in ["artifacts/reports/judge_validation/g6_consensus.json", "artifacts/reports/judge_validation/stress_v1_consensus.json",
          "artifacts/positive_control/rejudge/P0_consensus.json"] + sorted(glob.glob("artifacts/finetune/rejudge/*_consensus.json")):
    if os.path.exists(f): CONS.update(json.load(open(f)))

def h264(src, dst):
    i = av.open(src); vi = i.streams.video[0]; o = av.open(dst, "w", options={"movflags": "+faststart"})
    s = o.add_stream("libx264", rate=30); s.width, s.height, s.pix_fmt = vi.codec_context.width, vi.codec_context.height, "yuv420p"; s.options = {"crf": os.environ.get("CRF", "26")}
    n = 0
    for f in i.decode(vi):
        for p in s.encode(f.reformat(format="yuv420p")): o.mux(p)
        n += 1
    for p in s.encode(): o.mux(p)
    o.close(); i.close(); return n

index = []
for line in open(PICK):
    sess, _, tid = line.split(); rec = next(json.loads(l) for l in open(SEALED[sess]) if json.loads(l)["trial_id"] == tid)
    d = f"{OUT}/rollout_{tid}"; os.makedirs(f"{d}/video", exist_ok=True)
    z = np.load(f"{RAW}/{tid}_traj.npz"); n = len(z["state"])
    frames = {}
    for cam in ("top", "wrist"):
        shutil.copy(f"{RAW}/{tid}_{cam}.mp4", f"{d}/video/{cam}_av1.mp4"); frames[cam] = h264(f"{RAW}/{tid}_{cam}.mp4", f"{d}/video/{cam}.mp4")
    T = pd.DataFrame({"frame_index": np.arange(n), "t_wall_s": z["tick_s"].round(4), "t_video_s": (np.arange(n) / 30).round(4),
                      **{f"state.{j}": z["state"][:, k].round(3) for k, j in enumerate(J)}, **{f"action.{j}": z["action"][:, k].round(3) for k, j in enumerate(J)}})
    T.to_parquet(f"{d}/trajectory.parquet", index=False); T.to_csv(f"{d}/trajectory.csv", index=False)
    con = CONS.get(tid, {}); b = BLOCK[sess]
    ep = {"episode_id": f"rollout_{tid}", "source": "policy rollout (learned ACT policy on a Jetson Orin Nano Super; not teleoperation)",
          "block": b[0], "trial_number": rec["trial"], "start_position": b[1], "gripper": b[2], "object": "unopened 268 g cola can",
          "task": "Pick up the cola can and place it upright on the coaster", "engine": rec["cell"], "engine_description": CELL.get(rec["cell"], rec["cell"]),
          "outcome": {"success": rec["success"], "rule": "can standing upright on the coaster at the end (geometric judge on the overhead video) AND gripper released AND no human contact",
                      "automatic_judge": rec["judge_auto"], "video_consensus_rejudge": {k: con[k] for k in con if k in ("success_geom", "reason", "base_dist_px")} or None,
                      "released_by_operator": rec["released"], "human_contact": rec["human_contact"], "aborted": rec["aborted"]},
          "operator_note": NOTES.get(tid, "No failure reported by the operator." if rec["success"] else None),
          "ai_judge_end_of_trial": rec.get("d4_judge"),
          "trajectory": {"rows": n, "state": "observation.state: follower joint positions read at each control step", "action": "command sent to the follower at that step (the policy output after chunk blending, clipped to the motor limits)",
                         "units": "shoulder_pan..wrist_roll in degrees; gripper 0-100 (position, not force)", "space": "joint space; no end-effector pose is recorded",
                         "chunk_timing": {"infer_ms": z["infer_ms"].round(1).tolist(), "round_trip_ms": z["rtt_ms"].round(1).tolist(), "note": "one entry per 100-step action chunk request"}},
          "sync": {"rule": "frame i of each video is the camera image observed at control step i; state[i] was read at the same step and action[i] was sent right after",
                   "video_frames": frames, "trajectory_rows": n, "frames_equal_rows": frames["top"] == n == frames["wrist"],
                   "clock": "videos are encoded at a nominal 30 fps, but control steps are not evenly spaced (median %.1f ms, max %.0f ms); use t_wall_s for real time, not frame_index / 30" % (np.median(np.diff(z['tick_s'])) * 1000, np.diff(z['tick_s']).max() * 1000)}}
    json.dump(ep, open(f"{d}/episode.json", "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    index.append({"episode_id": ep["episode_id"], "source": "rollout", "block": b[0], "start": b[1], "gripper": b[2], "engine": rec["cell"], "success": rec["success"], "operator_note": ep["operator_note"]})
    print(ep["episode_id"], rec["cell"], rec["success"], frames, n, flush=True)

# two teleoperated demos from the LeRobot v3 dataset (for contrast: human control, all successful)
Rd = "/home/chanseok/edgeqgate_data/so101_demo"
E = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{Rd}/meta/episodes/chunk-*/*.parquet"))])
for epi in (1, 47):
    r = E[E.episode_index == epi].iloc[0]; d = f"{OUT}/teleop_demo_episode_{epi:06d}"; os.makedirs(f"{d}/video", exist_ok=True)
    D = pd.read_parquet(f"{Rd}/data/chunk-{int(r['data/chunk_index']):03d}/file-{int(r['data/file_index']):03d}.parquet"); g = D[D.episode_index == epi].reset_index(drop=True)
    S, A = np.stack(g["observation.state"]), np.stack(g["action"]); frames = {}
    for cam in ("top", "wrist"):
        K = f"videos/observation.images.{cam}"; src = f"{Rd}/{K}/chunk-{int(r[K + '/chunk_index']):03d}/file-{int(r[K + '/file_index']):03d}.mp4"
        t0, t1 = float(r[K + "/from_timestamp"]), float(r[K + "/to_timestamp"])
        i = av.open(src); vi = i.streams.video[0]; o = av.open(f"{d}/video/{cam}.mp4", "w", options={"movflags": "+faststart"}); s = o.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = vi.codec_context.width, vi.codec_context.height, "yuv420p"; s.options = {"crf": os.environ.get("CRF", "26")}; n = 0
        for f in i.decode(vi):
            t = float(f.pts * vi.time_base)
            if t < t0 - 1e-6 or t >= t1 - 1e-6: continue
            for p in s.encode(f.reformat(format="yuv420p")): o.mux(p)
            n += 1
        for p in s.encode(): o.mux(p)
        o.close(); i.close(); frames[cam] = n
    T = pd.DataFrame({"frame_index": g["frame_index"], "t_s": g["timestamp"].round(4), **{f"state.{j}": S[:, k].round(3) for k, j in enumerate(J)}, **{f"action.{j}": A[:, k].round(3) for k, j in enumerate(J)}})
    T.to_parquet(f"{d}/trajectory.parquet", index=False); T.to_csv(f"{d}/trajectory.csv", index=False)
    ep = {"episode_id": f"teleop_demo_episode_{epi:06d}", "source": "teleoperated demonstration (a person drove the SO-101 leader arm; not a policy)",
          "dataset": "chans/quantgate-so101-coaster (LeRobot v3.0), episode %d" % epi, "object": "unopened 268 g cola can", "start_position": "training start mark",
          "gripper": "as recorded for the LOCK-1 dataset", "task": "Pick up the cola can and place it upright on the coaster", "outcome": {"success": True, "note": "every demonstration in the dataset is a success"},
          "trajectory": {"rows": len(g), "state": "follower joint positions", "action": "leader arm joint positions (the human command)", "units": "degrees; gripper 0-100"},
          "sync": {"rule": "LeRobot timestamps: frame i is at t_s = i / 30 s from the episode start", "video_frames": frames, "trajectory_rows": len(g), "frames_equal_rows": frames["top"] == len(g) == frames["wrist"]}}
    json.dump(ep, open(f"{d}/episode.json", "w"), indent=1)
    index.append({"episode_id": ep["episode_id"], "source": "teleop", "block": "LOCK-1 dataset", "start": "training start mark", "gripper": "as recorded", "engine": None, "success": True, "operator_note": None})
    print(ep["episode_id"], frames, len(g), flush=True)
pd.DataFrame(index).to_csv(f"{OUT}/index.csv", index=False); json.dump(index, open(f"{OUT}/index.json", "w"), indent=1)
