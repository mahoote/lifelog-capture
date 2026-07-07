#!/bin/bash
set -euo pipefail

REPO_DIR="/home/martin/lifelog-capture"

cd "$REPO_DIR" || exit 1

git checkout main || echo "Could not switch to main branch. Continuing anyway."

# Wait for DNS/network to be up, helps when running at boot
for i in 1 2 3 4 5; do
  getent hosts github.com >/dev/null 2>&1 && break
  echo "Waiting for DNS..."
  sleep 2
done

git fetch || echo "Could not fetch latest changes. Probably offline. Continuing anyway."
git pull  || echo "Could not pull latest changes. Probably offline. Continuing anyway."

source .venv/bin/activate

python -m src.main