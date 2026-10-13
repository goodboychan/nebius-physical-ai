"""Cosmos-Reason2 success-judge evaluation (docs/cosmos_judge_eval_preregistration.md). Committed before any C1/C2 query.

  split : build the trial list (video path, label from the consensus re-judge) and the seeded dev/eval split
  run   : query one condition and prompt variant on dev or eval, writing per-trial answers and latencies
  score : metrics with Wilson 95% intervals
Usage:
  python cosmos_judge_eval.py split <out.json> <video dir> [<video dir> ...]
  python cosmos_judge_eval.py run <split.json> <C0|C1|C2> <variant> <dev|eval> <out.json>     env: COSMOS_URL, COSMOS_TOKEN_FILE
  python cosmos_judge_eval.py score <run.json> [<run.json> ...]"""
import base64, glob, http.client, io, json, math, os, re, sys, time, urllib.parse
import numpy as np

LABELS = ["artifacts/reports/judge_validation/g6_consensus.json", "artifacts/reports/judge_validation/stress_v1_consensus.json",
          "artifacts/stress_v2/rejudge/S0_consensus.json", "artifacts/stress_v2/rejudge/S1_consensus.json",
          "artifacts/stress_v2/rejudge/S4_consensus.json", "artifacts/fp16/rejudge/F0_consensus.json",
          "artifacts/positive_control/rejudge/P0_consensus.json"]
C0 = ("Overhead camera view after a robot arm tried to stand a can upright on a round coaster. "
      "Is the can standing upright on the coaster now? Answer with exactly one word: YES or NO.")
REASON_TAIL = " Think briefly about what you see, then end with exactly one line: 'Answer: YES' or 'Answer: NO'."
VARIANTS = {   # at most 3 per condition (prereg §3); chosen on dev only
    "C1": {"p1": "This is the final overhead camera frame of a robot trial. The goal: a can stands upright on a round coaster. Is the can upright on the coaster?" + REASON_TAIL,
           "p2": "Overhead view of a desk after a robot pick-and-place trial. Locate the round coaster and the can. Success means the can is standing upright (you see its circular top) and its base is on the coaster. A can lying on its side, off the coaster, or still in the gripper is a failure. Is this a success?" + REASON_TAIL,
           "p3": "You are a strict inspector. Only answer YES if you clearly see a standing can (circular lid visible from above) resting on the round coaster; otherwise answer NO. Final overhead frame of a robot trial: is the can standing on the coaster?" + REASON_TAIL},
    "C2": {"v1": "These are the last 3 seconds of an overhead camera video of a robot trial. The goal: a can stands upright on a round coaster at the end. At the end of the clip, is the can upright on the coaster?" + REASON_TAIL,
           "v2": "Last 3 seconds of a robot pick-and-place video, seen from above. Watch whether the can tips over, falls, or ends off the round coaster. Success means that at the end the can stands upright on the coaster and the gripper has let go. Is this a success?" + REASON_TAIL,
           "v3": "You are a strict inspector watching the end of a robot trial from above. Answer YES only if at the end you clearly see the can standing upright on the round coaster; if it falls, lies on its side, or is off the coaster, answer NO." + REASON_TAIL}}

def seed_from(*parts):
    sys.path.insert(0, "src"); from edgeqgate.hashing import seed_from as s; return s(*parts)

def split(out, dirs):
    lab = {}
    for f in LABELS: lab.update({k: bool(v["success_geom"]) for k, v in json.load(open(f)).items()})
    trials = []
    for d in dirs:
        for p in sorted(glob.glob(f"{d}/*_top.mp4")):
            tid = os.path.basename(p)[:-len("_top.mp4")]
            if tid in lab: trials.append({"trial_id": tid, "video": p, "standing": lab[tid]})
    rng = np.random.default_rng(seed_from("PREREG-SEED-2026-09-14", "COSMOS-JUDGE/split/v1"))
    for cls in (True, False):
        idx = [i for i, t in enumerate(trials) if t["standing"] is cls]; rng.shuffle(idx)
        for j, i in enumerate(idx): trials[i]["set"] = "dev" if j < len(idx) // 3 else "eval"
    json.dump({"n": len(trials), "n_fail": sum(not t["standing"] for t in trials), "trials": trials}, open(out, "w"), indent=1)
    print(len(trials), "trials;", sum(not t["standing"] for t in trials), "failures;", {s: sum(t["set"] == s for t in trials) for s in ("dev", "eval")})

