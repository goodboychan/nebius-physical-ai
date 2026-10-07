"""SO-101 실기 trial 실행기 (Orin, lerobot-env). TensorRT 정책 서버(trt_policy_server.py, python3.10)를 띄우고
30Hz로 팔을 움직인다. 매 trial: 홈 자세로 천천히 이동 → 엔터로 시작 → 최대 60초 → 자동 판정 → 로그.

- 정책 호출: 100스텝 chunk. 대기열이 PREF(10)스텝 남으면 그 순간 관측으로 다음 chunk를 백그라운드 요청한다. 새 chunk의 i번째
  동작은 요청 시점 + i 스텝의 동작이다. 이전 chunk의 마지막 BLEND(4)스텝은 이전 동작과 같은 시각의 새 동작을 w = 1/5..4/5로
  섞고, 이전 chunk가 끝나면 새 chunk를 그 시각의 인덱스부터 잇는다. 섞기 시작(요청 후 6스텝 = 200ms)까지 결과가 없으면
  기다리고 '늦은 chunk'로 센다 — 그보다 빠른 모든 셀은 같은 타이밍이다
- action은 팔로워 모터 제한으로 잘린다(모터가 하는 일과 같다)
- 오버헤드·손목 영상은 데모와 같은 코덱(AV1 libsvtav1, crf 30, g 2)으로 저장한다 — 판정기는 이 조건에서 검증됐다
- 중단: Ctrl+C (안전 개입, unsafe로 기록). 그 외에는 60초를 다 채운다
  (LeRobot 키보드 감지기는 쓰지 않는다 — 백그라운드에서 터미널 입력을 가로채 y/n 질문이 막혔다, 2026-10-07)
- 영상 압축은 별도 스레드에서 한다. 제어 루프가 늦어지면 몰아서 따라잡지 않고 시간 기준을 다시 잡는다(덜덜거림 방지)
- 판정: scripts/judge_success.py의 judge()(목표 영역 안·서 있음·정지) + 조작자 입력(놓음, 사람 개입) — 셋 다 만족해야 성공
사용: so101_trial.py <session 이름> <cell 코드> <엔진> [trial 수]"""
import json, os, queue, socket, struct, subprocess, sys, threading, time
import numpy as np, av, cv2
from lerobot.utils.import_utils import register_third_party_plugins; register_third_party_plugins()
from lerobot.robots.so_follower import SO101Follower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot_camera_openmv import OpenMVCameraConfig
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from judge_success import judge

session, cell, engine = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 1
FPS, T_MAX, N_ACT = 30, 60.0, 100
PREF, BLEND = 10, 4  # chunk가 10스텝 남으면 다음 chunk를 요청, 마지막 4스텝 동안 이전·새 chunk를 섞어 넘어간다(2026-10-07)
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

class Prefetch:
    """정책 서버 요청을 한 번에 하나, 백그라운드에서 보낸다."""
    def __init__(self): self.t = None; self.res = None
    def start(self, s, top, wrist, step):
        global seq
        payload = struct.pack("<I", seq) + s.tobytes() + np.ascontiguousarray(top).tobytes() + np.ascontiguousarray(wrist).tobytes(); seq += 1
        def run():
            t = time.perf_counter(); sk.sendall(payload); r = json.loads(rf.readline())
            self.res = (np.array(r["actions"]), r["infer_ms"], step, (time.perf_counter() - t) * 1000)
        self.res = None; self.t = threading.Thread(target=run, daemon=True); self.t.start()
    def take(self):
        self.t.join(); self.t = None; return self.res

def state_of(obs): return np.array([obs[f"{n}.pos"] for n in NAMES], np.float32)
def send(a): robot.send_action({f"{n}.pos": float(v) for n, v in zip(NAMES, np.clip(a, lo, hi))})

def go_home(sec=3.0):
    s0 = state_of(robot.get_observation())
    for k in range(int(sec * FPS)):
        send(s0 + (HOME - s0) * (k + 1) / (sec * FPS)); time.sleep(1 / FPS)

class Writer:
    """AV1 압축을 제어 루프 밖(스레드)에서 한다."""
    def __init__(self, path, w, h):
        self.c = av.open(path, "w"); self.st = self.c.add_stream("libsvtav1", rate=FPS)
        self.st.width, self.st.height, self.st.pix_fmt = w, h, "yuv420p"; self.st.options = {"crf": "30", "preset": "12", "g": "2"}
        self.q = queue.Queue(); self.t = threading.Thread(target=self._run, daemon=True); self.t.start()
    def _run(self):
        while True:
            img = self.q.get()
            if img is None: break
            for p in self.st.encode(av.VideoFrame.from_ndarray(img, format="rgb24")): self.c.mux(p)
        for p in self.st.encode(): self.c.mux(p)
        self.c.close()
    def put(self, img): self.q.put(img)
    def close(self): self.q.put(None); self.t.join()

