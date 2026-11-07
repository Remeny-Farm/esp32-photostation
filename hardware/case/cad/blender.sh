#!/usr/bin/env bash
# Run one of the case scripts in headless Blender: blender.sh <script.py> [args...]
# A relative script path is taken from this directory, an absolute one as given.
# BLENDER overrides the binary. The script's own exit code is returned.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
if [[ $# -lt 1 ]]; then
  echo "usage: blender.sh <script.py> [args...]" >&2
  exit 2
fi
script="$1"; shift
[[ "$script" == /* ]] || script="$here/$script"
bin="${BLENDER:-}"
if [[ -z "$bin" ]]; then
  if [[ -x /Applications/Blender.app/Contents/MacOS/Blender ]]; then
    bin=/Applications/Blender.app/Contents/MacOS/Blender
  else
    bin="$(command -v blender || true)"
  fi
fi
if [[ -z "$bin" ]]; then
  echo "blender.sh: Blender not found; install it or set BLENDER=/path/to/blender" >&2
  exit 2
fi
exec "$bin" --background --factory-startup --python-exit-code 1 \
  --python "$script" -- "$@"
