#!/usr/bin/env bash
set -euo pipefail

echo "Building Linux app..."
if command -v apt-get >/dev/null 2>&1; then
	sudo apt-get update
	sudo apt-get install -y libgtk-3-dev libasound2-dev
fi
flet build linux --cleanup-app --cleanup-packages

python3 scripts/patch_flet_build.py

echo "Done."
