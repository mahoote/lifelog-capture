#!/bin/bash

cd /home/martin/lifelog-capture || exit 1

git checkout main || echo "Could not switch to main branch. Continuing anyway."
git fetch || echo "Could not fetch latest changes. Probably offline. Continuing anyway."
git pull || echo "Could not pull latest changes. Probably offline. Continuing anyway."

python -m src.main