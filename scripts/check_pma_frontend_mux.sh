#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
HLS_INCLUDE_ETC="${HLS_INCLUDE_ETC:-${HLS_INCLUDE}/etc}"
OUT_DIR="${GRI_ROOT}/.tmp_build/pma_frontend_mux_$(date +%Y%m%d_%H%M%S)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--out-dir PATH]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
mkdir -p "${OUT_DIR}"

SRC="${GRI_ROOT}/kernels/pma_frontend_mux/pma_frontend_mux.cpp"
TB="${GRI_ROOT}/tests/pma_frontend_mux_tb.cpp"
EXE="${OUT_DIR}/pma_frontend_mux_test"
LOG="${OUT_DIR}/test.log"

if ! g++ -std=c++17 -w -I"${HLS_INCLUDE}" -I"${HLS_INCLUDE_ETC}" \
  "${TB}" -o "${EXE}" >"${LOG}" 2>&1; then
  cat "${LOG}" >&2
  exit 1
fi
if ! "${EXE}" >>"${LOG}" 2>&1; then
  cat "${LOG}" >&2
  exit 1
fi

{
  echo "timestamp=$(date -Is)"
  echo "SRC=${SRC}"
  echo "TB=${TB}"
  echo "EXE=${EXE}"
} >"${OUT_DIR}/manifest.env"
sha256sum "${SRC}" "${TB}" "${EXE}" "${LOG}" >"${OUT_DIR}/SHA256SUMS"

echo "PMA frontend mux test passed:"
echo "  ${OUT_DIR}"
