#!/usr/bin/env bash
# scripts/generate-icons.sh
#
# Generate PWA icons and iOS splash screens from a source 1024×1024 PNG.
# Requires: ImageMagick (convert command) or sharp-cli (npm).
#
# Usage:
#   bash scripts/generate-icons.sh [source-icon.png]
#
# Default source: assets/icon-source.png

set -euo pipefail

SOURCE="${1:-assets/icon-source.png}"
OUT_ICONS="frontend/public/icons"
OUT_SPLASH="frontend/public/splash"
SPLASH_BG="#1a1a2e"        # App background colour (used for splash screens)
SPLASH_ICON_SIZE=256       # Icon size (px) placed on the splash background

if [[ ! -f "$SOURCE" ]]; then
  echo "ERROR: Source icon not found at '$SOURCE'"
  echo "Place a 1024×1024 PNG at that path and re-run."
  exit 1
fi

command -v convert >/dev/null 2>&1 || {
  echo "ERROR: ImageMagick 'convert' not found. Install it:"
  echo "  macOS:  brew install imagemagick"
  echo "  Ubuntu: sudo apt-get install imagemagick"
  exit 1
}

mkdir -p "$OUT_ICONS" "$OUT_SPLASH"

echo "Generating app icons from $SOURCE..."

# ── Android / PWA icons ────────────────────────────────────────────────────
for SIZE in 72 96 128 144 152 192 384 512; do
  convert "$SOURCE" -resize "${SIZE}x${SIZE}" "${OUT_ICONS}/icon-${SIZE}x${SIZE}.png"
  echo "  ✓ icon-${SIZE}x${SIZE}.png"
done

# ── iOS specific ───────────────────────────────────────────────────────────
for SIZE in 120 167 180; do
  convert "$SOURCE" -resize "${SIZE}x${SIZE}" "${OUT_ICONS}/icon-${SIZE}x${SIZE}.png"
  echo "  ✓ icon-${SIZE}x${SIZE}.png (iOS)"
done

# Apple touch icon
convert "$SOURCE" -resize "180x180" "${OUT_ICONS}/apple-touch-icon.png"
echo "  ✓ apple-touch-icon.png"

# Favicon sizes
for SIZE in 16 32 48; do
  convert "$SOURCE" -resize "${SIZE}x${SIZE}" "${OUT_ICONS}/favicon-${SIZE}x${SIZE}.png"
  echo "  ✓ favicon-${SIZE}x${SIZE}.png"
done

echo ""
echo "Generating iOS splash screens..."

splash() {
  local name="$1" w="$2" h="$3"
  convert \
    -size "${w}x${h}" "xc:${SPLASH_BG}" \
    \( "$SOURCE" -resize "${SPLASH_ICON_SIZE}x${SPLASH_ICON_SIZE}" \) \
    -gravity center -composite \
    "${OUT_SPLASH}/${name}.png"
  echo "  ✓ ${name}.png (${w}x${h})"
}

splash "iphone-se"        640  1136
splash "iphone-8"         750  1334
splash "iphone-8-plus"   1242  2208
splash "iphone-x"        1125  2436
splash "iphone-xr"        828  1792
splash "iphone-11-pro-max" 1242 2688
splash "ipad"            1536  2048
splash "ipad-pro-10-5"   1668  2224
splash "ipad-pro-12-9"   2048  2732

echo ""
echo "Done! Icons → $OUT_ICONS  |  Splash → $OUT_SPLASH"
