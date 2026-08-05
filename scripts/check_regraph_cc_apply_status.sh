#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${1:-${GRI_ROOT}/.tmp_build/regraph_cc_apply_status}"
HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
mkdir -p "${OUT_DIR}"

g++ -std=c++17 -O2 -w \
  -DHAVE_EDGE_PROP=0 -DHAVE_UNSIGNED_PROP=1 -DHAVE_APPLY_OUTDEG=0 \
  -DHAVE_VERTEX_PROP=1 -DPARTITION_SIZE=16 \
  -DLITTLE_KERNEL_DST_BUFFER_SIZE=16 -DBIG_KERNEL_DST_BUFFER_SIZE=16 \
  -DSRC_BUFFER_SIZE=16 -DLOG2_SRC_BUFFER_SIZE=4 \
  -DVERTEX_REORDER_ENABLE=1 -DENABLE_COMPRESSED_EDGE_INPUT=0 \
  -DBIG_KERNEL_NUM=0 -DLITTLE_KERNEL_NUM=1 -DREGRAPH_PURE_LITTLE_ONLY \
  -I"${GRI_ROOT}/include/regraph_cc" \
  -I"${GRI_ROOT}/repos/ReGraph" \
  -I"${GRI_ROOT}/repos/ReGraph/acc_template" \
  -I"${GRI_ROOT}/repos/ReGraph/acc_template/common" \
  -I"${GRI_ROOT}/repos/ReGraph/acc_template/kernel_apply" \
  -I"${GRI_ROOT}/repos/ReGraph/acc_udfs" \
  -I"${HLS_INCLUDE}" -I"${HLS_INCLUDE}/etc" \
  "${GRI_ROOT}/tests/regraph_cc_apply_status_tb.cpp" \
  -o "${OUT_DIR}/regraph_cc_apply_status_tb"

"${OUT_DIR}/regraph_cc_apply_status_tb"
g++ -std=c++17 -O2 -w \
  -I"${GRI_ROOT}/include/regraph_cc" \
  -I"${HLS_INCLUDE}" -I"${HLS_INCLUDE}/etc" \
  "${GRI_ROOT}/tests/regraph_cc_policy_tb.cpp" \
  -o "${OUT_DIR}/regraph_cc_policy_tb"
"${OUT_DIR}/regraph_cc_policy_tb"
printf 'ReGraph CC min-label apply test passed: %s\n' "${OUT_DIR}"
