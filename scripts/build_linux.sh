#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "==> Syncing dependencies..."
uv sync --group dev

echo "==> Building standalone binary..."
rm -rf build dist release

uv run python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onefile \
  --name expenses-tracker \
  --hidden-import PIL._tkinter_finder \
  --add-data expenses_tracker/locales:expenses_tracker/locales \
  run_gui.py

mkdir -p release
ARCH="$(uname -m)"
tar -czf "release/expenses-tracker-linux-${ARCH}.tar.gz" -C dist expenses-tracker

echo "Build Linux listo en: release/expenses-tracker-linux-${ARCH}.tar.gz"
