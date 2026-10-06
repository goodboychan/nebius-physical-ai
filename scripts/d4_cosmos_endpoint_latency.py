"""D4 Cosmos-Reason2 Nebius 엔드포인트 지연 측정 (표준 라이브러리만). keep-alive 연결 1개, 22회 중 앞 2회 제외.
사용: U=<엔드포인트 URL> TOKEN=<토큰> python3 d4_cosmos_endpoint_latency.py <jpeg>"""
import os, json, time, base64, http.client, urllib.parse, statistics, sys
u=urllib.parse.urlparse(os.environ["U"]); h={"Authorization":"Bearer "+os.environ["TOKEN"],"Content-Type":"application/json"}
c=http.client.HTTPSConnection(u.netloc, timeout=120)
for i in range(30):
    try:
        c.request("GET","/v1/models",headers=h); r=c.getresponse(); b=r.read()
        if r.status==200: print("models", [m["id"] for m in json.loads(b)["data"]]); break
        print("status", r.status, b[:120])
    except Exception as e:
        print("wait", e); c=http.client.HTTPSConnection(u.netloc, timeout=120)
    time.sleep(10)
uri="data:image/jpeg;base64,"+base64.b64encode(open(sys.argv[1],"rb").read()).decode()
prompt="You supervise a robot arm placing a cola can on a coaster. Answer with one word: CONTINUE, FALLBACK, or ABORT."
body=json.dumps({"model":"nvidia/Cosmos-Reason2-2B","max_tokens":8,"temperature":0,"messages":[{"role":"user","content":[{"type":"image_url","image_url":{"url":uri}},{"type":"text","text":prompt}]}]})
lat=[]; outs=set()
for i in range(22):
    t=time.perf_counter(); c.request("POST","/v1/chat/completions",body=body,headers=h); r=c.getresponse(); d=json.loads(r.read()); ms=(time.perf_counter()-t)*1000
    if i>=2: lat.append(ms)
    outs.add(d["choices"][0]["message"]["content"].strip() if r.status==200 else str(d)[:100])
lat.sort(); print("n",len(lat),"median %.0f ms  p95 %.0f ms  min %.0f"%(statistics.median(lat), lat[int(0.95*len(lat))-1], lat[0]), "outputs", outs)
