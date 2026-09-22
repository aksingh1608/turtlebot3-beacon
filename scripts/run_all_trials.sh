#!/usr/bin/env bash
# Run trials 1 to 10 in order. Trial 1 starts with --fresh.
# Each trial waits for STOP or TIMEOUT. Then the results table is printed.
#
# Usage: scripts/run_all_trials.sh
# The simulation must already be running.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for n in $(seq 1 10); do
  if [ "$n" = 1 ]; then
    "$ROOT/run_trial.sh" --fresh 1
  else
    "$ROOT/run_trial.sh" "$n"
  fi
done

if [ -n "${BEACON_TRIALS_DIR:-}" ]; then
  TRIALS_DIR="$BEACON_TRIALS_DIR"
else
  TRIALS_DIR="$(python3 -c 'from beacon.spawn_marker import resolve_trials_dir; print(resolve_trials_dir())' 2>/dev/null || true)"
  if [ -z "$TRIALS_DIR" ]; then
    TRIALS_DIR="$(cd "$ROOT/../beacon/trials" && pwd)"
  fi
fi

echo "== results"
RESULTS="$TRIALS_DIR/results.csv"
if [ -f "$RESULTS" ]; then
  cat "$RESULTS"
else
  echo "(no results.csv at $RESULTS)"
  exit 1
fi
