#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
HLS_INCLUDE_ETC="${HLS_INCLUDE_ETC:-${HLS_INCLUDE}/etc}"
OUT_DIR="${GRI_ROOT}/.tmp_build/regraph_algorithm_policy_check_$(date +%Y%m%d_%H%M%S)"

if [[ "${1:-}" == "--out-dir" ]]; then
  OUT_DIR="$(realpath -m "$2")"
  shift 2
fi
if [[ $# -ne 0 ]]; then
  echo "Usage: $0 [--out-dir PATH]" >&2
  exit 2
fi

mkdir -p "${OUT_DIR}"
SRC="${GRI_ROOT}/kernels/regraph_algorithm_policy/regraph_algorithm_policy.cpp"
TB="${GRI_ROOT}/tests/regraph_algorithm_policy_tb.cpp"
LOG="${OUT_DIR}/test.log"

declare -A POLICY_IDS=(
  [weighted-sssp]=1
  [full-pagerank]=2
  [thresholded-residual-pagerank]=3
)

printf 'algorithm\tpolicy_id\texecutable\n' >"${OUT_DIR}/summary.tsv"
: >"${LOG}"
for algorithm in weighted-sssp full-pagerank thresholded-residual-pagerank; do
  executable="${OUT_DIR}/regraph_algorithm_policy_${algorithm}"
  {
    g++ -std=c++17 -w \
      -DREGRAPH_ALGORITHM_POLICY="${POLICY_IDS[${algorithm}]}" \
      -I"${HLS_INCLUDE}" \
      -I"${HLS_INCLUDE_ETC}" \
      "${TB}" -o "${executable}"
    "${executable}"
  } >>"${LOG}" 2>&1
  printf '%s\t%s\t%s\n' \
    "${algorithm}" "${POLICY_IDS[${algorithm}]}" "${executable}" \
    >>"${OUT_DIR}/summary.tsv"
done

{
  printf 'timestamp=%s\n' "$(date -Is)"
  printf 'claim_class=%s\n' "synthesizable_policy_core_not_full_system_native"
  printf 'lanes=%s\n' 8
  printf 'source=%s\n' "${SRC}"
  printf 'testbench=%s\n' "${TB}"
  printf 'git_head=%s\n' "$(git -C "${GRI_ROOT}" rev-parse HEAD)"
} >"${OUT_DIR}/manifest.env"

(
  cd "${OUT_DIR}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum
) >"${OUT_DIR}/SHA256SUMS"

echo "ReGraph algorithm policy checks passed: ${OUT_DIR}"
