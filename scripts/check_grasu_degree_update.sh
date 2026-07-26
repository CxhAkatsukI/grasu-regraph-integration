#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
OUT_DIR="${GRI_ROOT}/.tmp_build/grasu_degree_update_$(date +%Y%m%d_%H%M%S)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--out-dir PATH]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "${OUT_DIR}"
KERNEL_SRC="${GRASU_ROOT}/GraSU/GraSU_kernels/src"
TEST_BIN="${OUT_DIR}/grasu_degree_update_tb"

g++ -std=c++17 -O2 -w \
  -I"${HLS_INCLUDE}" \
  -I"${HLS_INCLUDE}/etc" \
  -I"${GRI_ROOT}/include" \
  -I"${KERNEL_SRC}" \
  "${GRI_ROOT}/tests/grasu_degree_update_tb.cpp" \
  -o "${TEST_BIN}"

"${TEST_BIN}" | tee "${OUT_DIR}/test.log"

{
  echo "CLAIM_CLASS=functional_protocol_test_not_synthesized_hardware"
  echo "GRI_GIT_HEAD=$(git -C "${GRI_ROOT}" rev-parse HEAD)"
  echo "GRASU_GIT_HEAD=$(git -C "${GRASU_ROOT}" rev-parse HEAD)"
  sha256sum \
    "${GRI_ROOT}/include/grasu_degree_delta.hpp" \
    "${GRI_ROOT}/kernels/grasu_dispatch_degree/grasu_dispatch_degree.cpp" \
    "${GRI_ROOT}/kernels/grasu_degree_update/grasu_degree_update.cpp" \
    "${GRI_ROOT}/tests/grasu_degree_update_tb.cpp" \
    "${KERNEL_SRC}/kernel_config.h" \
    "${TEST_BIN}"
} > "${OUT_DIR}/manifest.txt"

echo "GraSU ordered degree-update protocol test passed: ${OUT_DIR}"
