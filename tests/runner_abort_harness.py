"""Hardware-free harness for so101_trial.run_one abort paths (2026-10-13 external review).
It loads only the function and class definitions from scripts/so101_trial.py and runs them against a fake robot,
fake policy server and fake writer. Run: <python with numpy> tests/runner_abort_harness.py"""
import ast, json, os, threading, time, types, builtins, io, sys
import numpy as np
src = open(os.path.join(os.path.dirname(__file__), "..", "scripts", "so101_trial.py")).read()
tree = ast.parse(src)
keep = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in
        ("grab_latest", "Prefetch", "state_of", "send", "go_home", "run_one")]
NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]

class FakeWriter:
    def __init__(self, *a): pass
    def put(self, img): pass
    def close(self): pass

def make_env(robot, server_delay=0.0, tmp="/tmp/runner_harness"):
    os.makedirs(tmp, exist_ok=True)
    g = {"np": np, "json": json, "time": time, "threading": threading, "struct": __import__("struct"), "os": os,
         "NAMES": NAMES, "FPS": 30, "T_MAX": 2.0, "N_ACT": 100, "PREF": 10, "BLEND": 4, "HOME": np.zeros(6),
         "lo": -np.ones(6) * 1e3, "hi": np.ones(6) * 1e3, "robot": robot, "Writer": FakeWriter, "OUT": tmp, "SEALED": tmp,
         "BLIND": True, "STRESS": False, "CAN": None, "START": "test", "session": "harness", "bsession": "harness",
         "latest_top": {"img": None, "ts": None}, "d4_ask": {"f": None}, "d4_factory": None, "closers": [], "seq": 0, "cur_engine": "E",
         "cv2": types.SimpleNamespace(cvtColor=lambda x, c: x[..., 0], COLOR_RGB2GRAY=0),
         "judge": lambda frames, grip, can=None: {"success": True, "reason": "ok", "base_dist_px": 1.0}}
    class Sock:
        def sendall(self, payload): pass
    class RF:
        def readline(self):
            time.sleep(server_delay); return json.dumps({"actions": np.zeros((100, 6)).tolist(), "infer_ms": 1.0}) + "\n"
    g["sk"], g["rf"] = Sock(), RF()
    exec(compile(ast.Module(body=keep, type_ignores=[]), "so101_trial_defs", "exec"), g)
    return g

class Robot:
    def __init__(self, fail_at, exc=KeyboardInterrupt): self.n = 0; self.fail_at = fail_at; self.exc = exc
    def get_observation(self):
        self.n += 1
        if self.n > self.fail_at: raise self.exc()
        o = {f"{k}.pos": 0.0 for k in NAMES}; o["top"] = np.zeros((4, 4, 3), np.uint8); o["wrist"] = np.zeros((2, 2, 3), np.uint8); return o
    def send_action(self, a): pass

answers = iter(["y", "n", ""] * 10)
builtins.input = lambda *a: next(answers)
results = {}
import _thread
cases = [("abort_before_first_state", Robot(fail_at=0), 0.0, False),
         ("abort_during_first_request", Robot(fail_at=10 ** 9), 0.5, True),
         ("runtime_error_mid_trial", Robot(fail_at=20, exc=RuntimeError), 0.0, False),
         ("policy_server_timeout", Robot(fail_at=10 ** 9), 6.0, False)]
for name, robot, delay, interrupt in cases:
    g = make_env(robot, server_delay=delay); g["go_home"] = lambda sec=3.0: None
    if interrupt: threading.Timer(0.15, _thread.interrupt_main).start()
    t0 = time.time()
    rec, final, j, rel, touch = g["run_one"](f"t_{name}", name, "C", "E")
    results[name] = {"aborted": rec["aborted"], "steps": rec["steps"], "reason": j["reason"], "runtime_error": rec["runtime_error"],
                     "infer_ms_mean": rec["infer_ms_mean"], "rtt_ms_max": rec["rtt_ms_max"], "step_ms": rec["step_ms_p50_p99_max"],
                     "server_restart_flag": g["cur_engine"] is None,
                     "saved_traj": os.path.exists(f"/tmp/runner_harness/t_{name}_traj.npz"), "sec": round(time.time() - t0, 2)}
print(json.dumps(results, indent=1))
assert all(r["aborted"] and r["saved_traj"] for r in results.values())
assert results["policy_server_timeout"]["runtime_error"].startswith("RuntimeError: policy server reply timeout") and results["policy_server_timeout"]["server_restart_flag"]
print("HARNESS OK")
