#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
OUT_DIR="${GRI_ROOT}/.tmp_build/regraph_pagerank_apply_$(date +%Y%m%d_%H%M%S)"

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

compile_and_run() {
  local name="$1"
  local source="$2"
  g++ -std=c++17 -O2 -w \
    -I"${HLS_INCLUDE}" \
    -I"${HLS_INCLUDE}/etc" \
    -I"${GRI_ROOT}/include" \
    "${source}" \
    -o "${OUT_DIR}/${name}"
  "${OUT_DIR}/${name}" | tee "${OUT_DIR}/${name}.log"
}

compile_and_run full_pagerank_apply \
  "${GRI_ROOT}/tests/regraph_full_pagerank_apply_tb.cpp"
compile_and_run residual_pagerank_apply \
  "${GRI_ROOT}/tests/regraph_residual_pagerank_apply_tb.cpp"
compile_and_run full_pagerank_source_prepare \
  "${GRI_ROOT}/tests/regraph_full_pagerank_source_prepare_tb.cpp"
compile_and_run residual_pagerank_source_prepare \
  "${GRI_ROOT}/tests/regraph_residual_pagerank_source_prepare_tb.cpp"
compile_and_run pagerank_gather_udf \
  "${GRI_ROOT}/tests/regraph_pagerank_gather_udf_tb.cpp"

{
  echo "CLAIM_CLASS=functional_policy_path_not_synthesized_hardware"
  echo "GRI_GIT_HEAD=$(git -C "${GRI_ROOT}" rev-parse HEAD)"
  sha256sum \
    "${GRI_ROOT}/include/regraph_pagerank_apply.hpp" \
    "${GRI_ROOT}/include/regraph_pagerank/l2.h" \
    "${GRI_ROOT}/kernels/regraph_pagerank_apply/regraph_pagerank_apply.cpp" \
    "${GRI_ROOT}/kernels/regraph_pagerank_source_prepare/regraph_pagerank_source_prepare.cpp" \
    "${GRI_ROOT}/tests/regraph_full_pagerank_apply_tb.cpp" \
    "${GRI_ROOT}/tests/regraph_residual_pagerank_apply_tb.cpp" \
    "${GRI_ROOT}/tests/regraph_full_pagerank_source_prepare_tb.cpp" \
    "${GRI_ROOT}/tests/regraph_residual_pagerank_source_prepare_tb.cpp" \
    "${GRI_ROOT}/tests/regraph_pagerank_gather_udf_tb.cpp" \
    "${OUT_DIR}/full_pagerank_apply" \
    "${OUT_DIR}/residual_pagerank_apply" \
    "${OUT_DIR}/full_pagerank_source_prepare" \
    "${OUT_DIR}/residual_pagerank_source_prepare" \
    "${OUT_DIR}/pagerank_gather_udf"
} > "${OUT_DIR}/manifest.txt"

echo "ReGraph Full/residual PageRank policy-path tests passed: ${OUT_DIR}"
