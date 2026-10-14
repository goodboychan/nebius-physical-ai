#!/usr/bin/env bash
# Create the short-lived Nebius Managed MLflow cluster (decision_log 2026-10-14: create -> publish -> capture -> delete).
# Credentials: ~/.config/edgeqgate/mlflow_admin. One line = password (username edgeqgate); two lines = username, password.
# The password is never printed. Run with NB_PROFILE=mycloud (the user's own federated login): the default
# edgeqgate-cloud service account is least-privilege and cannot create MLflow clusters.
set -euo pipefail
f=~/.config/edgeqgate/mlflow_admin
if [ "$(wc -l < "$f")" -ge 2 ]; then U=$(sed -n 1p "$f"); P=$(sed -n 2p "$f"); else U=edgeqgate; P=$(sed -n 1p "$f"); fi
nebius ${NB_PROFILE:+--profile "$NB_PROFILE"} msp mlflow v1alpha1 cluster create \
  --parent-id project-e00dkv33pr00a5476qtybq --name edgeqgate-mlflow \
  --description "QuantGate results (populated from committed artifacts)" \
  --admin-username "$U" --admin-password "$P" \
  --network-id vpcnetwork-e00xnw7a6t3nn1w0er --service-account-id serviceaccount-e00d14c3pxd5z9t7b5 \
  --public-access --async --format json | grep -v -i password | head -8
