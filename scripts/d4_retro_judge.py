"""D4 AI-judge, retrospective on G6 (exploratory, decision_log 2026-10-11). Written before any query is sent.

For each G6 trial (main 225 + retest 20), the last frame of the overhead video goes to Cosmos-Reason2-2B with the
same end-of-trial question that the stress runner asks (so101_trial.py D4_JUDGE_PROMPT). The answer is compared with:
  - the criterion outcome (sealed log `success`: judge + released + no contact)
  - the automatic geometric judge alone (`judge_auto.success`)
  - the operator-reported near misses (can hit the floor but the trial succeeded)
It never changes any G6 outcome. Temperature 0, max_tokens 8, JPEG quality 85 (the runner's settings).
The video frame is AV1-compressed; the live runner sends the raw camera frame. This difference is reported.

Usage: python d4_retro_judge.py <video_dir with main/ and retest/> <unsealed_dir> <out.json>
Env: COSMOS_URL, COSMOS_TOKEN_FILE"""
import base64, http.client, io, json, os, sys, time, urllib.parse
import av
from PIL import Image

PROMPT = ("Overhead camera view after a robot arm tried to stand a can upright on a round coaster. "
          "Is the can standing upright on the coaster now? Answer with exactly one word: YES or NO.")
NEAR_MISS = {153, 182, 192, 205, 209, 224}

vdir, udir, outp = sys.argv[1:4]
u = urllib.parse.urlparse(os.environ["COSMOS_URL"])
hdr = {"Authorization": "Bearer " + open(os.path.expanduser(os.environ["COSMOS_TOKEN_FILE"])).read().strip(),
       "Content-Type": "application/json"}
conn = http.client.HTTPSConnection(u.netloc, timeout=30)


def ask(img):
    global conn
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=85)
    body = json.dumps({"model": "nvidia/Cosmos-Reason2-2B", "max_tokens": 8, "temperature": 0, "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}},
        {"type": "text", "text": PROMPT}]}]})
    for attempt in range(3):
        try:
            t = time.perf_counter(); conn.request("POST", "/v1/chat/completions", body=body, headers=hdr)
            d = json.loads(conn.getresponse().read())
            return d["choices"][0]["message"]["content"].strip(), (time.perf_counter() - t) * 1000
        except Exception:
            conn = http.client.HTTPSConnection(u.netloc, timeout=30); time.sleep(2)
    return None, None


def last_frame(path):
    c = av.open(path); last = None
    for f in c.decode(c.streams.video[0]): last = f
    c.close(); return last.to_image()


rows = []
for sess in ("main", "retest"):
    for l in open(os.path.join(udir, f"g6_{sess}_sealed.jsonl")):
        r = json.loads(l)
        if r.get("invalid"): continue
        p = os.path.join(vdir, sess, r["trial_id"] + "_top.mp4")
        ans, ms = ask(last_frame(p))
        a = (ans or "").upper().rstrip(".")
        rows.append({"session": sess, "trial": r["trial"], "cell": r["cell"], "success": r["success"],
                     "judge_auto": bool(r["judge_auto"].get("success")), "near_miss": sess == "main" and r["trial"] in NEAR_MISS,
                     "answer": ans, "yes": a == "YES" if a in ("YES", "NO") else None, "latency_ms": ms})
        print(sess, r["trial"], r["success"], ans, flush=True)


def cm(rs, key):
    c = {"YES_pos": 0, "YES_neg": 0, "NO_pos": 0, "NO_neg": 0, "other": 0}
    for r in rs:
        if r["yes"] is None: c["other"] += 1
        else: c[f"{'YES' if r['yes'] else 'NO'}_{'pos' if r[key] else 'neg'}"] += 1
    n = c["YES_pos"] + c["YES_neg"] + c["NO_pos"] + c["NO_neg"]
    c["agreement"] = (c["YES_pos"] + c["NO_neg"]) / n if n else None
    c["failure_recall"] = c["NO_neg"] / (c["NO_neg"] + c["YES_neg"]) if c["NO_neg"] + c["YES_neg"] else None
    c["success_recall"] = c["YES_pos"] / (c["YES_pos"] + c["NO_pos"]) if c["YES_pos"] + c["NO_pos"] else None
    return c


rep = {"exploratory": True, "prompt": PROMPT, "n": len(rows), "vs_criterion": cm(rows, "success"),
       "vs_judge_auto": cm(rows, "judge_auto"),
       "near_miss_answers": {r["trial"]: r["answer"] for r in rows if r["near_miss"]},
       "failure_answers": {f"{r['session']}{r['trial']}": r["answer"] for r in rows if not r["success"]}, "rows": rows}
json.dump(rep, open(outp, "w"), indent=1)
print(json.dumps({k: rep[k] for k in ("n", "vs_criterion", "vs_judge_auto", "near_miss_answers", "failure_answers")}, indent=1))
