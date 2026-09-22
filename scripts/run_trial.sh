#!/usr/bin/env bash
# Run one Beacon trial: spawn the marker, wait for STOP or TIMEOUT, print the result row.
#
# Usage:   scripts/run_trial.sh N
# All ten: for n in $(seq 1 10); do scripts/run_trial.sh "$n"; done
#
# Environment overrides:
#   BEACON_WS          workspace root, default ~/ros2_ws
#   BEACON_TRIALS_DIR  folder with positions.csv, logs and results.csv
#                      default <install prefix>/share/beacon/trials
#   BEACON_WAIT_S      seconds to wait for STOP or TIMEOUT, default 90
#
# The simulation must already be running: ros2 launch beacon sim.launch.py

set -euo pipefail

N="${1:-}"
if [ -z "$N" ]; then
  echo "usage: $0 N    (N is the trial number in positions.csv)"
  exit 1
fi

WS="${BEACON_WS:-$HOME/ros2_ws}"
WAIT_S="${BEACON_WAIT_S:-90}"

# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
# shellcheck disable=SC1091
source "$WS/install/setup.bash"

TRIALS_DIR="${BEACON_TRIALS_DIR:-$(ros2 pkg prefix beacon)/share/beacon/trials}"

echo "== trial $N (trials dir: $TRIALS_DIR)"
ros2 run beacon spawn_marker --trial "$N" --trials-dir "$TRIALS_DIR"

STATE_LOG="$(mktemp)"
PYTHONUNBUFFERED=1 ros2 topic echo /beacon/state std_msgs/msg/String > "$STATE_LOG" 2>/dev/null &
ECHO_PID=$!
cleanup() {
  kill "$ECHO_PID" 2>/dev/null || true
  rm -f "$STATE_LOG"
}
trap cleanup EXIT

deadline=$(( $(date +%s) + WAIT_S ))
final=""
last_shown=""
while [ "$(date +%s)" -lt "$deadline" ]; do
  sleep 0.5
  last="$(grep -E '^data: ' "$STATE_LOG" | tail -n 1 | sed 's/^data: //')"
  if [ -n "$last" ] && [ "$last" != "$last_shown" ]; then
    echo "   state: $last"
    last_shown="$last"
  fi
  # Only accept STOP or TIMEOUT once an active state has been seen for this trial.
  if grep -q -E '^data: (SEARCH|ALIGN|APPROACH)$' "$STATE_LOG"; then
    case "$last" in
      STOP|TIMEOUT) final="$last"; break ;;
    esac
  fi
done

if [ -z "$final" ]; then
  echo "== trial $N: no STOP or TIMEOUT within $WAIT_S s. Is the controller running?"
  exit 2
fi

sleep 1
echo "== trial $N finished with $final"
RESULTS="$TRIALS_DIR/results.csv"
if [ -f "$RESULTS" ]; then
  head -n 1 "$RESULTS"
  grep -E "^$N," "$RESULTS" | tail -n 1 || echo "(no row for trial $N yet)"
else
  echo "(no results.csv at $RESULTS yet)"
fi
echo "   log: $TRIALS_DIR/logs/trial_$N.csv"
