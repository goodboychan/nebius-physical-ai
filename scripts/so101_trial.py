"""SO-101 실기 trial 실행기 (Orin, lerobot-env). TensorRT 정책 서버(trt_policy_server.py, python3.10)를 띄우고
30Hz로 팔을 움직인다. 매 trial: 홈 자세로 천천히 이동 → 엔터로 시작 → 최대 60초 → 자동 판정 → 로그.

- 정책 호출: action 대기열이 비면 현재 관측으로 100스텝 chunk를 받아 n_action_steps(체크포인트 설정 100)만큼 실행
- action은 팔로워 모터 제한으로 잘린다(모터가 하는 일과 같다)
- 오버헤드·손목 영상은 데모와 같은 코덱(AV1 libsvtav1, crf 30, g 2)으로 저장한다 — 판정기는 이 조건에서 검증됐다
- 키: q = 중단(안전 개입, unsafe로 기록). 그 외에는 60초를 다 채운다
- 판정: scripts/judge_success.py의 judge()(목표 영역 안·서 있음·정지) + 조작자 입력(놓음, 사람 개입) — 셋 다 만족해야 성공
사용: so101_trial.py <session 이름> <cell 코드> <엔진> [trial 수]"""
import json, os, socket, struct, subprocess, sys, time
import numpy as np, av, cv2
from lerobot.utils.import_utils import register_third_party_plugins; register_third_party_plugins()
from lerobot.robots.so_follower import SO101Follower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot_camera_openmv import OpenMVCameraConfig
from lerobot.utils.keyboard_input import init_keyboard_listener
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from judge_success import judge

session, cell, engine = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 1
FPS, T_MAX, N_ACT = 30, 60.0, 100
NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
HOME = np.array(json.load(open(os.path.join(HERE, "so101_home.json")))["home_deg"])
OUT = os.path.expanduser(f"~/so101_trials/{session}"); os.makedirs(OUT, exist_ok=True)
SOCK = "/tmp/so101_policy.sock"

srv = subprocess.Popen(["/usr/bin/python3", os.path.join(HERE, "trt_policy_server.py"), engine,
                        os.path.join(os.path.dirname(engine), "norm_stats.npz"), SOCK],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for line in srv.stdout:
    if line.startswith("ready"): break
    if "Error" in line: print(line); sys.exit(1)
sk = socket.socket(socket.AF_UNIX); sk.connect(SOCK); rf = sk.makefile()

cams = {"top": OpenCVCameraConfig(index_or_path="/dev/so101_cam_top", width=640, height=480, fps=30, fourcc="MJPG"),
        "wrist": OpenMVCameraConfig(fps=30)}
subprocess.run(["/usr/local/bin/so101-cam-lock", "/dev/so101_cam_top"], capture_output=True)
robot = SO101Follower(SO101FollowerConfig(port="/dev/so101_follower", id="follower", cameras=cams))
robot.connect()
cal = robot.calibration
lo = np.array([0.0 if n == "gripper" else (cal[n].range_min - (cal[n].range_min + cal[n].range_max) / 2) * 360 / 4095 for n in NAMES])
hi = np.array([100.0 if n == "gripper" else (cal[n].range_max - (cal[n].range_min + cal[n].range_max) / 2) * 360 / 4095 for n in NAMES])
listener, events = init_keyboard_listener()

def state_of(obs): return np.array([obs[f"{n}.pos"] for n in NAMES], np.float32)
def send(a): robot.send_action({f"{n}.pos": float(v) for n, v in zip(NAMES, np.clip(a, lo, hi))})

def go_home(sec=3.0):
    s0 = state_of(robot.get_observation())
    for k in range(int(sec * FPS)):
        send(s0 + (HOME - s0) * (k + 1) / (sec * FPS)); time.sleep(1 / FPS)

def writer(path, w, h):
    c = av.open(path, "w"); st = c.add_stream("libsvtav1", rate=FPS); st.width, st.height, st.pix_fmt = w, h, "yuv420p"
    st.options = {"crf": "30", "preset": "12", "g": "2"}; return c, st

seq = 0
for t_i in range(N):
    tid = f"{cell}_{time.strftime('%m%d_%H%M%S')}"
    go_home()
    input(f"\n[{t_i+1}/{N}] {tid}: 캔을 시작 표시에 세우고 손을 화면 밖으로 뺀 뒤 엔터 > ")
    events["stop_recording"] = False; events["exit_early"] = False
    ctop, stop_ = writer(f"{OUT}/{tid}_top.mp4", 640, 480); cwr, swr = writer(f"{OUT}/{tid}_wrist.mp4", 320, 200)
    queue, states, actions, inf_ms, last_top = [], [], [], [], []
    t0 = time.perf_counter(); aborted = False; k = 0
    while True:
        t = time.perf_counter() - t0
        if t >= T_MAX: break
        if events["stop_recording"]: aborted = True; break
        obs = robot.get_observation(); s = state_of(obs)
        if not queue:
            sk.sendall(struct.pack("<I", seq) + s.tobytes() + np.ascontiguousarray(obs["top"]).tobytes() + np.ascontiguousarray(obs["wrist"]).tobytes())
            r = json.loads(rf.readline()); seq += 1; inf_ms.append(r["infer_ms"]); queue = list(np.array(r["actions"])[:N_ACT])
        a = queue.pop(0); send(a)
        states.append(s); actions.append(a)
        for img, (c, st) in ((obs["top"], (ctop, stop_)), (obs["wrist"], (cwr, swr))):
            for p in st.encode(av.VideoFrame.from_ndarray(img, format="rgb24")): c.mux(p)
        last_top.append(cv2.cvtColor(obs["top"], cv2.COLOR_RGB2GRAY)); last_top = last_top[-15:]
        k += 1
        time.sleep(max(0.0, t0 + k / FPS - time.perf_counter()))
    for c, st in ((ctop, stop_), (cwr, swr)):
        for p in st.encode(): c.mux(p)
        c.close()
    S = np.stack(states); A = np.stack(actions)
    j = judge(last_top, float(S[-1, 5])) if not aborted else {"success": False, "reason": "unsafe(operator abort)"}
    # '놓음'은 자동 판정하지 않는다(success_criterion §3). 조작자가 마지막 상태를 보고 답한다
    rel = None
    while rel not in ("y", "n"):
        rel = input("  집게가 캔에서 떨어져 있습니까(캔을 놓았나)? [y/n] > ").strip().lower()
    touch = None
    while touch not in ("y", "n"):
        touch = input("  trial 중 사람이 캔이나 팔을 건드렸습니까? [y/n] > ").strip().lower()
    final = bool(j["success"]) and rel == "y" and touch == "n"
    rec = {"trial_id": tid, "session": session, "cell": cell, "engine": os.path.basename(engine), "aborted": aborted,
           "duration_s": round(time.perf_counter() - t0, 2), "steps": len(S), "judge_auto": j,
           "released": rel == "y", "human_contact": touch == "y", "success": final,
           "infer_ms_mean": round(float(np.mean(inf_ms)), 1), "n_infer": len(inf_ms)}
    np.savez(f"{OUT}/{tid}_traj.npz", state=S, action=A, infer_ms=np.array(inf_ms))
    with open(f"{OUT}/trials.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
    print(f"  -> {'성공' if final else '실패'} (자동 {j['reason']}, 놓음 {rel}, 개입 {touch})  {rec['duration_s']}s, 추론 {rec['n_infer']}회 평균 {rec['infer_ms_mean']}ms")
go_home()
robot.disconnect(); sk.close(); srv.terminate()
if listener: listener.stop()
