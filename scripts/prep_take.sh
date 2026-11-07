#!/usr/bin/env bash
# Get everything ready for a clean demo take (macOS, local Switch server run by Switch Console).
#   1. Mattermost healthy (restart it if it stalled; it does that on a small, busy Mac)
#   2. Shop and memory reset to the start of the demo
#   3. Scribe restarted so it reads the fresh memory
# Usage: ./scripts/prep_take.sh [server-url]   (default http://localhost:60282; Console shows the real port)
set -euo pipefail
cd "$(dirname "$0")/.."
URL="${1:-${SWITCH_URL:-http://localhost:60282}}"
MM=switchdash-local-mattermost-mattermost-1

health() { docker inspect --format '{{.State.Health.Status}}' "$MM" 2>/dev/null || echo missing; }

if [ "$(health)" != "healthy" ]; then
  echo "Mattermost is $(health); restarting it..."
  docker restart "$MM" >/dev/null
  for _ in $(seq 1 24); do [ "$(health)" = "healthy" ] && break; sleep 8; done
fi
echo "Mattermost: $(health)"

./scripts/reset_demo.sh

pkill -f 'scribe.agent run' 2>/dev/null || true
sleep 1
SWITCH_URL="$URL" nohup .venv/bin/python -m scribe.agent run > .scribe.log 2>&1 &
sleep 4
pgrep -f 'scribe.agent run' >/dev/null && echo "Scribe: running" || { echo "Scribe did not start; see .scribe.log"; exit 1; }
echo "Ready. Post your first message now."
