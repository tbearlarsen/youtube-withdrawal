#!/usr/bin/env bash
# Pull the latest code into the deploy checkout, rebuild/restart the live
# container on VM101, then verify it actually came up. See directives/deploy.md.
#
# Run by a Claude session that has (1) file access to /docker on VM101 and
# (2) SSH to VM101 as a docker-group user — e.g. the home-server session.
# The git pull runs locally (as VM101's `claude` user git refuses the checkout
# with "dubious ownership"); only `docker compose` goes over SSH.
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/docker/youtube-withdrawal}"
SSH_TARGET="${DEPLOY_SSH:-claude@10.0.0.101}"
SSH_KEY="${DEPLOY_SSH_KEY:-/docker/.claude-secrets/vm101_ssh_key}"
BACKUP_DIR="${DEPLOY_DIR}-data-backup"

if [ ! -r "$SSH_KEY" ]; then
    echo "FAILED: SSH key $SSH_KEY not readable (set DEPLOY_SSH_KEY). Nothing was changed."
    exit 1
fi

cd "$DEPLOY_DIR"

# 1. Protect live app state. data/*.json is written by the running app; a pull
#    must never replace or delete it (favorites.json/requested.json were once
#    tracked in git, and the commit that untracked them deletes them on pull).
rm -rf "$BACKUP_DIR"
cp -a data "$BACKUP_DIR"
echo "Backed up live data to $BACKUP_DIR"
# Restore even if the pull fails part-way (set -e would otherwise exit with data reset)
trap 'cp -a "$BACKUP_DIR"/. "$DEPLOY_DIR/data/"' EXIT

tracked=$(git ls-files 'data/*.json')
if [ -n "$tracked" ]; then
    # Reset to HEAD so the pull can't fail on the app's in-place edits;
    # the backup is restored right after.
    git checkout -- $tracked
fi

git pull --ff-only

cp -a "$BACKUP_DIR"/. data/
trap - EXIT
echo "Restored live data"

# 2. Rebuild and restart on VM101.
ssh -i "$SSH_KEY" -o BatchMode=yes "$SSH_TARGET" "cd $DEPLOY_DIR && docker compose up -d --build"

echo "Waiting for the container to settle..."
sleep 3

# 3. Verify.
if ! ssh -i "$SSH_KEY" -o BatchMode=yes "$SSH_TARGET" "docker ps --filter name=youtube-withdrawal --filter status=running" | grep -q youtube-withdrawal; then
    echo "FAILED: container is not running. Check: docker compose logs youtube-withdrawal (on VM101)"
    exit 1
fi

if curl -sf http://10.0.0.101:8008/ > /dev/null; then
    echo "OK: deployed $(git log --oneline -1) and responding at http://10.0.0.101:8008/"
else
    echo "FAILED: container is running but the health check did not respond."
    echo "Check TubeArchivist connectivity (TA_URL) and: docker compose logs youtube-withdrawal (on VM101)"
    exit 1
fi
