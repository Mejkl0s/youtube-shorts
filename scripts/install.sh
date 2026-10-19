#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo 'Install FFmpeg with libx264 and drawtext first.' >&2; exit 1; }
command -v ffprobe >/dev/null
test -f /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf || { echo 'Install DejaVu fonts first.' >&2; exit 1; }
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$PWD/.runtime/cache/pip}"
export npm_config_cache="${npm_config_cache:-$PWD/.runtime/cache/npm}"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
npm run build
# New browser projects use keyless online speech. Local Piper is an explicit alternative.
if [ "${INSTALL_LOCAL_VOICE:-0}" = "1" ]; then
  .venv/bin/python scripts/download_models.py --language en
fi
