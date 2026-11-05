#!/usr/bin/env bash
# Host tests. Usage: run.sh [name]   (name "ident" runs test/ident_test.cpp only)
set -euo pipefail
cd "$(dirname "$0")/.."

out=build/test
mkdir -p "$out"

if [ $# -gt 1 ]; then
  echo "usage: run.sh [name]" >&2
  exit 2
fi

if [ $# -eq 1 ]; then
  tests=("test/$1_test.cpp")
  [ -f "${tests[0]}" ] || { echo "no such test: ${tests[0]}" >&2; exit 2; }
else
  shopt -s nullglob
  tests=(test/*_test.cpp)
  [ ${#tests[@]} -gt 0 ] || { echo "no tests found" >&2; exit 2; }
fi

shopt -s nullglob
core=(src/core/*.cpp)

status=0
for t in "${tests[@]}"; do
  name=$(basename "$t" .cpp)
  echo "== $name"
  if ! c++ -std=c++17 -Wall -Wextra -Werror -I src -I test "$t" ${core[@]+"${core[@]}"} -o "$out/$name"; then
    echo "COMPILE FAILED: $name" >&2
    status=1
    continue
  fi
  "$out/$name" || status=1
done
exit $status
