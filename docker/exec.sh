#!/usr/bin/env bash
# Open a second shell in the running beacon container, with Humble sourced.
set -euo pipefail
exec docker exec -it beacon bash -c 'source /opt/beacon_env.sh; exec bash'
