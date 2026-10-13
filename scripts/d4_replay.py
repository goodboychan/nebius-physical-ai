"""Offline replay of the D4 Cosmos-Reason2 shadow supervisor and end-of-trial judge on saved overhead videos
(positive-control amendment 2, written before the trials). This is descriptive only (EX-3) and never used for an outcome.
- Shadow supervisor: every 15th frame (2 Hz at 30 fps), with so101_trial.py's D4_PROMPT for stress sessions
  ("... picks up a can ...").
- End judge: the last frame, with D4_JUDGE_PROMPT.
Both run at temperature 0 with max_tokens 8 and JPEG quality 85, as live. Differences from live: AV1-compressed frames,
and no live latency.
Usage: python d4_replay.py <video dir> <out.json>   env: COSMOS_URL, COSMOS_TOKEN_FILE"""
import base64, glob, http.client, io, json, os, sys, time, urllib.parse
import av

D4_PROMPT = ("Overhead camera view of a robot arm that picks up a can and stands it upright on a round coaster. "
             "Answer with exactly one word: CONTINUE if the task is proceeding normally, FALLBACK if the arm looks stuck or "
             "confused, ABORT if something is unsafe (the can falling off the table, the arm hitting something, a human hand "
             "in the workspace).")
D4_JUDGE_PROMPT = ("Overhead camera view after a robot arm tried to stand a can upright on a round coaster. "
                   "Is the can standing upright on the coaster now? Answer with exactly one word: YES or NO.")
u = urllib.parse.urlparse(os.environ["COSMOS_URL"])
hdr = {"Authorization": "Bearer " + open(os.path.expanduser(os.environ["COSMOS_TOKEN_FILE"])).read().strip(), "Content-Type": "application/json"}
conn = http.client.HTTPSConnection(u.netloc, timeout=30)

def ask(img, prompt):
    global conn
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=85)
    body = json.dumps({"model": "nvidia/Cosmos-Reason2-2B", "max_tokens": 8, "temperature": 0, "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}},
        {"type": "text", "text": prompt}]}]})
    for _ in range(3):
        try:
            conn.request("POST", "/v1/chat/completions", body=body, headers=hdr)
            return json.loads(conn.getresponse().read())["choices"][0]["message"]["content"].strip()
        except Exception:
            conn = http.client.HTTPSConnection(u.netloc, timeout=30); time.sleep(2)
    return None

def parse(t):
    t = (t or "").upper()
    return next((d for d in ("ABORT", "FALLBACK", "CONTINUE") if d in t), "UNKNOWN")

out = {}
for p in sorted(glob.glob(f"{sys.argv[1]}/*_top.mp4")):
    tid = os.path.basename(p)[:-len("_top.mp4")]; c = av.open(p); frames = []; last = None
    for i, f in enumerate(c.decode(c.streams.video[0])):
        if i % 15 == 0: frames.append(f.to_image())
        last = f
    c.close()
    dec = [parse(ask(im, D4_PROMPT)) for im in frames]
    out[tid] = {"n_verdicts": len(dec), "decisions": {d: dec.count(d) for d in set(dec)}, "end_judge": ask(last.to_image(), D4_JUDGE_PROMPT)}
    print(tid, out[tid]["decisions"], out[tid]["end_judge"], flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1)
