#!/bin/bash
# 녹화 전 손목 카메라(OpenMV AE3) 연결 시험(약 10초). 이전 녹화가 카메라 스트리밍 중에 비정상 종료되면
# 보드 링크가 막혀 다음 연결이 멈춘다(2026-10-06). 소프트웨어 USB 재인증으로는 풀리지 않았고
# (재인증 뒤 보드가 리셋을 반복함), 케이블을 뽑았다 꽂아야 풀린다. 그래서 막혔는지만 미리 확인한다.
timeout 45 ~/lerobot-env/.venv/bin/python - <<'PY' 2>/dev/null | grep -E "^(OK|FAIL)"
import time
from lerobot.utils.import_utils import register_third_party_plugins; register_third_party_plugins()
from lerobot_camera_openmv import OpenMVCamera, OpenMVCameraConfig
try:
    c = OpenMVCamera(OpenMVCameraConfig(fps=30)); c.connect(); time.sleep(1)
    f = c.read_latest(max_age_ms=500); c.disconnect(); print("OK wrist camera", f.shape)
except Exception as e:
    print("FAIL", e)
PY
