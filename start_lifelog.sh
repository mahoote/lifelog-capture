#!/bin/bash

cd /home/martin/lifelog-capture || exit 1

git checkout main || exit 1
git fetch || exit 1
git pull || exit 1

python -m src.main