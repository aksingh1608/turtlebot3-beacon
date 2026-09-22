#!/usr/bin/env bash
# Start the Beacon container with the repo mounted and the display forwarded.
#
# Usage: docker/run.sh
#        docker/run.sh --gpu
#
# The repo appears at /ws/src/turtlebot3-beacon. Files written there
# are owned by the user who starts this script.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU=()
if [ "${1:-}" = "--gpu" ]; then
  GPU=(--gpus all --env NVIDIA_VISIBLE_DEVICES=all --env NVIDIA_DRIVER_CAPABILITIES=all)
elif [ -n "${1:-}" ]; then
  echo "usage: $0 [--gpu]"
  exit 1
fi

if [ -z "${DISPLAY:-}" ]; then
  echo "DISPLAY is empty. Start this from a desktop session so Gazebo can open."
  exit 1
fi

xhost +local:root >/dev/null
xhost +SI:localuser:"$(id -un)" >/dev/null || true

if docker ps -a --format '{{.Names}}' | grep -qx beacon; then
  echo "A container named beacon already exists."
  echo "Enter it with docker/exec.sh, or remove it with: docker rm -f beacon"
  exit 1
fi

args=(
  docker run -it --name beacon
  --user "$(id -u):$(id -g)"
  --network host
  --env DISPLAY="$DISPLAY"
  --env QT_X11_NO_MITSHM=1
  --env HOME=/tmp/beacon-home
  --volume /tmp/.X11-unix:/tmp/.X11-unix
  --volume "$ROOT:/ws/src/turtlebot3-beacon"
)
if [ "${#GPU[@]}" -gt 0 ]; then
  args+=("${GPU[@]}")
fi
args+=(beacon:humble bash)
exec "${args[@]}"
