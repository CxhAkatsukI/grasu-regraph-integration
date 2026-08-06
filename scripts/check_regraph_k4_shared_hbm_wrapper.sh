#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
HLS_INCLUDE_ETC="${HLS_INCLUDE_ETC:-${HLS_INCLUDE}/etc}"
OUT_DIR="${GRI_ROOT}/.tmp_build/regraph_k4_shared_hbm_wrapper_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${OUT_DIR}"

g++ -std=c++17 -O2 -w -c \
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
  -DBIG_KERNEL_NUM=0 \
  -DLITTLE_KERNEL_NUM=4 \
  -DREGRAPH_PURE_LITTLE_ONLY \
  -I"${HLS_INCLUDE}" \
  -I"${HLS_INCLUDE_ETC}" \
  -I"${REGRAPH_ROOT}/acc_udfs/sssp" \
  -I"${REGRAPH_ROOT}" \
  -I"${REGRAPH_ROOT}/acc_template" \
  -I"${REGRAPH_ROOT}/acc_template/common" \
  -I"${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper" \
  "${GRI_ROOT}/kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp" \
  -o "${OUT_DIR}/kernel_hbm_wrapper.o"

printf 'regraph_k4_shared_hbm_wrapper compile PASS\n'
