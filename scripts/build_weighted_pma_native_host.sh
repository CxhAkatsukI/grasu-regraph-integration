#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${OUT_DIR:-${GRI_ROOT}/.tmp_build/weighted_pma_native_host}"
OUT_BIN="${OUT_BIN:-}"
VITIS_HLS="${VITIS_HLS:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1}"
ALGORITHM="weighted_sssp"
PIPELINE_MODE="weighted-axis"

usage() {
  cat <<USAGE
Usage: $0 [options]

Build the conversion-free weighted PMA native pipeline host.

Options:
  --out-dir PATH    Output directory. Default: ${OUT_DIR}
  --out-bin PATH    Output binary. Default: <out-dir>/weighted_pma_native_host
  --algorithm NAME  weighted_sssp, connected_components, full_pagerank, or
                    residual_pagerank.
  --pipeline-mode MODE
                    weighted-axis or sharded-k4.
  -h, --help        Show this help.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$(abs_path "$2")"; shift 2 ;;
    --out-bin) OUT_BIN="$(abs_path "$2")"; shift 2 ;;
    --algorithm) ALGORITHM="$2"; shift 2 ;;
    --pipeline-mode) PIPELINE_MODE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${ALGORITHM}" in
  weighted_sssp) DEFAULT_BIN=weighted_pma_native_host; ALGORITHM_DEFINE=() ;;
  connected_components)
    DEFAULT_BIN=connected_components_pma_native_host
    ALGORITHM_DEFINE=(-DGRASU_REGRAPH_CONNECTED_COMPONENTS=1)
    ;;
  full_pagerank)
    DEFAULT_BIN=full_pagerank_pma_native_host
    ALGORITHM_DEFINE=(-DGRASU_REGRAPH_FULL_PAGERANK=1)
    ;;
  residual_pagerank)
    DEFAULT_BIN=residual_pagerank_pma_native_host
    ALGORITHM_DEFINE=(-DGRASU_REGRAPH_RESIDUAL_PAGERANK=1)
    ;;
  *) echo "Invalid --algorithm: ${ALGORITHM}" >&2; exit 2 ;;
esac

case "${PIPELINE_MODE}" in
  weighted-axis)
    HOST_SOURCE="${GRI_ROOT}/tools/weighted_pma_native_host.cpp"
    HANDOFF=weighted_pma_to_axis_stream
    ;;
  sharded-k4)
    case "${ALGORITHM}" in
      weighted_sssp) DEFAULT_BIN=sharded_k4_sssp_native_host ;;
      connected_components) DEFAULT_BIN=sharded_k4_cc_native_host ;;
      full_pagerank)
        DEFAULT_BIN=sharded_k4_full_pagerank_native_host
        ;;
      residual_pagerank)
        DEFAULT_BIN=sharded_k4_residual_pagerank_native_host
        ;;
    esac
    case "${ALGORITHM}" in
      full_pagerank|residual_pagerank)
        HOST_SOURCE="${GRI_ROOT}/tools/sharded_k4_pagerank_native_host.cpp"
        ;;
      *) HOST_SOURCE="${GRI_ROOT}/tools/sharded_k4_native_host.cpp" ;;
    esac
    HANDOFF=four_sharded_pma_source_gather_frontends_to_one_regraph_downstream
    ;;
  *) echo "Invalid --pipeline-mode: ${PIPELINE_MODE}" >&2; exit 2 ;;
esac

mkdir -p "${OUT_DIR}"
if [[ -z "${OUT_BIN}" ]]; then
  OUT_BIN="${OUT_DIR}/${DEFAULT_BIN}"
fi

g++ -std=c++17 -O2 -Wall -Wextra -Werror \
  -DGRASU_MAX_CACHE_SEGMENT=131072 \
  "${ALGORITHM_DEFINE[@]}" \
  -I"${XILINX_XRT}/include" \
  -I"${VITIS_HLS}/include" \
  -I"${VITIS_HLS}/include/etc" \
  -I"${GRI_ROOT}/include" \
  "${HOST_SOURCE}" \
  -L"${XILINX_XRT}/lib" \
  -Wl,-rpath,"${XILINX_XRT}/lib" \
  -lxilinxopencl -lpthread \
  -o "${OUT_BIN}"

sha256sum "${HOST_SOURCE}" \
          "${GRI_ROOT}/tools/weighted_pma_native_host.cpp" \
          "${GRI_ROOT}/include/weighted_pma_graph.hpp" \
          "${GRI_ROOT}/include/weighted_pma_runtime_plan.hpp" \
          "${GRI_ROOT}/include/weighted_pma_update_reference.hpp" \
          "${OUT_BIN}" | tee "${OUT_DIR}/weighted_pma_native_host.sha256"
cat >"${OUT_DIR}/manifest.txt" <<MANIFEST
CLAIM_CLASS=candidate_hls_host_not_yet_run
ALGORITHM=${ALGORITHM}
PIPELINE_MODE=${PIPELINE_MODE}
HANDOFF=${HANDOFF}
CONVERSION_COST=absent
MAX_CACHE_SEGMENT=131072
HOST=${OUT_BIN}
MANIFEST
printf 'built %s\n' "${OUT_BIN}"
