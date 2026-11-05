#!/usr/bin/env bash
# Run one of the case scripts in headless Blender: blender.sh <script.py> [args...]
# BLENDER overrides the binary. The script's own exit code is returned.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="$1"; shift
bin="${BLENDER:-}"
if [[ -z "$bin" ]]; then
  if [[ -x /Applications/Blender.app/Contents/MacOS/Blender ]]; then
    bin=/Applications/Blender.app/Contents/MacOS/Blender
  else
    bin="$(command -v blender)"
  fi
fi
exec "$bin" --background --factory-startup --python-exit-code 1 \
  --python "$here/$script" -- "$@"