def frames(p, last_s=None, fps=None):
    import av
    c = av.open(p); st = c.streams.video[0]; fs = [(float(f.pts * st.time_base), f) for f in c.decode(st)]; c.close()
    if last_s is None: return [fs[-1][1].to_image()]
    t_end = fs[-1][0]; out, nxt = [], t_end - last_s
    for t, f in fs:
        if t >= nxt: out.append(f.to_image()); nxt += 1 / fps
    return out

def mp4_b64(imgs, fps=4):
    import av
    buf = io.BytesIO(); o = av.open(buf, "w", format="mp4"); s = o.add_stream("libx264", rate=fps)
    s.width, s.height, s.pix_fmt = imgs[0].width, imgs[0].height, "yuv420p"
    for im in imgs:
        for pk in s.encode(av.VideoFrame.from_image(im)): o.mux(pk)
    for pk in s.encode(): o.mux(pk)
    o.close(); return base64.b64encode(buf.getvalue()).decode()

def jpg_b64(im):
    b = io.BytesIO(); im.save(b, "JPEG", quality=85); return base64.b64encode(b.getvalue()).decode()

def parse(text, cond):
    t = (text or "").upper()
    if cond == "C0":
        return "YES" if t.strip().startswith("YES") else ("NO" if t.strip().startswith("NO") else None)
    m = re.findall(r"ANSWER\s*[:：]\s*(YES|NO)", t)
    return m[-1] if m else None

def run(splitp, cond, var, which, out):
    u = urllib.parse.urlparse(os.environ["COSMOS_URL"]); hdr = {"Authorization": "Bearer " + open(os.path.expanduser(os.environ["COSMOS_TOKEN_FILE"])).read().strip(), "Content-Type": "application/json"}
    conn = http.client.HTTPSConnection(u.netloc, timeout=120)
    prompt = C0 if cond == "C0" else VARIANTS[cond][var]; mt = 8 if cond == "C0" else 768
    T = [t for t in json.load(open(splitp))["trials"] if t["set"] == which]; res = []
    for t in T:
        if cond == "C2": media = {"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + mp4_b64(frames(t["video"], 3.0, 4))}}
        else: media = {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + jpg_b64(frames(t["video"])[0])}}
        body = json.dumps({"model": "nvidia/Cosmos-Reason2-2B", "max_tokens": mt, "temperature": 0,
                           "messages": [{"role": "user", "content": [media, {"type": "text", "text": prompt}]}]})
        txt, ms = None, None
        for _ in range(3):
            try:
                t0 = time.time(); conn.request("POST", "/v1/chat/completions", body=body, headers=hdr); d = json.loads(conn.getresponse().read())
                txt = d["choices"][0]["message"]["content"]; ms = (time.time() - t0) * 1000; break
            except Exception as e:
                txt = f"<error {type(e).__name__}: {str(e)[:80]}>"; conn = http.client.HTTPSConnection(u.netloc, timeout=120); time.sleep(2)
        res.append({"trial_id": t["trial_id"], "standing": t["standing"], "answer": parse(txt, cond), "latency_ms": ms, "raw": (txt or "")[-300:]})
        print(t["trial_id"], t["standing"], res[-1]["answer"], flush=True)
    json.dump({"cond": cond, "variant": var, "set": which, "prompt": prompt, "max_tokens": mt, "results": res}, open(out, "w"), indent=1)

def wilson(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [(c - h) / d, (c + h) / d]

def score(paths):
    for p in paths:
        R = json.load(open(p)); r = R["results"]; F = [x for x in r if not x["standing"]]; Sx = [x for x in r if x["standing"]]
        fr = sum(x["answer"] == "NO" for x in F); fa = sum(x["answer"] == "NO" for x in Sx); sr = sum(x["answer"] == "YES" for x in Sx); ab = sum(x["answer"] is None for x in r)
        lat = [x["latency_ms"] for x in r if x["latency_ms"]]
        m = {"cond": R["cond"], "variant": R["variant"], "set": R["set"], "n": len(r), "n_fail": len(F),
             "failure_recall": [fr, len(F), wilson(fr, len(F))], "false_alarm": [fa, len(Sx), wilson(fa, len(Sx))], "abstain": [ab, len(r)],
             "balanced_accuracy": ((fr / len(F) if F else 0) + (sr / len(Sx) if Sx else 0)) / 2, "latency_ms_median": float(np.median(lat)) if lat else None}
        print(json.dumps(m))

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "split": split(a[1], a[2:])
    elif a[0] == "run": run(*a[1:6])
    else: score(a[1:])
