#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${OUT_DIR:-${GRI_ROOT}/.tmp_build/fullpr_pma_native_host_check_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "${OUT_DIR}"

"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
  --algorithm full_pagerank --out-dir "${OUT_DIR}"
HOST="${OUT_DIR}/full_pagerank_pma_native_host"
OUTPUT="${OUT_DIR}/prepare.out"
"${HOST}" --prepare-only \
  "${GRI_ROOT}/workloads/weighted_pma_native_tiny/weighted_pma_native_tiny.graph" \
  "${OUT_DIR}/result.txt" | tee "${OUTPUT}"
rg -q 'FULL_PR_PMA_NATIVE_PREP status=PASS .*physical_updates=8 rounds=3 rank_sum=1\.0000001 conversion_cost=absent' \
  "${OUTPUT}"

printf 'Full PageRank PMA native host checks passed:\n  %s\n' "${OUT_DIR}"
