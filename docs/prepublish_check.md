# Pre-publication secret check

## Run 1 — 2026-10-12 (repo private, 138 commits)

Method: the full history (`git rev-list --all`) and the working tree were scanned twice.
1. **Patterns**: PEM private-key headers, AWS access keys, Tavily, NVIDIA, OpenAI-style and Hugging Face tokens, AWS
   secret assignments, long Bearer tokens and JWTs.
2. **Actual values**: every credential value in `~/.config/edgeqgate/*`, 54 strings in total. These are the env file,
   the S3 credentials, the service-account private-key body and the endpoint token. Values were compared, never printed.

| Check | Result |
|---|---|
| Secret patterns, full history | **0 hits** |
| Actual credential values, full history | **0 hits** |
| Actual credential values, working tree (excluding `.git`, `.venv`) | **0 hits** |
| Files named like keys or credentials | only scripts that *check for* credentials and a probe result without secrets |

Not secrets, but public after release (decide before publishing):
- Nebius resource IDs: project (2 files), endpoint (1), service account and public-key ID (`docs/manual_actions.md`).
  These are not usable without credentials. The service-account key is rotated right after submission (user decision).
- Local paths `/home/chanseok/...` in 7 files.
- The git author email on every commit.

Repeat this check right before the repository is made public (`LOCK-4` checklist).
