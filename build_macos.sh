#!/usr/bin/env bash
set -euo pipefail

echo "Building macOS app..."
flet build macos --cleanup-app --cleanup-packages

python3 scripts/patch_flet_build.py

echo "Done."
