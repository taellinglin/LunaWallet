#!/usr/bin/env bash
set -euo pipefail

echo "Building Linux app..."
flet build linux --cleanup-app --cleanup-packages

python3 scripts/patch_flet_build.py

echo "Done."
