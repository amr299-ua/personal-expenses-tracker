#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR"

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements-build.txt

rm -rf build dist release
"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onefile \
  --name expenses-tracker \
  run_gui.py

mkdir -p release
ARCH="$(uname -m)"
tar -czf "release/expenses-tracker-macos-${ARCH}.tar.gz" -C dist expenses-tracker

echo "Build macOS listo en: release/expenses-tracker-macos-${ARCH}.tar.gz"
