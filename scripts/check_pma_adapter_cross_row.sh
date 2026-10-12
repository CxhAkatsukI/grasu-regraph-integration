#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"
if [[ ($# != 2 && $# != 3) || "$1" != "--out-dir" || (${3:-} != "" && ${3:-} != "--continuous-directory" && ${3:-} != "--directory-tile" && ${3:-} != "--packet-pipeline" && ${3:-} != "--bank-stream" && ${3:-} != "--bank-stream-wide") ]]; then
  echo "Usage: $0 --out-dir FRESH_DIRECTORY [--continuous-directory | --directory-tile | --packet-pipeline | --bank-stream | --bank-stream-wide]" >&2
  exit 2
fi
OUT_DIR="$2"
mkdir "${OUT_DIR}"
HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
continuous=0
tile=8
packet=0
bank=0
bank_lines=128
if [[ ${3:-} == "--continuous-directory" ]]; then continuous=1; fi
if [[ ${3:-} == "--directory-tile" ]]; then tile=128; fi
if [[ ${3:-} == "--packet-pipeline" ]]; then tile=1024; packet=1; fi
if [[ ${3:-} == "--bank-stream" ]]; then tile=1024; packet=1; bank=1; fi
if [[ ${3:-} == "--bank-stream-wide" ]]; then tile=1024; packet=1; bank=1; bank_lines=256; fi
printf 'CONTINUOUS_DIRECTORY=%s\n' "${continuous}"
for mode in weighted destination unit; do
  case "${mode}" in
    weighted) defines=(-DGRASU_REGRAPH_WEIGHTED_PMA=1) ;;
    destination) defines=(-DGRASU_REGRAPH_WEIGHTED_PMA=0 -DGRASU_REGRAPH_DESTINATION_ONLY=1) ;;
    unit) defines=(-DGRASU_REGRAPH_WEIGHTED_PMA=0) ;;
  esac
  g++ -std=c++17 -w "${defines[@]}" \
    -DPMA_ADAPTER_TEST_SKIP_EMPTY=1 -DPMA_ADAPTER_TEST_ROW_LINE=1 \
    -DPMA_ADAPTER_TEST_CROSS_ROW=1 \
    -DPMA_ADAPTER_TEST_CONTINUOUS_DIRECTORY="${continuous}" \
    -DPMA_ADAPTER_TEST_DIRECTORY_TILE_ROWS="${tile}" \
    -DPMA_ADAPTER_TEST_PACKET_PIPELINE="${packet}" \
    -DPMA_ADAPTER_TEST_BANK_STREAM="${bank}" \
    -DPMA_ADAPTER_TEST_BANK_FIFO_LINES="${bank_lines}" \
    -I"${HLS_INCLUDE}" -I"${HLS_INCLUDE}/etc" \
    "${GRI_ROOT}/tests/pma_adapter_row_prefetch_tb.cpp" \
    -o "${OUT_DIR}/${mode}_test"
  "${OUT_DIR}/${mode}_test"
done
