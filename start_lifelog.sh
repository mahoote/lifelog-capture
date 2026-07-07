#!/bin/bash
set -euo pipefail

REPO_DIR="/home/martin/lifelog-capture"

cd "$REPO_DIR" || exit 1

git checkout main || echo "Could not switch to main branch. Continuing anyway."

fetch_ok=false
if git fetch; then
    fetch_ok=true
else
    echo "Could not fetch latest changes. Probably offline."

    # Wait for DNS/network to be up, helps when running at boot
    for i in 1 2 3 4 5; do
        getent hosts github.com >/dev/null 2>&1 && break
        echo "Waiting for DNS..."
        sleep 2
    done

    if git fetch; then
        fetch_ok=true
    else
        echo "Could not fetch latest changes. Probably offline. Continuing anyway."
    fi
fi

if [ "$fetch_ok" = true ]; then
    git merge --ff-only origin/main || echo "Could not merge latest changes. Continuing anyway."
fi

source .venv/bin/activate
python -m src.main
