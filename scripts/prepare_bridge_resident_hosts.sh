#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="${OUT_ROOT:-/data/tmp/chuxiao/bridge_resident_hosts_20260806}"

for algorithm in weighted_sssp connected_components residual_pagerank; do
  "${SCRIPT_DIR}/build_weighted_pma_native_host.sh" \
    --algorithm "${algorithm}" \
    --out-dir "${OUT_ROOT}/${algorithm}"
done

echo "BRIDGE_RESIDENT_HOSTS_PASS out_root=${OUT_ROOT}"
