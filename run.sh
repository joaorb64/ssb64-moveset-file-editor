#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "Checking for pipenv..."
python3 -m pip install --user --upgrade pipenv --quiet || true

echo "Installing/updating dependencies..."
python3 -m pipenv install

echo "Launching SSB64 Moveset Editor..."
python3 -m pipenv run python Main.py
