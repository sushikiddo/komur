#!/usr/bin/env bash
# Build a clean macOS drag-and-drop .dmg from dist/Kömür.app (with /Applications symlink).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_PATH="${1:-$ROOT_DIR/dist/Kömür.app}"
VERSION="${2:-$(python3 -c 'import sys; sys.path.insert(0, "'"$ROOT_DIR"'"); from version import APP_VERSION; print(APP_VERSION)')}"
OUT_DIR="${3:-$ROOT_DIR/release-artifacts}"
DMG_NAME="Komur-${VERSION}-macOS-arm64.dmg"
DMG_PATH="${OUT_DIR}/${DMG_NAME}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found: $APP_PATH" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

ditto "$APP_PATH" "$STAGE/Kömür.app"
ln -s /Applications "$STAGE/Applications"

rm -f "$DMG_PATH"
hdiutil create \
  -volname "Kömür ${VERSION}" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

(cd "$OUT_DIR" && shasum -a 256 "$DMG_NAME" > "${DMG_NAME}.sha256")
echo "Created: $DMG_PATH"
