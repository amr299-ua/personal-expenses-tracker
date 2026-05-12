#!/usr/bin/env bash
# Build a .rpm package for Personal Expenses Tracker.
# Requires: PyInstaller, rpmbuild
set -euo pipefail

APP_NAME="expenses-tracker"
VERSION="1.0.0"
RELEASE="1"
ARCH="x86_64"
MAINTAINER="Personal Expenses Tracker Team"
DESCRIPTION="Personal Expenses Tracker - Desktop application to track income and expenses"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"
RELEASE_DIR="$PROJECT_DIR/release"
RPM_ROOT="$PROJECT_DIR/build/rpm"
RPMBUILD_DIR="$RPM_ROOT/rpmbuild"
RPM_NAME="${APP_NAME}-${VERSION}-${RELEASE}.${ARCH}"

echo "==> Building PyInstaller binary..."
cd "$PROJECT_DIR"
python -m PyInstaller expenses-tracker.spec --clean --noconfirm

echo "==> Preparing RPM directory structure..."
rm -rf "$RPM_ROOT"
mkdir -p "$RPMBUILD_DIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
mkdir -p "$RPMBUILD_DIR/BUILDROOT"

BUILDROOT="$RPMBUILD_DIR/BUILDROOT/${APP_NAME}-${VERSION}-${RELEASE}.${ARCH}"
mkdir -p "$BUILDROOT/usr/bin"
mkdir -p "$BUILDROOT/usr/share/applications"
mkdir -p "$BUILDROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILDROOT/usr/share/doc/$APP_NAME"

# Copy binary
cp "$DIST_DIR/$APP_NAME/$APP_NAME" "$BUILDROOT/usr/bin/"

# Copy desktop file
cp "$PROJECT_DIR/resources/$APP_NAME.desktop" "$BUILDROOT/usr/share/applications/"

# Create spec file
cat > "$RPMBUILD_DIR/SPECS/$APP_NAME.spec" << EOF
Name:           $APP_NAME
Version:        $VERSION
Release:        $RELEASE
Summary:        Personal Expenses Tracker
License:        MIT
URL:            https://github.com/user/personal-expenses-tracker
Source:         %{name}-%{version}.tar.gz

Requires:       python3-tkinter

%description
A desktop application to track personal income and expenses.
Supports multiple currencies, budgets, charts, and cloud sync.

%install
cp -r %{_builddir}/* %{buildroot}/

%files
/usr/bin/$APP_NAME
/usr/share/applications/$APP_NAME.desktop
/usr/share/doc/$APP_NAME/copyright

%changelog
* $(date "+%a %b %d %Y") $MAINTAINER - $VERSION-$RELEASE
- See CHANGELOG.md for full details
EOF

# Create copyright
mkdir -p "$RPMBUILD_DIR/BUILD/usr/share/doc/$APP_NAME"
cat > "$RPMBUILD_DIR/BUILD/usr/share/doc/$APP_NAME/copyright" << EOF
Copyright: 2026 Personal Expenses Tracker Team
License: MIT
EOF

echo "==> Building .rpm package..."
mkdir -p "$RELEASE_DIR"
(cd "$RPMBUILD_DIR" && rpmbuild -bb SPECS/$APP_NAME.spec \
    --define "_topdir $(pwd)" \
    --define "_buildrootdir $(pwd)/BUILDROOT" \
    --define "_builddir $(pwd)/BUILD" \
    --define "_rpmdir $RELEASE_DIR" \
    --define "_srcrpmdir $RELEASE_DIR"
)

echo "==> Done: $RELEASE_DIR/$ARCH/$RPM_NAME.rpm"
