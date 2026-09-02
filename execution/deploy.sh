#!/usr/bin/env bash
# Rebuild and restart the live container, then verify it actually came up.
# See directives/deploy.md for when to run this — never automatically on
# every commit, only when explicitly asked to deploy.
set -euo pipefail

cd "$(dirname "$0")/.."

git pull
docker compose up -d --build

echo "Waiting for the container to settle..."
sleep 3

if ! docker ps --filter name=youtube-withdrawal --filter status=running | grep -q youtube-withdrawal; then
    echo "FAILED: container is not running. Check: docker compose logs youtube-withdrawal"
    exit 1
fi

if curl -sf http://10.0.0.101:8008/ > /dev/null; then
    echo "OK: deployed and responding at http://10.0.0.101:8008/"
else
    echo "FAILED: container is running but the health check did not respond."
    echo "Check TubeArchivist connectivity (TA_URL) and: docker compose logs youtube-withdrawal"
    exit 1
fi
