#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${OUT_DIR:-${GRI_ROOT}/.tmp_build/cc_pma_native_host_check_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "${OUT_DIR}"

"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
  --algorithm connected_components --out-dir "${OUT_DIR}"
HOST="${OUT_DIR}/connected_components_pma_native_host"

GRAPH="${OUT_DIR}/reciprocal.graph"
printf '6 8 0\n0 1 1\n1 0 1\n1 2 1\n2 1 1\n3 4 1\n4 3 1\n4 5 1\n5 4 1\n' >"${GRAPH}"
OUTPUT="${OUT_DIR}/prepare.out"
"${HOST}" --prepare-only "${GRAPH}" "${OUT_DIR}/result.txt" 0 16 | tee "${OUTPUT}"
rg -q 'CC_PMA_NATIVE_PREP status=PASS .*oracle_converged=1 .*components=2 .*conversion_cost=absent' \
  "${OUTPUT}"

BAD_GRAPH="${OUT_DIR}/nonreciprocal.graph"
printf '4 1 0\n0 1 1\n' >"${BAD_GRAPH}"
if "${HOST}" --prepare-only "${BAD_GRAPH}" "${OUT_DIR}/bad.txt" \
     >"${OUT_DIR}/bad.out" 2>&1; then
  echo "Expected non-reciprocal CC input to fail" >&2
  exit 1
fi
rg -q 'connected_components requires reciprocal directed edges' "${OUT_DIR}/bad.out"

printf 'Connected-components PMA native host checks passed:\n  %s\n' "${OUT_DIR}"
