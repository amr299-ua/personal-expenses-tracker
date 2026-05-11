#!/usr/bin/env bash
# Build a .deb package for Personal Expenses Tracker.
# Requires: PyInstaller, dpkg-deb, fakeroot
set -euo pipefail

APP_NAME="expenses-tracker"
VERSION="0.2.0"
ARCH="amd64"
MAINTAINER="Personal Expenses Tracker Team"
DESCRIPTION="Personal Expenses Tracker - Desktop application to track income and expenses"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"
RELEASE_DIR="$PROJECT_DIR/release"
DEB_ROOT="$PROJECT_DIR/build/deb"
DEB_NAME="${APP_NAME}_${VERSION}_${ARCH}"

echo "==> Building PyInstaller binary..."
cd "$PROJECT_DIR"
python -m PyInstaller expenses-tracker.spec --clean --noconfirm

echo "==> Preparing .deb directory structure..."
rm -rf "$DEB_ROOT"
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/usr/bin"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DEB_ROOT/usr/share/doc/$APP_NAME"

# Copy binary
cp "$DIST_DIR/$APP_NAME/$APP_NAME" "$DEB_ROOT/usr/bin/"

# Copy desktop file
cp "$PROJECT_DIR/resources/$APP_NAME.desktop" "$DEB_ROOT/usr/share/applications/"

# Create copyright
cat > "$DEB_ROOT/usr/share/doc/$APP_NAME/copyright" << 'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: personal-expenses-tracker
Source: https://github.com/user/personal-expenses-tracker

Files: *
Copyright: 2026 Personal Expenses Tracker Team
License: MIT
EOF

# Create control file
cat > "$DEB_ROOT/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $VERSION
Architecture: $ARCH
Maintainer: $MAINTAINER
Installed-Size: $(du -sk "$DEB_ROOT" | cut -f1)
Depends: libc6, libpython3.10 | libpython3.11 | libpython3.12, python3-tk
Section: utils
Priority: optional
Homepage: https://github.com/user/personal-expenses-tracker
Description: $DESCRIPTION
 A desktop application to track personal income and expenses.
 Supports multiple currencies, budgets, charts, and cloud sync.
EOF

# Create changelog
cat > "$DEB_ROOT/usr/share/doc/$APP_NAME/changelog" << EOF
$APP_NAME ($VERSION) unstable; urgency=medium

  * See CHANGELOG.md for full details.

 -- $MAINTAINER  $(date -R)
EOF
gzip -9 "$DEB_ROOT/usr/share/doc/$APP_NAME/changelog"

echo "==> Building .deb package..."
mkdir -p "$RELEASE_DIR"
dpkg-deb --build "$DEB_ROOT" "$RELEASE_DIR/$DEB_NAME.deb"

echo "==> Done: $RELEASE_DIR/$DEB_NAME.deb"
