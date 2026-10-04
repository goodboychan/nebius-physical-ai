#!/bin/bash
# OpenMV IDE(openmv-qtc-14.0.2 settings.json)의 AE3 레시피 그대로. 파일시스템 지우기(-a 5)는 하지 않는다.
set -e
cd ~/omv_fw/OPENMV_AE3
D=37c5:96e3
echo "[$(date +%T)] waiting for AE3 bootloader ($D) ..."
sudo dfu-util -w -d $D -a 1 -D firmware_M55_HP.bin
sudo dfu-util    -d $D -a 2 -D firmware_M55_HE.bin
sudo dfu-util    -d $D -a 3 -D romfs1.img
sudo dfu-util    -d $D -a 6 -D romfs0.img -R
echo "[$(date +%T)] FLASH_DONE"
