#!/bin/bash
# D4 감독자 모델 nvidia/Cosmos-Reason2-2B를 Nebius AI Cloud 엔드포인트(L40S, vLLM)로 띄운다.
# 가중치는 우리 S3 버킷(models/Cosmos-Reason2-2B)에서 읽으므로 엔드포인트에 HF 토큰을 넣지 않는다.
# 토큰은 ~/.config/edgeqgate/cosmos_endpoint_token (600)에 두고 출력하지 않는다.
# 평소에는 멈춰 두고(stop) 실기 세션 때만 켠다: nebius ai endpoint start|stop <id>
set -euo pipefail
T=~/.config/edgeqgate/cosmos_endpoint_token
[ -f "$T" ] || (umask 077; python3 -c "import secrets;print(secrets.token_urlsafe(32))" > "$T")
AWS_CONFIG_FILE="${AWS_CONFIG_FILE:?endpoint_url·region이 든 AWS config}" \
AWS_SHARED_CREDENTIALS_FILE=~/.config/edgeqgate/s3_credentials \
nebius ai endpoint create --async --parent-id project-e00dkv33pr00a5476qtybq --name "${NAME:-cosmos-reason2-d4}" \
  --image vllm/vllm-openai:v0.29.0-x86_64-cu129 --platform gpu-l40s-a --disk-size 100Gi \
  --container-port 8000 --auth token --token "$(cat "$T")" \
  --volume "s3://edgeqgate-audit:/s3:ro:edgeqgate" \
  --args "/s3/models/Cosmos-Reason2-2B --served-model-name nvidia/Cosmos-Reason2-2B --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.85" \
  2>&1 | grep -viE "token|secret"
