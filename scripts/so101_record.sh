#!/bin/bash
# SO-101 데모 녹화 (단일팔, 카메라 2대). 수집 설정은 여기 한 곳에서만 바꾼다.
#   사용: ~/so101_record.sh <이름> <에피소드 수> <에피소드 길이(초)> [리셋 시간(초)]
#   예:   ~/so101_record.sh test 2 15 10
set -e
NAME=${1:?이름}; N=${2:?에피소드 수}; T=${3:?에피소드 길이}; R=${4:-10}
source ~/lerobot-env/.venv/bin/activate
CAMS='{"top": {"type": "opencv", "index_or_path": "/dev/so101_cam_top", "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"}, "wrist": {"type": "openmv", "fps": 30}}'
/usr/local/bin/so101-cam-lock /dev/so101_cam_top >/dev/null      # 오버헤드 수동 설정 재적용
lerobot-record \
  --robot.type=so101_follower --robot.port=/dev/so101_follower --robot.id=follower \
  --robot.cameras="$CAMS" \
  --teleop.type=so101_leader --teleop.port=/dev/so101_leader --teleop.id=leader \
  --dataset.repo_id="local/so101_${NAME}" \
  --dataset.root="$HOME/so101_data/${NAME}" \
  --dataset.single_task="Pick up the beer can" \
  --dataset.fps=30 \
  --dataset.num_episodes="$N" --dataset.episode_time_s="$T" --dataset.reset_time_s="$R" \
  --dataset.push_to_hub=false
