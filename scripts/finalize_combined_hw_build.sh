#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw"
BUILD_ROOT="${GRI_ROOT}/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335"
SESSION="combined_hw_coldinit_250mhz_20260712_112335"
PRESET="smoke"
EVIDENCE_OUT=""
SMOKE_OUT=""
GRASU_HOST=""
REGRAPH_HOST=""
SKIP_EVIDENCE=0
SKIP_SMOKE=0
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Finalize an existing combined GraSU + ReGraph hardware build once the xclbin
has been produced. The script does not build hardware. It checks the combined
xclbin, collects resource evidence, and runs the GraSU->ReGraph SSSP smoke
sweep with both hosts loading the same combined xclbin.

Options:
  --target hw|hw_emu         Build target. Default: ${TARGET}
  --build-root PATH          Combined build root. Default: ${BUILD_ROOT}
  --session NAME             Optional tmux session name for monitor output.
  --preset smoke|review|capacity
                             Sweep preset. Default: ${PRESET}
  --evidence-out PATH        Evidence output root.
  --smoke-out PATH           Smoke/sweep output root.
  --grasu-host PATH          GraSU host. Default is derived from --target.
  --regraph-host PATH        ReGraph SSSP host. Default is derived from --target.
  --skip-evidence            Do not collect resource evidence.
  --skip-smoke               Do not run GraSU->ReGraph smoke/sweep.
  --dry-run                  Print commands without running them.
  -h, --help                 Show this help.

Typical use after the current real-hw build finishes:

  $0 \\
    --target hw \\
    --build-root ${GRI_ROOT}/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335 \\
    --session combined_hw_coldinit_250mhz_20260712_112335 \\
    --preset smoke
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
    --preset) PRESET="$2"; shift 2 ;;
    --evidence-out) EVIDENCE_OUT="$(abs_under_root "$2")"; shift 2 ;;
    --smoke-out) SMOKE_OUT="$(abs_under_root "$2")"; shift 2 ;;
    --grasu-host) GRASU_HOST="$(abs_under_root "$2")"; shift 2 ;;
    --regraph-host) REGRAPH_HOST="$(abs_under_root "$2")"; shift 2 ;;
    --skip-evidence) SKIP_EVIDENCE=1; shift ;;
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  hw|hw_emu) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

case "${PRESET}" in
  smoke|review|capacity) ;;
  *) echo "Invalid --preset: ${PRESET}" >&2; exit 2 ;;
esac

BUILD_ROOT="$(abs_under_root "${BUILD_ROOT}")"
XCLBIN="${BUILD_ROOT}/build/grasu_regraph_combined.${TARGET}.xclbin"

if [[ -z "${GRASU_HOST}" ]]; then
  if [[ "${TARGET}" == "hw_emu" ]]; then
    GRASU_HOST="${GRASU_ROOT}/.tmp_build/u55c_hbm_hwemu/GraSU_host_u55c"
  else
    GRASU_HOST="${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/GraSU_host_u55c"
  fi
fi
if [[ -z "${REGRAPH_HOST}" ]]; then
  if [[ "${TARGET}" == "hw_emu" ]]; then
    REGRAPH_HOST="/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/host_graph_fpga_sssp"
  else
    REGRAPH_HOST="/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp"
  fi
fi

if [[ -z "${EVIDENCE_OUT}" ]]; then
  EVIDENCE_OUT="${GRI_ROOT}/results/resource_evidence_$(date +%Y%m%d_%H%M%S)_combined_${TARGET}_final"
fi
if [[ -z "${SMOKE_OUT}" ]]; then
  SMOKE_OUT="${GRI_ROOT}/results/grasu_regraph_sssp_${PRESET}_combined_${TARGET}_$(date +%Y%m%d_%H%M%S)"
fi

if [[ ! -e "${XCLBIN}" ]]; then
  echo "Combined xclbin is not ready yet: ${XCLBIN}" >&2
  if [[ -n "${SESSION}" && -x "${SCRIPT_DIR}/monitor_combined_hw_build.sh" ]]; then
    echo
    "${SCRIPT_DIR}/monitor_combined_hw_build.sh" \
      --build-root "${BUILD_ROOT}" \
      --session "${SESSION}" \
      --idle-warn-minutes 10 | sed -n '1,180p' >&2 || true
  fi
  exit 1
fi

echo "combined_xclbin=${XCLBIN}"
run_cmd sha256sum "${XCLBIN}"

if [[ "${SKIP_EVIDENCE}" == "0" ]]; then
  run_cmd "${SCRIPT_DIR}/collect_combined_hw_evidence.sh" \
    --target "${TARGET}" \
    --combined-build-root "${BUILD_ROOT}" \
    --combined-xclbin "${XCLBIN}" \
    --grasu-host "${GRASU_HOST}" \
    --regraph-host "${REGRAPH_HOST}" \
    --out-root "${EVIDENCE_OUT}"
fi

if [[ "${SKIP_SMOKE}" == "0" ]]; then
  sweep_cmd=(
    "${SCRIPT_DIR}/run_grasu_regraph_sssp_sweep.sh"
    --preset "${PRESET}" \
    --grasu-host "${GRASU_HOST}" \
    --regraph-host "${REGRAPH_HOST}" \
    --combined-xclbin "${XCLBIN}" \
    --out-root "${SMOKE_OUT}"
  )
  if [[ "${TARGET}" == "hw_emu" ]]; then
    sweep_cmd+=(--xcl-emulation-mode hw_emu)
  fi
  run_cmd "${sweep_cmd[@]}"
fi

echo "DONE combined_xclbin=${XCLBIN}"
if [[ "${SKIP_EVIDENCE}" == "0" ]]; then
  echo "DONE evidence_out=${EVIDENCE_OUT}"
fi
if [[ "${SKIP_SMOKE}" == "0" ]]; then
  echo "DONE smoke_out=${SMOKE_OUT}"
fi
