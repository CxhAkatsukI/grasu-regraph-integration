#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${GRI_ROOT}/.tmp_build/regraph_frontend_mux_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${OUT_DIR}"

g++ -std=c++17 -O2 -w \
  -I"/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include" \
  -I"/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include/etc" \
  "${GRI_ROOT}/tests/regraph_frontend_mux_tb.cpp" \
  -o "${OUT_DIR}/regraph_frontend_mux_test"

"${OUT_DIR}/regraph_frontend_mux_test"
printf 'regraph_frontend_mux PASS\n'
