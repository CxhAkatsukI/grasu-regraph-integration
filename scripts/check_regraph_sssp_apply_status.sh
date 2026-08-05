#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
OUT_DIR="${GRI_ROOT}/.tmp_build/regraph_sssp_apply_status_$(date +%Y%m%d_%H%M%S)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--out-dir PATH]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "${OUT_DIR}"
g++ -std=c++17 -O2 -w \
  -DHAVE_EDGE_PROP=1 -DHAVE_UNSIGNED_PROP=1 \
  -DHAVE_APPLY_OUTDEG=0 -DHAVE_VERTEX_PROP=1 \
  -DPARTITION_SIZE=16 -DLITTLE_KERNEL_DST_BUFFER_SIZE=16 \
  -DBIG_KERNEL_DST_BUFFER_SIZE=16 -DSRC_BUFFER_SIZE=16 \
  -DLOG2_SRC_BUFFER_SIZE=4 -DVERTEX_REORDER_ENABLE=1 \
  -DENABLE_COMPRESSED_EDGE_INPUT=0 -DBIG_KERNEL_NUM=0 \
  -DLITTLE_KERNEL_NUM=1 -DREGRAPH_PURE_LITTLE_ONLY \
  -I"${HLS_INCLUDE}" -I"${HLS_INCLUDE}/etc" \
  -I"${REGRAPH_ROOT}/acc_udfs/sssp" \
  -I"${REGRAPH_ROOT}/acc_template" \
  -I"${REGRAPH_ROOT}/acc_template/common" \
  -I"${REGRAPH_ROOT}/acc_template/kernel_apply" \
  "${GRI_ROOT}/tests/regraph_sssp_apply_status_tb.cpp" \
  -o "${OUT_DIR}/regraph_sssp_apply_status_tb"

"${OUT_DIR}/regraph_sssp_apply_status_tb" \
  | tee "${OUT_DIR}/regraph_sssp_apply_status_tb.log"

sha256sum \
  "${GRI_ROOT}/kernels/regraph_sssp_apply_status/kernel_apply.cpp" \
  "${GRI_ROOT}/tests/regraph_sssp_apply_status_tb.cpp" \
  "${OUT_DIR}/regraph_sssp_apply_status_tb" \
  > "${OUT_DIR}/SHA256SUMS"

echo "ReGraph SSSP apply active-count test passed: ${OUT_DIR}"
