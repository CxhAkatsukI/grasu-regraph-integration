#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"
if [[ $# != 2 || "$1" != "--out-dir" ]]; then
  echo "Usage: $0 --out-dir FRESH_DIRECTORY" >&2
  exit 2
fi
OUT_DIR="$2"
mkdir "${OUT_DIR}"
HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
for mode in weighted destination unit; do
  case "${mode}" in
    weighted) defines=(-DGRASU_REGRAPH_WEIGHTED_PMA=1) ;;
    destination) defines=(-DGRASU_REGRAPH_WEIGHTED_PMA=0 -DGRASU_REGRAPH_DESTINATION_ONLY=1) ;;
    unit) defines=(-DGRASU_REGRAPH_WEIGHTED_PMA=0) ;;
  esac
  g++ -std=c++17 -w "${defines[@]}" \
    -DPMA_ADAPTER_TEST_SKIP_EMPTY=1 -DPMA_ADAPTER_TEST_ROW_LINE=1 \
    -DPMA_ADAPTER_TEST_CROSS_ROW=1 \
    -I"${HLS_INCLUDE}" -I"${HLS_INCLUDE}/etc" \
    "${GRI_ROOT}/tests/pma_adapter_row_prefetch_tb.cpp" \
    -o "${OUT_DIR}/${mode}_test"
  "${OUT_DIR}/${mode}_test"
done
