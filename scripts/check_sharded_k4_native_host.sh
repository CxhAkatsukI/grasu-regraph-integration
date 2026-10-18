#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

ROW_LINE_READ=0
BUILD_OPTIONS=()
case "${1:-}" in
  "") ;;
  --row-line-read) ROW_LINE_READ=1; BUILD_OPTIONS=(--row-line-read); shift ;;
  *) echo "Usage: $0 [--row-line-read]" >&2; exit 2 ;;
esac
if [[ $# != 0 ]]; then
  echo "Usage: $0 [--row-line-read]" >&2
  exit 2
fi

OUT_DIR="${OUT_DIR:-${GRI_ROOT}/.tmp_build/sharded_k4_native_host_check_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "${OUT_DIR}"

"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
  --pipeline-mode sharded-k4 --algorithm weighted_sssp \
  --out-dir "${OUT_DIR}/sssp" "${BUILD_OPTIONS[@]}"
"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
  --pipeline-mode sharded-k4 --algorithm connected_components \
  --out-dir "${OUT_DIR}/cc" "${BUILD_OPTIONS[@]}"
"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
  --pipeline-mode sharded-k4 --algorithm full_pagerank \
  --out-dir "${OUT_DIR}/full_pr" "${BUILD_OPTIONS[@]}"
"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
  --pipeline-mode sharded-k4 --algorithm residual_pagerank \
  --out-dir "${OUT_DIR}/residual_pr" "${BUILD_OPTIONS[@]}"

SSSP_HOST="${OUT_DIR}/sssp/sharded_k4_sssp_native_host"
CC_HOST="${OUT_DIR}/cc/sharded_k4_cc_native_host"
FULL_PR_HOST="${OUT_DIR}/full_pr/sharded_k4_full_pagerank_native_host"
RESIDUAL_PR_HOST="${OUT_DIR}/residual_pr/sharded_k4_residual_pagerank_native_host"

g++ -std=c++17 -O2 -Wall -Wextra -Werror \
  "${GRI_ROOT}/tests/resident_full_pagerank_test.cpp" \
  -o "${OUT_DIR}/resident_full_pagerank_test"
"${OUT_DIR}/resident_full_pagerank_test" > "${OUT_DIR}/resident_reference.out"

# Six destination partitions exercise the path beyond the legacy four-partition
# control limit. Cross-partition edges also require a local dst19 encoding.
SSSP_GRAPH="${OUT_DIR}/six_partition_sssp.graph"
cat >"${SSSP_GRAPH}" <<'GRAPH'
327681 3 1
0 65536 1
65536 131072 2
131072 327680 3
327680 1 4 1
GRAPH
SSSP_OUTPUT="${OUT_DIR}/six_partition_sssp.out"
"${SSSP_HOST}" --prepare-only "${SSSP_GRAPH}" \
  "${OUT_DIR}/six_partition_sssp.result" 0 16 | tee "${SSSP_OUTPUT}"
rg -q 'WEIGHTED_PMA_NATIVE_SHARDED_PREP status=PASS .*destination_partitions=6 .*pma_destination_abi=local_dst19 .*k4_frontends=4 shared_regraph_downstream=1 conversion_cost=absent' \
  "${SSSP_OUTPUT}"

CC_GRAPH="${OUT_DIR}/six_partition_cc.graph"
cat >"${CC_GRAPH}" <<'GRAPH'
327681 6 2
0 65536 1
65536 0 1
65536 131072 1
131072 65536 1
131072 327680 1
327680 131072 1
327680 1 1 1
1 327680 1 1
GRAPH
CC_OUTPUT="${OUT_DIR}/six_partition_cc.out"
"${CC_HOST}" --prepare-only "${CC_GRAPH}" \
  "${OUT_DIR}/six_partition_cc.result" 0 16 | tee "${CC_OUTPUT}"
rg -q 'CC_PMA_NATIVE_SHARDED_PREP status=PASS .*destination_partitions=6 .*oracle_converged=1 .*pma_destination_abi=local_dst19 .*k4_frontends=4 shared_regraph_downstream=1 conversion_cost=absent' \
  "${CC_OUTPUT}"

FULL_PR_OUTPUT="${OUT_DIR}/six_partition_full_pr.out"
"${FULL_PR_HOST}" --prepare-only "${SSSP_GRAPH}" \
  "${OUT_DIR}/six_partition_full_pr.result" | tee "${FULL_PR_OUTPUT}"
rg -q 'FULL_PR_PMA_NATIVE_SHARDED_PREP status=PASS .*destination_partitions=6 .*pma_destination_abi=local_dst19 .*k4_frontends=4 shared_regraph_downstream=1 conversion_cost=absent' \
  "${FULL_PR_OUTPUT}"

"${FULL_PR_HOST}" --prepare-only "${SSSP_GRAPH}" \
  "${OUT_DIR}/resident_full_pr.result" --resident-fullpr \
  > "${OUT_DIR}/resident_full_pr.out"
rg -q 'FULL_PR_PMA_NATIVE_SHARDED_INPUT .*convergence=global_l1 epsilon=1e-06 warm_residual_checked=1' \
  "${OUT_DIR}/resident_full_pr.out"
rg -q 'FULL_PR_PMA_NATIVE_SHARDED_PREP status=PASS' \
  "${OUT_DIR}/resident_full_pr.out"
if "${RESIDUAL_PR_HOST}" --prepare-only "${SSSP_GRAPH}" \
    "${OUT_DIR}/wrong_mode.result" --resident-fullpr \
    > "${OUT_DIR}/wrong_mode.out" 2>&1; then
  echo "residual host incorrectly accepted the FullPR-only flag" >&2
  exit 1
fi
if "${FULL_PR_HOST}" --update-only nonexistent.xclbin "${SSSP_GRAPH}" \
    "${OUT_DIR}/wrong_update.result" --resident-fullpr \
    > "${OUT_DIR}/wrong_update.out" 2>&1; then
  echo "update-only incorrectly accepted the FullPR convergence flag" >&2
  exit 1
fi

RESIDUAL_PR_OUTPUT="${OUT_DIR}/six_partition_residual_pr.out"
"${RESIDUAL_PR_HOST}" --prepare-only "${SSSP_GRAPH}" \
  "${OUT_DIR}/six_partition_residual_pr.result" | tee "${RESIDUAL_PR_OUTPUT}"
rg -q 'RESIDUAL_PR_PMA_NATIVE_SHARDED_PREP status=PASS .*destination_partitions=6 .*pma_destination_abi=local_dst19 .*k4_frontends=4 shared_regraph_downstream=1 conversion_cost=absent' \
  "${RESIDUAL_PR_OUTPUT}"

cat >"${OUT_DIR}/check_manifest.env" <<MANIFEST
STATUS=PASS
CLAIM_CLASS=host_preprocessing_and_cpu_oracle_only
HARDWARE_EXECUTED=0
PIPELINE_MODE=sharded-k4
DESTINATION_PARTITIONS=6
PMA_DESTINATION_ABI=local_dst19
K4_FRONTENDS=4
SHARED_REGRAPH_DOWNSTREAM=1
CONVERSION_COST=absent
ROW_LINE_READ=${ROW_LINE_READ}
ALGORITHMS=weighted_sssp,connected_components,full_pagerank,residual_pagerank
RESIDENT_FULLPR_PREPARATION=PASS
RESIDENT_FULLPR_BOARD_EXECUTED=0
MANIFEST

printf 'Sharded K4 native host checks passed:\n  %s\n' "${OUT_DIR}"
