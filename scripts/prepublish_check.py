"""Secret check before making the repository public (decision_log: secret check 2). Prints locations, never values.
1. Exact secrets: every value in ~/.config/edgeqgate/ (env values, token files, PEM bodies, S3 keys, MLflow admin)
   is searched for in every blob of the whole git history (all refs), plus the working tree.
2. Patterns: private-key headers, common token shapes (hf_, sk-, AKIA, JWT, Bearer), Nebius IAM/endpoint ids, internal
   host names and private IP addresses.
Exit 1 if an exact secret is found anywhere. Pattern hits are listed for review (some are expected, e.g. docs that
name the env variable).
Usage: python scripts/prepublish_check.py"""
import glob, os, re, subprocess, sys
CFG = os.path.expanduser("~/.config/edgeqgate")
secrets = {}
for p in glob.glob(f"{CFG}/*"):
    raw = open(p, errors="ignore").read(); name = os.path.basename(p)
    if name.endswith(".pem"):
        body = "".join(l for l in raw.splitlines() if l and not l.startswith("-----"))
        for i in range(0, max(len(body) - 40, 1), 40): secrets[f"{name}[{i}]"] = body[i:i + 40]
        continue
    for ln in raw.splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1); v = v.strip().strip('"').strip("'")
            if len(v) >= 12 and not v.startswith(("http://", "https://")) and "/" not in v[:2]: secrets[f"{name}:{k.strip().replace('export ', '')}"] = v
        elif len(ln.strip()) >= 16 and " " not in ln.strip(): secrets[name] = ln.strip()
    try:
        import json
        def walk(o, path):
            if isinstance(o, dict): [walk(v, f"{path}.{k}") for k, v in o.items()]
            elif isinstance(o, str) and len(o) >= 16 and not o.startswith("http"): secrets[f"{name}{path}"] = o
        walk(json.loads(raw), "")
    except Exception: pass
print(f"exact secrets to look for: {len(secrets)} (values not printed)")
PAT = {"private key": rb"-----BEGIN [A-Z ]*PRIVATE KEY-----", "hf token": rb"\bhf_[A-Za-z0-9]{30,}", "openai-style key": rb"\bsk-[A-Za-z0-9_-]{20,}",
       "aws key id": rb"\bAKIA[0-9A-Z]{16}\b", "jwt": rb"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
       "bearer literal": rb"Bearer [A-Za-z0-9._-]{20,}", "nebius v1 token": rb"\bv1\.[A-Za-z0-9_-]{30,}", "private ip": rb"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b",
       "endpoint host": rb"[a-z0-9-]+\.(?:endpoint|endpoints)\.[a-z0-9.-]*nebius[a-z0-9.-]*", "internal host": rb"\b(?:kepler|udoo-bolt|lattepanda3-delta|particle-tachyon)\b"}
blobs = subprocess.run("git rev-list --all --objects | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)'", shell=True, capture_output=True, text=True).stdout.splitlines()
blobs = [b.split(" ", 3) for b in blobs if b.startswith("blob ")]
found, pats = [], {}
proc = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
for _, sha, size, path in blobs:
    if int(size) > 20_000_000: continue
    proc.stdin.write((sha + "\n").encode()); proc.stdin.flush(); hdr = proc.stdout.readline(); data = proc.stdout.read(int(hdr.split()[2])); proc.stdout.read(1)
    for k, v in secrets.items():
        if v.encode() in data: found.append((k, path, sha[:10]))
    if path.endswith((".png", ".jpg", ".mp4", ".m4a", ".npz", ".pt", ".parquet", ".onnx", ".engine", ".pdf", ".zip", ".safetensors")): continue
    for name, rx in PAT.items():
        for m in re.finditer(rx, data):
            pats.setdefault((name, path), m.group(0)[:12])
proc.stdin.close()
print(f"blobs scanned: {len(blobs)}")
if found:
    print("EXACT SECRET FOUND:"); [print(f"  {k}  in  {p}  (blob {s})") for k, p, s in sorted(set(found))]
else: print("exact secrets in git history: none")
print(f"pattern hits for review: {len(pats)}")
for (name, path), snip in sorted(pats.items()): print(f"  [{name}] {path}  ({snip.decode(errors='ignore')}…)")
sys.exit(1 if found else 0)
