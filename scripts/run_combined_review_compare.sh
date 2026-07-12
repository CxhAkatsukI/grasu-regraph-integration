#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw"
BUILD_ROOT="${GRI_ROOT}/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335"
SESSION="combined_hw_coldinit_250mhz_20260712_112335"
CHAIN_OUT="${GRI_ROOT}/results/grasu_regraph_sssp_review_combined_hw_$(date +%Y%m%d_%H%M%S)"
COMPARE_OUT="${GRI_ROOT}/results/spine_vs_grasu_regraph_review_combined_hw_$(date +%Y%m%d_%H%M%S)"
SPINE_SUMMARY="${GRI_ROOT}/results/spine_builtin_review_hw_20260712_121941/summary.tsv"
CHAIN_SUMMARY=""
REGRAPH_HOST="/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-600}"
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Run the combined GraSU+ReGraph review sweep, then join its summary with the
recorded Spine review baseline. This produces the first scenario-level
Spine-vs-chain comparison table.

Options:
  --target hw|hw_emu          Combined xclbin target. Default: ${TARGET}
  --build-root PATH           Combined build root. Default: ${BUILD_ROOT}
  --session NAME              Optional tmux session for missing-xclbin monitor.
  --chain-out PATH            GraSU+ReGraph review output root.
  --chain-summary PATH        Reuse an existing chain summary instead of running.
  --compare-out PATH          Comparison output root.
  --spine-summary PATH        Spine summary TSV. Default: ${SPINE_SUMMARY}
  --regraph-host PATH         ReGraph SSSP host. Default: ${REGRAPH_HOST}
  --timeout SECONDS           Per-chain-case timeout. Default: ${TIMEOUT_SECONDS}
  --dry-run                   Print commands without executing hardware.
  -h, --help                  Show this help.
USAGE
}

abs_under_root() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${GRI_ROOT}" "$1" ;;
  esac
}

run_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [[ "${DRY_RUN}" == "0" ]]; then
    "$@"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --session) SESSION="$2"; shift 2 ;;
    --chain-out) CHAIN_OUT="$(abs_under_root "$2")"; shift 2 ;;
    --chain-summary) CHAIN_SUMMARY="$(abs_under_root "$2")"; shift 2 ;;
    --compare-out) COMPARE_OUT="$(abs_under_root "$2")"; shift 2 ;;
    --spine-summary) SPINE_SUMMARY="$(abs_under_root "$2")"; shift 2 ;;
    --regraph-host) REGRAPH_HOST="$(abs_under_root "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  hw|hw_emu) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

BUILD_ROOT="$(abs_under_root "${BUILD_ROOT}")"
XCLBIN="${BUILD_ROOT}/build/grasu_regraph_combined.${TARGET}.xclbin"

if [[ -z "${CHAIN_SUMMARY}" && ! -e "${XCLBIN}" && "${DRY_RUN}" == "0" ]]; then
  echo "Combined xclbin is not ready yet: ${XCLBIN}" >&2
  if [[ -n "${SESSION}" ]]; then
    "${SCRIPT_DIR}/monitor_combined_hw_build.sh" \
      --build-root "${BUILD_ROOT}" \
      --session "${SESSION}" \
      --idle-warn-minutes 10 | sed -n '1,180p' >&2 || true
  fi
  exit 1
fi

if [[ ! -e "${SPINE_SUMMARY}" && "${DRY_RUN}" == "0" ]]; then
  echo "Missing Spine summary: ${SPINE_SUMMARY}" >&2
  exit 1
fi

if [[ -z "${CHAIN_SUMMARY}" ]]; then
  chain_cmd=(
    "${SCRIPT_DIR}/run_grasu_regraph_sssp_sweep.sh"
    --preset review
    --timeout "${TIMEOUT_SECONDS}"
    --regraph-host "${REGRAPH_HOST}"
    --combined-xclbin "${XCLBIN}"
    --out-root "${CHAIN_OUT}"
  )
  if [[ "${TARGET}" == "hw_emu" ]]; then
    chain_cmd+=(--xcl-emulation-mode hw_emu)
  fi
  run_cmd "${chain_cmd[@]}"
  CHAIN_SUMMARY="${CHAIN_OUT}/summary.tsv"
fi

run_cmd "${SCRIPT_DIR}/compare_spine_chain_summaries.py" \
  --chain-summary "${CHAIN_SUMMARY}" \
  --spine-summary "${SPINE_SUMMARY}" \
  --pair small_chain_v64=carry_l1:small_high_diameter \
  --pair small_star_v4096_u1024=star_4096:small_hot_source \
  --pair small_spread_v4096_u1024=fanout_4096_s64:small_spread_fanout \
  --pair small_hotdst_v4096_u1024=duplicate_heavy_4096:small_hot_destination \
  --pair medium_star_v65536_u8192=star_65536:medium_hot_source \
  --pair medium_spread_v65536_u16384=fanout_65536_s256:medium_spread_fanout \
  --out-dir "${COMPARE_OUT}"

echo "DONE chain_summary=${CHAIN_SUMMARY}"
echo "DONE spine_summary=${SPINE_SUMMARY}"
echo "DONE compare_out=${COMPARE_OUT}"
