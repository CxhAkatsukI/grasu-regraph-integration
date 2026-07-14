#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
OUT_DIR=""

usage() {
  cat <<USAGE
Usage: $0 [--out-dir PATH]

Run a lightweight C++ syntax check for the integration-owned ReGraph little-GS
stream-input wrapper. This does not synthesize an XO.
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
if [[ ! -d "${REGRAPH_ROOT}/acc_template" ]]; then
  echo "Missing ReGraph acc_template directory: ${REGRAPH_ROOT}/acc_template" >&2
  exit 1
fi

if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/.tmp_build/regraph_stream_little_gs_check_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "${OUT_DIR}"

SRC="${GRI_ROOT}/kernels/regraph_stream_little_gs/little_gs_stream.cpp"
OBJ="${OUT_DIR}/little_gs_stream.o"
LOG="${OUT_DIR}/compile.log"

{
  echo "timestamp=$(date -Is)"
  echo "GRI_ROOT=${GRI_ROOT}"
  echo "REGRAPH_ROOT=${REGRAPH_ROOT}"
  echo "HLS_INCLUDE=${HLS_INCLUDE}"
  echo "SRC=${SRC}"
  echo "OBJ=${OBJ}"
} > "${OUT_DIR}/manifest.env"

g++ -std=c++17 -w \
  -DHAVE_EDGE_PROP=1 \
  -DHAVE_UNSIGNED_PROP=1 \
  -DHAVE_APPLY_OUTDEG=0 \
  -DHAVE_VERTEX_PROP=1 \
  -DPARTITION_SIZE=65536 \
  -DLITTLE_KERNEL_DST_BUFFER_SIZE=65536 \
  -DBIG_KERNEL_DST_BUFFER_SIZE=524288 \
  -DSRC_BUFFER_SIZE=4096 \
  -DLOG2_SRC_BUFFER_SIZE=12 \
  -DVERTEX_REORDER_ENABLE=1 \
  -DENABLE_COMPRESSED_EDGE_INPUT=0 \
  -DBIG_KERNEL_NUM=1 \
  -DLITTLE_KERNEL_NUM=1 \
  -I"${HLS_INCLUDE}" \
  -I"${REGRAPH_ROOT}/acc_udfs/sssp" \
  -I"${REGRAPH_ROOT}" \
  -I"${REGRAPH_ROOT}/acc_template" \
  -I"${REGRAPH_ROOT}/acc_template/common" \
  -I"${REGRAPH_ROOT}/acc_udfs" \
  -I"${REGRAPH_ROOT}/acc_template/kernel_little_gs" \
  -c "${SRC}" \
  -o "${OBJ}" \
  > "${LOG}" 2>&1

{
  sha256sum "${SRC}"
  sha256sum "${OBJ}"
  sha256sum "${LOG}"
} > "${OUT_DIR}/SHA256SUMS"

echo "ReGraph stream little-GS syntax check passed:"
echo "  ${OUT_DIR}"
