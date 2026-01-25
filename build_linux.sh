#!/usr/bin/env bash
set -euo pipefail

echo "Building Linux app..."
if command -v apt-get >/dev/null 2>&1; then
	sudo apt-get update
	sudo apt-get install -y libgtk-3-dev libasound2-dev pkg-config build-essential
elif command -v pacman >/dev/null 2>&1; then
	sudo pacman -Syu --noconfirm
	sudo pacman -S --noconfirm gtk3 alsa-lib pkgconf base-devel
elif command -v dnf >/dev/null 2>&1; then
	sudo dnf install -y gtk3-devel alsa-lib-devel pkgconf-pkg-config gcc make
elif command -v yum >/dev/null 2>&1; then
	sudo yum install -y gtk3-devel alsa-lib-devel pkgconfig gcc make
elif command -v zypper >/dev/null 2>&1; then
	sudo zypper install -y gtk3-devel alsa-devel pkg-config gcc make
fi
flet build linux --cleanup-app --cleanup-packages

python3 scripts/patch_flet_build.py

echo "Done."
