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

Run a lightweight C++ syntax check for the PMA-to-ReGraph adapter kernel using
the Vitis HLS C++ headers. This does not synthesize an XO.
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
OBJ="${OUT_DIR}/pma_to_regraph_adapter.o"
LOG="${OUT_DIR}/compile.log"

{
  echo "timestamp=$(date -Is)"
  echo "GRI_ROOT=${GRI_ROOT}"
  echo "HLS_INCLUDE=${HLS_INCLUDE}"
  echo "HLS_INCLUDE_ETC=${HLS_INCLUDE_ETC}"
  echo "SRC=${SRC}"
  echo "OBJ=${OBJ}"
} > "${OUT_DIR}/manifest.env"

g++ -std=c++17 -w \
  -I"${HLS_INCLUDE}" \
  -I"${HLS_INCLUDE_ETC}" \
  -c "${SRC}" \
  -o "${OBJ}" \
  > "${LOG}" 2>&1

{
  sha256sum "${SRC}"
  sha256sum "${OBJ}"
  sha256sum "${LOG}"
} > "${OUT_DIR}/SHA256SUMS"

echo "PMA-to-ReGraph adapter syntax check passed:"
echo "  ${OUT_DIR}"
