#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${GRI_ROOT}/.tmp_build/residualpr_pma_native_host_check_$(date +%Y%m%d_%H%M%S)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--out-dir PATH]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "${OUT_DIR}"
"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
  --algorithm residual_pagerank \
  --out-dir "${OUT_DIR}"

HOST="${OUT_DIR}/residual_pagerank_pma_native_host"
RESULT="${OUT_DIR}/residual_pagerank.txt"
LOG="${OUT_DIR}/prepare.log"
"${HOST}" --prepare-only \
  "${GRI_ROOT}/workloads/weighted_pma_native_tiny/weighted_pma_native_tiny.graph" \
  "${RESULT}" | tee "${LOG}"

grep -q "RESIDUAL_PR_PMA_NATIVE_PREP status=PASS" "${LOG}"
grep -q "oracle_converged=1" "${LOG}"
grep -q "threshold_semantics=direct_per_vertex" "${LOG}"

echo "Residual PageRank PMA native host checks passed:"
echo "  ${OUT_DIR}"
