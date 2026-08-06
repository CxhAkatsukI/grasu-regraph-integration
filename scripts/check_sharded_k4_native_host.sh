#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${OUT_DIR:-${GRI_ROOT}/.tmp_build/sharded_k4_native_host_check_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "${OUT_DIR}"

"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
  --pipeline-mode sharded-k4 --algorithm weighted_sssp \
  --out-dir "${OUT_DIR}/sssp"
"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
  --pipeline-mode sharded-k4 --algorithm connected_components \
  --out-dir "${OUT_DIR}/cc"

SSSP_HOST="${OUT_DIR}/sssp/sharded_k4_sssp_native_host"
CC_HOST="${OUT_DIR}/cc/sharded_k4_cc_native_host"

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
ALGORITHMS=weighted_sssp,connected_components
MANIFEST

printf 'Sharded K4 native host checks passed:\n  %s\n' "${OUT_DIR}"
