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
사용: so101_trial.py <session 이름> <cell 코드> <엔진> [trial 수]
      so101_trial.py --blind <main|retest>   (G6: 봉인 순서표를 따른다, IG-4·IG-5)
      so101_trial.py --blind F0 fp16         (FP16 실기, docs/fp16_real_arm_preregistration.md)
      so101_trial.py --blind P0 pc           (양성 대조, docs/positive_control_preregistration.md)
      so101_trial.py --blind <S0|S1|S4> [v2] (스트레스 시험, v2 = 고무줄 그리퍼 §8, S0 = 패드 없는 정상 조건 기준, docs/stress_test_protocol.md: 새 봉인 순서표 ~/.edgeqgate_sealed/stress/,
                                              S4는 시험 전에 잰 캔 판정 값 stress_can_S4.json, trial 끝에 Cosmos에게 판정 질문 1회 — 기술 통계용)
블라인드 모드: 셀↔토큰 대응과 순서는 ~/.edgeqgate_sealed/에만 있다. 화면과 공개 로그에는 trial 번호만 남고, 셀·arm은 봉인 로그에만
쓴다. 중간에 끝내도 다음 실행이 다음 trial부터 잇는다. 무효(시작 조건 실수 등)로 표시한 trial은 같은 번호로 다시 한다."""
import json, os, queue, socket, struct, subprocess, sys, threading, time
import numpy as np, av, cv2
from lerobot.utils.import_utils import register_third_party_plugins; register_third_party_plugins()
from lerobot.robots.so_follower import SO101Follower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot_camera_openmv import OpenMVCameraConfig
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from judge_success import judge
sys.path.insert(0, os.path.expanduser("~/edgeqgate/repo/src"))
from edgeqgate.supervisor import Supervisor, SupervisorConfig

# D4 Cosmos-Reason2 감독자 — **관찰 모드**(판정을 기록만 하고 팔에 개입하지 않는다, decision_log 2026-10-08).
# 엔드포인트 설정이 없거나 응답이 없으면 감독 없이 진행하고 그 사실을 기록한다.
D4_CFG = os.path.expanduser("~/.config/edgeqgate/cosmos_endpoint.json")
STRESS = len(sys.argv) > 2 and sys.argv[1] == "--blind" and sys.argv[2] in ("S0", "S1", "S4", "F0", "P0")
D4_PROMPT = ("Overhead camera view of a robot arm that picks up a " + ("can" if STRESS else "cola can") + " and stands it upright on a round coaster. "
             "Answer with exactly one word: CONTINUE if the task is proceeding normally, FALLBACK if the arm looks stuck or "
             "confused, ABORT if something is unsafe (the can falling off the table, the arm hitting something, a human hand "
             "in the workspace).")
D4_JUDGE_PROMPT = ("Overhead camera view after a robot arm tried to stand a can upright on a round coaster. "
                   "Is the can standing upright on the coaster now? Answer with exactly one word: YES or NO.")
latest_top = {"img": None}; d4_ask = {"f": None}
def make_d4():
    if not os.path.exists(D4_CFG): return None
    import base64, http.client, urllib.parse
    cfg = json.load(open(D4_CFG)); u = urllib.parse.urlparse(cfg["url"])
    hdr = {"Authorization": "Bearer " + open(os.path.expanduser(cfg["token_file"])).read().strip(), "Content-Type": "application/json"}
    conn = {"c": http.client.HTTPSConnection(u.netloc, timeout=10)}
    def infer(img, prompt=D4_PROMPT):
        if img is None: return ""
        ok, jpg = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
        body = json.dumps({"model": "nvidia/Cosmos-Reason2-2B", "max_tokens": 8, "temperature": 0, "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()}},
            {"type": "text", "text": prompt}]}]})
        try:
            conn["c"].request("POST", "/v1/chat/completions", body=body, headers=hdr); r = conn["c"].getresponse(); d = json.loads(r.read())
        except Exception:
            conn["c"] = http.client.HTTPSConnection(u.netloc, timeout=10); raise
        return d["choices"][0]["message"]["content"]
    d4_ask["f"] = infer
    return lambda: Supervisor(infer, lambda: latest_top["img"], SupervisorConfig(rate_hz=2.0))

BLIND = sys.argv[1] == "--blind"
SEALED = os.path.expanduser("~/.edgeqgate_sealed")
if BLIND:
    bsession = sys.argv[2]; assert bsession in ("main", "retest", "S0", "S1", "S4", "F0", "P0")
    SV = sys.argv[3] if STRESS and len(sys.argv) > 3 else "v1"; assert SV in ("v1", "v2", "fp16", "pc")   # v2: 고무줄 그리퍼(프로토콜 §8), fp16: FP16 실기
    assert (bsession == "F0") == (SV == "fp16"), "F0 블록은 fp16과 함께만: --blind F0 fp16"
    assert (bsession == "P0") == (SV == "pc"), "P0 블록은 pc와 함께만: --blind P0 pc"
    if STRESS: SEALED += "/stress" + {"v1": "", "v2": "_v2", "fp16": "_fp16", "pc": "_pc"}[SV]
    sealed = json.load(open(f"{SEALED}/{'stress' if STRESS else 'g6'}_sealed.json")); plan = sealed[bsession]
    session, cell = f"{'stress' + {'v1': '', 'v2': '_v2', 'fp16': '_fp16', 'pc': '_pc'}[SV] if STRESS else 'g6'}_{bsession}", "BLIND"
    engine_of = lambda tok: f"{SEALED}/engines/{tok}.engine"
    pubfull = json.load(open(f"{SEALED}/{'stress' if STRESS else 'g6'}_schedule_public.json")); pub = pubfull[bsession]
    # 실행 전 확인(2026-10-12 외부 검토 반영): 봉인 순서표가 공개본에 적힌 해시와 같은지, LOCK-2 기록이 온전한지.
    # 하나라도 실패하면 trial을 시작하지 않는다
    import hashlib
    _sb = open(f"{SEALED}/{'stress' if STRESS else 'g6'}_sealed.json", "rb").read()
    if hashlib.sha256(_sb).hexdigest() != pubfull["sealed_sha256"]:
        sys.exit("실행 거부: 봉인 순서표 해시가 공개본과 다르다")
    from pathlib import Path
    from edgeqgate.freeze import require_lock2
    _repo = Path(os.path.expanduser("~/edgeqgate/repo"))
    os.environ.setdefault("EDGEQGATE_GRID_PATH", str(_repo / "configs" / "variant_grid.yaml"))
    try:
        require_lock2(_repo / "artifacts" / "freeze" / "lock2.json")
    except Exception as e:
        sys.exit(f"실행 거부: LOCK-2 확인 실패 — {type(e).__name__}: {str(e)[:200]}")
    print("실행 전 확인: 봉인 순서표 해시 일치, LOCK-2 확인 통과")
    engine = engine_of(pub[0]["engine_token"])
else:
    session, cell, engine = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 1
CAN = None   # S4: 시험 전에 잰 노란 캔 판정 값(so101_can_calib.py). 그 밖에는 success_criterion §3 잠금 값
if BLIND and bsession == "S4":
    CAN = json.load(open(os.path.join(HERE, "stress_can_S4.json")))
START = {"P0": "콜라캔을 원래 시작 표시에 세우고 (Ctrl+C를 누를 준비를 하고)", "F0": "콜라캔을 원래 시작 표시에 세우고", "S0": "캔을 원래 시작 표시(S0)에 세우고", "S1": "캔을 **3cm 옮긴** 시작 표시(S1)에 세우고", "S4": "**노란 캔**을 원래 시작 표시에 세우고"}.get(sys.argv[2] if BLIND else "", "캔을 시작 표시에 세우고")
FPS, T_MAX, N_ACT = 30, 60.0, 100
PREF, BLEND = 10, 4  # chunk가 10스텝 남으면 다음 chunk를 요청, 마지막 4스텝 동안 이전·새 chunk를 섞어 넘어간다(2026-10-07)
NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
HOME = np.array(json.load(open(os.path.join(HERE, "so101_home.json")))["home_deg"])
OUT = os.path.expanduser(f"~/so101_trials/{session}"); os.makedirs(OUT, exist_ok=True)
SOCK = "/tmp/so101_policy.sock"

srv = sk = rf = None; cur_engine = None
def start_server(eng):
    """엔진이 바뀔 때만 서버를 다시 띄운다. 출력에 엔진 이름이 나오지 않게 한다(블라인드)."""
    global srv, sk, rf, cur_engine
    if eng == cur_engine: return
    if srv is not None: sk.close(); srv.terminate(); srv.wait()
    srv = subprocess.Popen(["/usr/bin/python3", os.path.join(HERE, "trt_policy_server.py"), eng,
                            os.path.join(os.path.dirname(eng), "norm_stats.npz"), SOCK],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in srv.stdout:
        if line.startswith("ready"): break
        if "Error" in line or "Traceback" in line: print("정책 서버 시작 실패"); sys.exit(1)
    sk = socket.socket(socket.AF_UNIX); sk.connect(SOCK); rf = sk.makefile(); cur_engine = eng
start_server(engine)
d4_factory = make_d4()
print("D4 감독자(관찰 모드):", "켜짐" if d4_factory else "꺼짐(엔드포인트 설정 없음)")

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
def run_one(tid, label, cellname, engname):
    go_home()
    input(f"\n{label}: {START} 손을 화면 밖으로 뺀 뒤 엔터 > ")
    wtop, wwr = Writer(f"{OUT}/{tid}_top.mp4", 640, 480), Writer(f"{OUT}/{tid}_wrist.mp4", 320, 200)
    aq, states, actions, inf_ms, last_top, tick, rtt, late = [], [], [], [], [], [], [], 0
    pf = Prefetch(); newc = None; k0 = 0
    sup = d4_factory() if d4_factory else None
    latest_top["img"] = None
    if sup: sup.start()
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
            wtop.put(obs["top"]); wwr.put(obs["wrist"]); latest_top["img"] = obs["top"]
            last_top.append(cv2.cvtColor(obs["top"], cv2.COLOR_RGB2GRAY)); last_top = last_top[-15:]
            k += 1; nxt += 1 / FPS
            now = time.perf_counter()
            if now < nxt: time.sleep(nxt - now)
            elif now - nxt > 1 / FPS: nxt = now   # 한 스텝 넘게 늦으면 몰아서 따라잡지 않는다
    except KeyboardInterrupt:
        aborted = True; print("\n  Ctrl+C: 중단 (unsafe)")
    t_loop = time.perf_counter() - t0
    d4 = None
    if sup:
        sup.stop(); d4 = sup.ex3_summary(); d4["mode"] = "shadow"; d4["log"] = [{k2: e[k2] for k2 in ("decision", "latency_ms", "error")} for e in sup.log]
    # 영상 마무리(남은 압축·파일 닫기)는 판정과 무관하므로 백그라운드에서 한다. 프로그램 끝에서 모두 기다린다
    closers.append(threading.Thread(target=lambda w=(wtop, wwr): [x.close() for x in w])); closers[-1].start()
    S = np.stack(states); A = np.stack(actions)
    j = judge(last_top, float(S[-1, 5]), CAN) if not aborted else {"success": False, "reason": "unsafe(operator abort)"}
    ai = None   # 스트레스: trial 끝 프레임으로 Cosmos에게 한 번 묻는다(기술 통계, 판정에 쓰지 않는다)
    if STRESS and d4_ask["f"] and not aborted:
        t_a = time.perf_counter()
        try: ai = {"answer": d4_ask["f"](latest_top["img"], D4_JUDGE_PROMPT).strip(), "error": None}
        except Exception as e: ai = {"answer": None, "error": type(e).__name__}
        ai["latency_ms"] = round((time.perf_counter() - t_a) * 1000, 1)
    # '놓음'은 자동 판정하지 않는다(success_criterion §3). 조작자가 마지막 상태를 보고 답한다
    rel = None
    while rel not in ("y", "n"):
        rel = input("  집게가 캔에서 떨어져 있습니까(캔을 놓았나)? [y/n] > ").strip().lower()
    touch = None
    while touch not in ("y", "n"):
        touch = input("  trial 중 사람이 캔이나 팔을 건드렸습니까? [y/n] > ").strip().lower()
    final = bool(j["success"]) and rel == "y" and touch == "n"
    inv = None
    while inv not in ("", "x"):
        inv = input("  시작 조건 실수 등으로 이 trial을 무효로 할까요? [엔터=아니오 / x=무효] > ").strip().lower()
    rec = {"trial_id": tid, "session": session, "cell": cellname, "engine": engname, "aborted": aborted, "invalid": inv == "x",
           "duration_s": round(t_loop, 2), "steps": len(S), "judge_auto": j,
           "released": rel == "y", "human_contact": touch == "y", "success": final,
           "infer_ms_mean": round(float(np.mean(inf_ms)), 1), "n_infer": len(inf_ms), "d4": d4}
    if STRESS: rec["condition"] = bsession; rec["d4_judge"] = ai
    np.savez(f"{SEALED if BLIND else OUT}/{tid}_traj.npz", state=S, action=A, infer_ms=np.array(inf_ms), tick_s=np.array(tick), rtt_ms=np.array(rtt))
    rec["rtt_ms_max"] = round(float(max(rtt)), 1); rec["late_chunks"] = late   # late > 0: 섞기 시작까지 결과가 오지 않은 chunk 수
    dt = np.diff(np.array(tick)) * 1000
    rec["step_ms_p50_p99_max"] = [round(float(np.percentile(dt, 50)), 1), round(float(np.percentile(dt, 99)), 1), round(float(dt.max()), 1)]
    return rec, final, j, rel, touch
def report(rec, final, j, rel, touch):
    head = f"  -> {'무효' if rec['invalid'] else ('성공' if final else '실패')} (자동 {j['reason']}, 놓음 {rel}, 개입 {touch})  {rec['duration_s']}s, 스텝 간격 p50/p99 {rec['step_ms_p50_p99_max'][:2]} ms, 늦은 chunk {rec['late_chunks']}"
    if rec.get("d4"): head += f", Cosmos 판정 {rec['d4'].get('decisions')}"
    # 블라인드에서는 추론 지연을 보이지 않는다 — FP32(약 78ms)와 INT8(약 30ms)이 지연으로 구별되기 때문이다
    print(head if BLIND else head + f", 추론 {rec['n_infer']}회 평균 {rec['infer_ms_mean']}ms, 왕복 최대 {rec['rtt_ms_max']}ms")

if not BLIND:
    for t_i in range(N):
        tid = f"{cell}_{time.strftime('%m%d_%H%M%S')}"
        out = run_one(tid, f"[{t_i+1}/{N}] {tid}", cell, os.path.basename(engine)); rec = out[0]
        with open(f"{OUT}/{'invalid_trials' if rec['invalid'] else 'trials'}.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
        report(*out)
else:
    pub_log = f"{OUT}/trials.jsonl"
    done = {json.loads(l)["trial"] for l in open(pub_log)} if os.path.exists(pub_log) else set()
    todo = [r for r in pub if r["trial"] not in done]
    tag = ({"F0": "FP16", "P0": "양성 대조"}.get(bsession, "스트레스")) if STRESS else "G6"
    print(f"\n{tag} {bsession}: 남은 trial {len(todo)} / {len(pub)}")
    for r in todo:
        tok = r["engine_token"]; start_server(engine_of(tok))
        cs = next(x for x in plan if x["trial"] == r["trial"])
        tid = f"{bsession}{r['trial']:03d}_{time.strftime('%m%d_%H%M%S')}"
        out = run_one(tid, f"[{tag} {bsession} trial {r['trial']}/{len(pub)}]", "SEALED", tok); rec = out[0]
        sealed_rec = dict(rec, cell=cs["cell"], arm=cs.get("arm", "STRESS"), trial=r["trial"])
        rec = {k: v for k, v in rec.items() if k not in ("infer_ms_mean", "rtt_ms_max", "n_infer")}   # 공개 로그에서 지연 제외
        rec["trial"] = r["trial"]
        with open(f"{SEALED}/{session}_sealed.jsonl", "a") as f: f.write(json.dumps(sealed_rec) + "\n")
        with open(f"{OUT}/{'invalid_trials' if rec['invalid'] else 'trials'}.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
        report(*out)
        if rec["invalid"]: print("  (무효 — 같은 번호를 다음에 다시 합니다)"); 
        if input("  엔터 = 다음 trial / q = 오늘은 여기까지 > ").strip().lower() == "q": break
go_home()
for c in closers: c.join()   # 영상 파일이 모두 닫힐 때까지
robot.disconnect(); sk.close(); srv.terminate()
