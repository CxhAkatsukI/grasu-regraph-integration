#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
HLS_INCLUDE_ETC="${HLS_INCLUDE_ETC:-${HLS_INCLUDE}/etc}"
OUT_DIR=""

usage() {
  cat <<USAGE
Usage: $0 [--out-dir PATH]

Compile and execute legacy-unit, weighted-PMA, and destination-only C++ tests for the
PMA-to-ReGraph adapter using the Vitis HLS headers. This does not synthesize an
XO.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -d "${HLS_INCLUDE}" ]]; then
  echo "Missing Vitis HLS include directory: ${HLS_INCLUDE}" >&2
  exit 1
fi
if [[ ! -d "${HLS_INCLUDE_ETC}" ]]; then
  echo "Missing Vitis HLS include/etc directory: ${HLS_INCLUDE_ETC}" >&2
  exit 1
fi

if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/.tmp_build/pma_to_regraph_adapter_check_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "${OUT_DIR}"

SRC="${GRI_ROOT}/kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
TB="${GRI_ROOT}/tests/pma_to_regraph_adapter_tb.cpp"
LEGACY_EXE="${OUT_DIR}/pma_to_regraph_adapter_legacy_test"
WEIGHTED_EXE="${OUT_DIR}/pma_to_regraph_adapter_weighted_test"
DESTINATION_EXE="${OUT_DIR}/pma_to_regraph_adapter_destination_test"
SHARDED_WEIGHTED_EXE="${OUT_DIR}/pma_to_regraph_adapter_sharded_weighted_test"
SHARDED_DESTINATION_EXE="${OUT_DIR}/pma_to_regraph_adapter_sharded_destination_test"
LOG="${OUT_DIR}/test.log"

{
  echo "timestamp=$(date -Is)"
  echo "GRI_ROOT=${GRI_ROOT}"
  echo "HLS_INCLUDE=${HLS_INCLUDE}"
  echo "HLS_INCLUDE_ETC=${HLS_INCLUDE_ETC}"
  echo "SRC=${SRC}"
  echo "TB=${TB}"
  echo "LEGACY_EXE=${LEGACY_EXE}"
  echo "WEIGHTED_EXE=${WEIGHTED_EXE}"
  echo "DESTINATION_EXE=${DESTINATION_EXE}"
  echo "SHARDED_WEIGHTED_EXE=${SHARDED_WEIGHTED_EXE}"
  echo "SHARDED_DESTINATION_EXE=${SHARDED_DESTINATION_EXE}"
} > "${OUT_DIR}/manifest.env"

if ! {
  g++ -std=c++17 -w \
    -I"${HLS_INCLUDE}" \
    -I"${HLS_INCLUDE_ETC}" \
    "${TB}" \
    -o "${LEGACY_EXE}"
  "${LEGACY_EXE}"

  g++ -std=c++17 -w \
    -DGRASU_REGRAPH_WEIGHTED_PMA=1 \
    -I"${HLS_INCLUDE}" \
    -I"${HLS_INCLUDE_ETC}" \
    "${TB}" \
    -o "${WEIGHTED_EXE}"
  "${WEIGHTED_EXE}"

  g++ -std=c++17 -w \
    -DGRASU_REGRAPH_DESTINATION_ONLY=1 \
    -I"${HLS_INCLUDE}" \
    -I"${HLS_INCLUDE_ETC}" \
    "${TB}" \
    -o "${DESTINATION_EXE}"
  "${DESTINATION_EXE}"

  g++ -std=c++17 -w \
    -DGRASU_REGRAPH_WEIGHTED_PMA=1 \
    -DGRASU_REGRAPH_SHARDED_PMA=1 \
    -I"${HLS_INCLUDE}" \
    -I"${HLS_INCLUDE_ETC}" \
    "${TB}" \
    -o "${SHARDED_WEIGHTED_EXE}"
  "${SHARDED_WEIGHTED_EXE}"

  g++ -std=c++17 -w \
    -DGRASU_REGRAPH_DESTINATION_ONLY=1 \
    -DGRASU_REGRAPH_SHARDED_PMA=1 \
    -I"${HLS_INCLUDE}" \
    -I"${HLS_INCLUDE_ETC}" \
    "${TB}" \
    -o "${SHARDED_DESTINATION_EXE}"
  "${SHARDED_DESTINATION_EXE}"
} > "${LOG}" 2>&1; then
  cat "${LOG}" >&2
  exit 1
fi

{
  sha256sum "${SRC}"
  sha256sum "${TB}"
  sha256sum "${LEGACY_EXE}"
  sha256sum "${WEIGHTED_EXE}"
  sha256sum "${DESTINATION_EXE}"
  sha256sum "${SHARDED_WEIGHTED_EXE}"
  sha256sum "${SHARDED_DESTINATION_EXE}"
  sha256sum "${LOG}"
} > "${OUT_DIR}/SHA256SUMS"

echo "PMA-to-ReGraph adapter legacy, weighted, and destination-only tests passed:"
echo "  ${OUT_DIR}"
