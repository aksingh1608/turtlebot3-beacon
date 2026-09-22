#!/bin/bash
# shellcheck disable=SC1091
source /opt/beacon_env.sh
if [ -d /ws/src/turtlebot3-beacon ]; then
  cd /ws/src/turtlebot3-beacon
fi
exec "$@"
