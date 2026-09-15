#!/bin/sh
set -e
mkdir -p /app/edgeqgate
for f in __init__ hashing scores audit_buffer splits grid; do
  cp /inject/${f}.py /app/edgeqgate/${f}.py
done
cp /inject/payload.json /app/payload.json
cp /inject/audit_job.py /app/audit_job.py
pip install -q --no-cache-dir numpy PyYAML >/dev/null 2>&1
exec python /app/audit_job.py
