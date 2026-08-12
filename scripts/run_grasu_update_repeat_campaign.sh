#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRI_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

device_index=${DEVICE_INDEX:-0}
repeats=${GRASU_UPDATE_REPEATS:-5}
datasets=${DATASETS:-au,su,wk,r19}
out_root=${OUT_ROOT:-/data/tmp/chuxiao/grasu_update_repeat_campaign}
host_root=${HOST_ROOT:-/data/tmp/chuxiao/sharded_k4_hosts_update_repeat_v1}
workload_root=${WORKLOAD_ROOT:-/data/tmp/chuxiao/fullgraph_fpga_workloads_20260806}
sssp_xclbin=${SSSP_XCLBIN:-/data/tmp/chuxiao/grasu_regraph_sharded_k4_sssp_hw_b8d2ba3_20260806/build/grasu_regraph_weighted_pma_native_sharded_k4.hw.xclbin}
cc_xclbin=${CC_XCLBIN:-/data/tmp/chuxiao/grasu_regraph_sharded_k4_cc_hw_d886f42_20260806/build/grasu_regraph_connected_components_pma_native_sharded_k4.hw.xclbin}
respr_xclbin=${RESPR_XCLBIN:-/data/tmp/chuxiao/grasu_regraph_sharded_k4_respr_hw_bfe2024_route_aggressive_slr2_20260807/build/grasu_regraph_residual_pagerank.hw.xclbin}

usage() {
  cat <<USAGE
Usage: $0 [--device-index N] [--datasets CSV] [--out-root DIR] [--repeats N]

Run correctness-gated same-process G+R update-repeat diagnostics for weighted
SSSP, connected components, and residual PageRank. Defaults may be overridden
with HOST_ROOT, WORKLOAD_ROOT, SSSP_XCLBIN, CC_XCLBIN, and RESPR_XCLBIN.
USAGE
}

while (( $# > 0 )); do
  case "$1" in
    --device-index) device_index=$2; shift 2 ;;
    --datasets) datasets=$2; shift 2 ;;
    --out-root) out_root=$2; shift 2 ;;
    --repeats) repeats=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for value in "${device_index}" "${repeats}"; do
  [[ "${value}" =~ ^[0-9]+$ ]] || { echo "numeric argument required" >&2; exit 2; }
done
(( repeats >= 2 && repeats <= 32 )) || {
  echo "--repeats must be in [2, 32]" >&2
  exit 2
}

IFS=',' read -r -a dataset_array <<<"${datasets}"
algorithms=(weighted_sssp connected_components residual_pagerank)
mkdir -p "${out_root}"

for dataset in "${dataset_array[@]}"; do
  for algorithm in "${algorithms[@]}"; do
    case "${algorithm}" in
      weighted_sssp)
        host="${host_root}/sssp/sharded_k4_sssp_native_host"
        xclbin="${sssp_xclbin}"
        ;;
      connected_components)
        host="${host_root}/cc/sharded_k4_cc_native_host"
        xclbin="${cc_xclbin}"
        ;;
      residual_pagerank)
        host="${host_root}/residual_pr/sharded_k4_residual_pagerank_native_host"
        xclbin="${respr_xclbin}"
        ;;
    esac
    graph="${workload_root}/${dataset}_${algorithm}_insert_u8.graph"
    out_dir="${out_root}/${dataset}_${algorithm}"
    echo "UPDATE_REPEAT_CASE dataset=${dataset} algorithm=${algorithm} device=${device_index} repeats=${repeats}"
    GRASU_UPDATE_REPEATS="${repeats}" \
      bash "${SCRIPT_DIR}/run_pma_native_hw.sh" \
        --algorithm "${algorithm}" \
        --host "${host}" \
        --xclbin "${xclbin}" \
        --graph "${graph}" \
        --out-dir "${out_dir}" \
        --device-index "${device_index}" \
        --source 0 \
        --max-supersteps 256 \
        --update-only \
        --timeout 600
  done
done

echo "GRASU_UPDATE_REPEAT_CAMPAIGN status=PASS out=${out_root}"
