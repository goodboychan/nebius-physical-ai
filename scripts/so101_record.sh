#!/bin/bash
# SO-101 데모 녹화 (단일팔, 카메라 2대). 수집 설정은 여기 한 곳에서만 바꾼다.
#   사용: ~/so101_record.sh <이름> <에피소드 수> <에피소드 길이(초)> [리셋 시간(초)]
#   예:   ~/so101_record.sh demo 20 25 10
#   같은 이름으로 다시 실행하면 기존 데이터셋에 이어서 녹화한다(resume).
#   녹화 중 키: n = 이 에피소드 일찍 끝내기, r = 방금 에피소드 다시 녹화, q = 녹화 종료
set -e
NAME=${1:?이름}; N=${2:?에피소드 수}; T=${3:?에피소드 길이}; R=${4:-10}
source ~/lerobot-env/.venv/bin/activate
CAMS='{"top": {"type": "opencv", "index_or_path": "/dev/so101_cam_top", "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"}, "wrist": {"type": "openmv", "fps": 30}}'
/usr/local/bin/so101-cam-lock /dev/so101_cam_top >/dev/null      # 오버헤드 수동 설정 재적용
~/so101_omv_check.sh | tee /dev/stderr | grep -q "^OK" \
  || { echo "손목 카메라가 응답하지 않습니다. AE3 USB 케이블을 뽑았다 10초 뒤 다시 꽂고 다시 실행하세요"; exit 1; }
DS="$HOME/so101_data/${NAME}"
if [ -f "$DS/meta/info.json" ] && [ ! -d "$DS/meta/episodes" ]; then   # 에피소드 0개로 끝난 빈 데이터셋은 옆으로 치운다
  mv "$DS" "$DS.empty-$(date +%m%d_%H%M%S)"; echo "빈 데이터셋을 옮겼습니다: $DS.empty-*"
fi
RESUME=false; [ -d "$DS/meta/episodes" ] && RESUME=true
echo "dataset ~/so101_data/${NAME}  resume=${RESUME}  episodes=${N}  ${T}s + reset ${R}s"
lerobot-record \
  --robot.type=so101_follower --robot.port=/dev/so101_follower --robot.id=follower \
  --robot.cameras="$CAMS" \
  --teleop.type=so101_leader --teleop.port=/dev/so101_leader --teleop.id=leader \
  --dataset.repo_id="local/so101_${NAME}" \
  --dataset.root="$HOME/so101_data/${NAME}" \
  --dataset.single_task="Pick up the cola can and place it upright on the coaster" \
  --dataset.fps=30 \
  --dataset.num_episodes="$N" --dataset.episode_time_s="$T" --dataset.reset_time_s="$R" \
  --dataset.push_to_hub=false --resume="$RESUME"
