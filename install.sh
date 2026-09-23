#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"

mode=".[laya]"
case "${1:-}" in
  --no-ai) mode="." ;;
  "") ;;
  *) printf 'Usage: ./install.sh [--no-ai]\n' >&2; exit 2 ;;
esac

if command -v uv >/dev/null 2>&1; then
  uv venv --python 3.12 .venv
  uv pip install --python .venv/bin/python "$mode"
else
  python_bin=""
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c \
      'import sys; assert (3, 11) <= sys.version_info[:2] < (3, 14)' 2>/dev/null; then
      python_bin="$candidate"
      break
    fi
  done
  if [ -z "$python_bin" ]; then
    printf 'Install Python 3.11–3.13 or uv, then rerun this installer.\n' >&2
    exit 1
  fi
  "$python_bin" -m venv .venv
  .venv/bin/python -m pip install "$mode"
fi
printf '\nInstalled. Run ./laya-top\n'
printf 'Optional model download: ./laya-top model download\n'
