#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $# != 2 || $1 != --out-dir ]]; then
  echo "usage: $0 --out-dir FRESH_DIRECTORY" >&2
  exit 2
fi
mkdir "$2"
out=$(cd "$2" && pwd)
include=${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}
for mode in weighted destination unit; do
  case "$mode" in
    weighted) flags=(-DGRASU_REGRAPH_WEIGHTED_PMA=1) ;;
    destination) flags=(-DGRASU_REGRAPH_DESTINATION_ONLY=1) ;;
    unit) flags=() ;;
  esac
  g++ -std=c++17 -O1 -w -pthread "${flags[@]}" \
    -I"$include" -I"$include/etc" "$root/tests/pma_prefetch_compact_tb.cpp" \
    -o "$out/$mode" > "$out/$mode.build.log" 2>&1
  timeout 180 "$out/$mode" > "$out/$mode.run.log" 2>&1
  tail -n 2 "$out/$mode.run.log"
done
