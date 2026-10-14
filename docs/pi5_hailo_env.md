# Raspberry Pi 5 + Hailo-8 environment (mirrors the Orin LeRobot setup, 2026-10-14)

Host `raspberrypi-hailo`: Raspberry Pi 5 (8 GB), Debian 12, Hailo-8 (firmware 4.20.0), HailoRT 4.20.0 (system
Python 3.11 bindings only).

## Two Python environments, as on Orin

| | Orin | Pi 5 |
|---|---|---|
| LeRobot runner | `~/lerobot-env/.venv`, CPython 3.12.13 | `~/lerobot-env/.venv`, CPython 3.12.13 (uv) |
| Policy backend | TensorRT server (`trt_policy_server.py`, separate process) | HailoRT, system Python 3.11 (`~/edgeqgate_hailo/venv`, `--system-site-packages` + onnxruntime 1.24.2), separate process |

LeRobot 0.6.1 requires Python ≥ 3.12 and the HailoRT bindings exist only for 3.11, so the runner and the policy backend
cannot share one interpreter. That is the same process split the Orin runner already uses.

## Package set

The Orin freeze list (`uv pip freeze`, 90 packages) was installed with `--no-deps`. The differences are:

- torch 2.11.0 and torchvision 0.26.0 are the `+cpu` builds from `download.pytorch.org/whl/cpu`.
- Not installed: the CUDA/NVIDIA wheels (`nvidia-*`, `cuda-*`, `triton`).
- Not installed: `torchcodec`. The aarch64 PyPI wheel links CUDA (`libnvrtc.so.13`), and there is no aarch64 CPU
  build. LeRobot then falls back to PyAV (av 15.1.0) for video decoding. Encoding is unaffected.
- The `lerobot_camera_openmv` plugin is the same source (copied from Orin `~/plugins`), installed editable.
- Everything else is pinned to the same versions: lerobot 0.6.1, numpy 2.2.6, opencv-python-headless 4.13.0.92,
  feetech-servo-sdk 1.0.0, av 15.1.0, datasets 4.8.5 and the rest.

## Devices

- These were copied from Orin: `/etc/udev/rules.d/{70-so101-mm-ignore,99-so101,99-so101-cam,99-so101-omv,99-so101-wrist}.rules`
  and `/usr/local/bin/so101-{cam,wrist}-lock`. They give the same names: `/dev/so101_follower`, `/dev/so101_leader`,
  `/dev/so101_cam_top`, `/dev/so101_cam_wrist_omv`.
- One change: the old Sonix wrist rule dropped its Orin-specific `ID_PATH` match.
- Calibration: `~/.cache/huggingface/lerobot/calibration/{robots/so_follower/follower.json, teleoperators/so_leader/leader.json}`
  copied from Orin.
- The user is in `dialout` and `video`.

## Rebuild

```bash
uv venv --python 3.12 ~/lerobot-env/.venv
uv pip install --python ~/lerobot-env/.venv/bin/python torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python ~/lerobot-env/.venv/bin/python --no-deps -r configs/pi5_lerobot_reqs.txt   # Orin freeze minus nvidia-*, cuda-*, triton, torch, torchvision, torchcodec, -e
uv pip install --python ~/lerobot-env/.venv/bin/python --no-deps -e ~/plugins/lerobot_camera_openmv
```