seq = 0
closers = []
for t_i in range(N):
    tid = f"{cell}_{time.strftime('%m%d_%H%M%S')}"
    go_home()
    input(f"\n[{t_i+1}/{N}] {tid}: 캔을 시작 표시에 세우고 손을 화면 밖으로 뺀 뒤 엔터 > ")
    wtop, wwr = Writer(f"{OUT}/{tid}_top.mp4", 640, 480), Writer(f"{OUT}/{tid}_wrist.mp4", 320, 200)
    aq, states, actions, inf_ms, last_top, tick, rtt, late = [], [], [], [], [], [], [], 0
    pf = Prefetch(); newc = None; k0 = 0
    t0 = time.perf_counter(); aborted = False; k = 0; nxt = t0
    try:
        while time.perf_counter() - t0 < T_MAX:
            tick.append(time.perf_counter() - t0)
            obs = robot.get_observation(); s = state_of(obs)
            if not aq:                                   # 첫 chunk: 지금 관측으로 요청하고 기다린다
                pf.start(s, obs["top"], obs["wrist"], k); acts, ims, k0, ms = pf.take()
                inf_ms.append(ims); rtt.append(ms); aq = list(acts[k - k0:N_ACT]); nxt = time.perf_counter()
            r = len(aq)                                   # 이번 스텝을 포함한 이전 chunk의 남은 수
            if r == PREF and pf.t is None and newc is None:
                pf.start(s, obs["top"], obs["wrist"], k)
            if r <= BLEND and newc is None and pf.t is not None:
                was_late = pf.res is None; late += int(was_late)
                acts, ims, k0, ms = pf.take(); inf_ms.append(ims); rtt.append(ms); newc = acts
                if was_late: nxt = time.perf_counter()
            a = aq.pop(0)
            if newc is not None and r <= BLEND:
                w = (BLEND - r + 1) / (BLEND + 1); a = (1 - w) * a + w * newc[k - k0]
            send(a)
            if not aq and newc is not None:
                aq = list(newc[k + 1 - k0:N_ACT]); newc = None
            states.append(s); actions.append(a)
            wtop.put(obs["top"]); wwr.put(obs["wrist"])
            last_top.append(cv2.cvtColor(obs["top"], cv2.COLOR_RGB2GRAY)); last_top = last_top[-15:]
            k += 1; nxt += 1 / FPS
            now = time.perf_counter()
            if now < nxt: time.sleep(nxt - now)
            elif now - nxt > 1 / FPS: nxt = now   # 한 스텝 넘게 늦으면 몰아서 따라잡지 않는다
    except KeyboardInterrupt:
        aborted = True; print("\n  Ctrl+C: 중단 (unsafe)")
    t_loop = time.perf_counter() - t0
    # 영상 마무리(남은 압축·파일 닫기)는 판정과 무관하므로 백그라운드에서 한다. 프로그램 끝에서 모두 기다린다
    closers.append(threading.Thread(target=lambda w=(wtop, wwr): [x.close() for x in w])); closers[-1].start()
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
           "duration_s": round(t_loop, 2), "steps": len(S), "judge_auto": j,
           "released": rel == "y", "human_contact": touch == "y", "success": final,
           "infer_ms_mean": round(float(np.mean(inf_ms)), 1), "n_infer": len(inf_ms)}
    np.savez(f"{OUT}/{tid}_traj.npz", state=S, action=A, infer_ms=np.array(inf_ms), tick_s=np.array(tick), rtt_ms=np.array(rtt))
    rec["rtt_ms_max"] = round(float(max(rtt)), 1); rec["late_chunks"] = late   # late > 0: 섞기 시작까지 결과가 오지 않은 chunk 수
    dt = np.diff(np.array(tick)) * 1000
    rec["step_ms_p50_p99_max"] = [round(float(np.percentile(dt, 50)), 1), round(float(np.percentile(dt, 99)), 1), round(float(dt.max()), 1)]
    with open(f"{OUT}/trials.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
    print(f"  -> {'성공' if final else '실패'} (자동 {j['reason']}, 놓음 {rel}, 개입 {touch})  {rec['duration_s']}s, 추론 {rec['n_infer']}회 평균 {rec['infer_ms_mean']}ms, 스텝 간격 p50/p99/max {rec['step_ms_p50_p99_max']} ms, 왕복 최대 {rec['rtt_ms_max']}ms, 늦은 chunk {rec['late_chunks']}")
go_home()
for c in closers: c.join()   # 영상 파일이 모두 닫힐 때까지
robot.disconnect(); sk.close(); srv.terminate()
