#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

LABEL=""
MANIFEST="${GRI_ROOT}/workloads/sssp_benchmark_pure_stage0/manifest.tsv"
PLAN_DIR=""
HOST_OUT=""
HOST_IDENTITY_DIR=""
SPINE_OUT=""
TIMEOUT_SECONDS=600
SPINE_TIMEOUT_SECONDS=300
GRASU_HOST=""
GRASU_XCLBIN=""
REGRAPH_HOST=""
REGRAPH_XCLBIN=""
COMBINED_XCLBIN=""
SPINE_HOST=""
SPINE_XCLBIN=""
XCL_EMULATION_MODE_VALUE=""
VITIS_SETTINGS=""
GRASU_EMCONFIG_PATH=""
REGRAPH_EMCONFIG_PATH=""
SKIP_PLAN=0
SKIP_HOST=0
SKIP_HOST_IDENTITY=0
SKIP_SPINE=0
STATUS_ONLY=0
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Prepare or run the same-input pure_stage0 host and Spine baselines used by
the pure-pipeline comparison. This script does not build xclbins.

Default flow:
  1. export pure_stage0 comparison plan and input_identity.tsv
  2. run GraSU -> host -> ReGraph with device graph export
  3. audit host case.env files against input_identity.tsv
  4. run Spine on the host-exported *.from_grasu.sssp.edges files

Options:
  --label NAME                Result suffix. Default: after_<git short hash>.
  --manifest PATH             pure_stage0 manifest. Default: ${MANIFEST}
  --plan-dir PATH             Plan dir. Default: results/pure_stage0_comparison_plan_<label>
  --host-out PATH             Host baseline dir. Default: results/grasu_regraph_sssp_pure_stage0_<label>
  --host-identity-dir PATH    Host identity audit dir. Default: results/grasu_regraph_sssp_pure_stage0_identity_<label>
  --spine-out PATH            Spine baseline dir. Default: results/spine_edge_file_pure_stage0_<label>
  --timeout SECONDS           Host per-case timeout. Default: ${TIMEOUT_SECONDS}
  --spine-timeout SECONDS     Spine per-case timeout. Default: ${SPINE_TIMEOUT_SECONDS}
  --grasu-host PATH           Passed to run_grasu_regraph_sssp_sweep.sh.
  --grasu-xclbin PATH         Passed to run_grasu_regraph_sssp_sweep.sh.
  --regraph-host PATH         Passed to run_grasu_regraph_sssp_sweep.sh.
  --regraph-xclbin PATH       Passed to run_grasu_regraph_sssp_sweep.sh.
  --combined-xclbin PATH      Use one xclbin for GraSU and ReGraph host baseline.
  --spine-host PATH           Passed to run_spine_edge_file_sweep.sh.
  --spine-xclbin PATH         Passed to run_spine_edge_file_sweep.sh.
  --xcl-emulation-mode MODE   Passed to host baseline, e.g. hw_emu.
  --vitis-settings PATH       Passed to host baseline for hw_emu.
  --grasu-emconfig-path PATH  Passed to host baseline for hw_emu.
  --regraph-emconfig-path PATH
                              Passed to host baseline for hw_emu.
  --skip-plan                 Reuse an existing comparison plan.
  --skip-host                 Do not run host baseline.
  --skip-host-identity        Do not audit host baseline input identity.
  --skip-spine                Do not run Spine baseline.
  --status-only               Print current artifact status and exit.
  --dry-run                   Print commands; do not execute host/Spine runs.
                              Plan export still runs unless --skip-plan is set.
  -h, --help                  Show this help.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

print_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
}

run_cmd() {
  print_cmd "$@"
  if [[ "${DRY_RUN}" == "0" ]]; then
    "$@"
  fi
}

sha_or_missing() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    sha256sum "${path}" | awk '{print $1}'
  else
    printf 'MISSING'
  fi
}

exists_yes_no() {
  if [[ -e "$1" ]]; then
    printf 'yes'
  else
    printf 'no'
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --label) LABEL="$2"; shift 2 ;;
    --manifest) MANIFEST="$(abs_path "$2")"; shift 2 ;;
    --plan-dir) PLAN_DIR="$(abs_path "$2")"; shift 2 ;;
    --host-out) HOST_OUT="$(abs_path "$2")"; shift 2 ;;
    --host-identity-dir) HOST_IDENTITY_DIR="$(abs_path "$2")"; shift 2 ;;
    --spine-out) SPINE_OUT="$(abs_path "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --spine-timeout) SPINE_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --grasu-host) GRASU_HOST="$(abs_path "$2")"; shift 2 ;;
    --grasu-xclbin) GRASU_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --regraph-host) REGRAPH_HOST="$(abs_path "$2")"; shift 2 ;;
    --regraph-xclbin) REGRAPH_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --combined-xclbin) COMBINED_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --spine-host) SPINE_HOST="$(abs_path "$2")"; shift 2 ;;
    --spine-xclbin) SPINE_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --xcl-emulation-mode) XCL_EMULATION_MODE_VALUE="$2"; shift 2 ;;
    --vitis-settings) VITIS_SETTINGS="$(abs_path "$2")"; shift 2 ;;
    --grasu-emconfig-path) GRASU_EMCONFIG_PATH="$(abs_path "$2")"; shift 2 ;;
    --regraph-emconfig-path) REGRAPH_EMCONFIG_PATH="$(abs_path "$2")"; shift 2 ;;
    --skip-plan) SKIP_PLAN=1; shift ;;
    --skip-host) SKIP_HOST=1; shift ;;
    --skip-host-identity) SKIP_HOST_IDENTITY=1; shift ;;
    --skip-spine) SKIP_SPINE=1; shift ;;
    --status-only) STATUS_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

cd "${GRI_ROOT}"

if [[ -z "${LABEL}" ]]; then
  LABEL="after_$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
fi
if [[ -z "${PLAN_DIR}" ]]; then
  PLAN_DIR="${GRI_ROOT}/results/pure_stage0_comparison_plan_${LABEL}"
fi
if [[ -z "${HOST_OUT}" ]]; then
  HOST_OUT="${GRI_ROOT}/results/grasu_regraph_sssp_pure_stage0_${LABEL}"
fi
if [[ -z "${HOST_IDENTITY_DIR}" ]]; then
  HOST_IDENTITY_DIR="${GRI_ROOT}/results/grasu_regraph_sssp_pure_stage0_identity_${LABEL}"
fi
if [[ -z "${SPINE_OUT}" ]]; then
  SPINE_OUT="${GRI_ROOT}/results/spine_edge_file_pure_stage0_${LABEL}"
fi

INPUT_IDENTITY="${PLAN_DIR}/input_identity.tsv"
COMPARISON_PLAN="${PLAN_DIR}/comparison_plan.tsv"
HOST_SUMMARY="${HOST_OUT}/summary.tsv"
HOST_IDENTITY_OUT="${HOST_IDENTITY_DIR}/input_identity_check.tsv"
SPINE_SUMMARY="${SPINE_OUT}/summary.tsv"
RUN_ENV="${PLAN_DIR}/baseline_run.env"

write_status() {
  cat <<STATUS
pure_stage0_baselines_status
label=${LABEL}
plan_dir=${PLAN_DIR}
comparison_plan=$(exists_yes_no "${COMPARISON_PLAN}") sha256=$(sha_or_missing "${COMPARISON_PLAN}")
input_identity=$(exists_yes_no "${INPUT_IDENTITY}") sha256=$(sha_or_missing "${INPUT_IDENTITY}")
host_out=${HOST_OUT}
host_summary=$(exists_yes_no "${HOST_SUMMARY}") sha256=$(sha_or_missing "${HOST_SUMMARY}")
host_identity_out=$(exists_yes_no "${HOST_IDENTITY_OUT}") sha256=$(sha_or_missing "${HOST_IDENTITY_OUT}")
spine_out=${SPINE_OUT}
spine_summary=$(exists_yes_no "${SPINE_SUMMARY}") sha256=$(sha_or_missing "${SPINE_SUMMARY}")
STATUS
}

if [[ "${STATUS_ONLY}" == "1" ]]; then
  write_status
  exit 0
fi

mkdir -p "${PLAN_DIR}" "${HOST_IDENTITY_DIR}"
{
  printf 'label=%s\n' "${LABEL}"
  printf 'manifest=%s\n' "${MANIFEST}"
  printf 'manifest_sha256=%s\n' "$(sha_or_missing "${MANIFEST}")"
  printf 'plan_dir=%s\n' "${PLAN_DIR}"
  printf 'comparison_plan=%s\n' "${COMPARISON_PLAN}"
  printf 'comparison_plan_sha256=%s\n' "$(sha_or_missing "${COMPARISON_PLAN}")"
  printf 'input_identity=%s\n' "${INPUT_IDENTITY}"
  printf 'input_identity_sha256=%s\n' "$(sha_or_missing "${INPUT_IDENTITY}")"
  printf 'host_out=%s\n' "${HOST_OUT}"
  printf 'host_summary=%s\n' "${HOST_SUMMARY}"
  printf 'host_identity_dir=%s\n' "${HOST_IDENTITY_DIR}"
  printf 'host_identity_out=%s\n' "${HOST_IDENTITY_OUT}"
  printf 'spine_out=%s\n' "${SPINE_OUT}"
  printf 'spine_summary=%s\n' "${SPINE_SUMMARY}"
  printf 'timeout_seconds=%s\n' "${TIMEOUT_SECONDS}"
  printf 'spine_timeout_seconds=%s\n' "${SPINE_TIMEOUT_SECONDS}"
  printf 'skip_plan=%s\n' "${SKIP_PLAN}"
  printf 'skip_host=%s\n' "${SKIP_HOST}"
  printf 'skip_host_identity=%s\n' "${SKIP_HOST_IDENTITY}"
  printf 'skip_spine=%s\n' "${SKIP_SPINE}"
  printf 'dry_run=%s\n' "${DRY_RUN}"
  printf 'git_head=%s\n' "$(git -C "${GRI_ROOT}" rev-parse HEAD)"
} > "${RUN_ENV}"

if [[ "${SKIP_PLAN}" == "0" ]]; then
  print_cmd "${SCRIPT_DIR}/export_pure_stage0_comparison_plan.py" \
    --manifest "${MANIFEST}" \
    --label "${LABEL}" \
    --out-dir "${PLAN_DIR}"
  "${SCRIPT_DIR}/export_pure_stage0_comparison_plan.py" \
    --manifest "${MANIFEST}" \
    --label "${LABEL}" \
    --out-dir "${PLAN_DIR}"
fi

if [[ "${SKIP_HOST}" == "0" ]]; then
  host_cmd=(
    "${SCRIPT_DIR}/run_grasu_regraph_sssp_sweep.sh"
    --preset pure_stage0
    --workload-root "${MANIFEST%/manifest.tsv}"
    --out-root "${HOST_OUT}"
    --timeout "${TIMEOUT_SECONDS}"
    --skip-generate
    --device-graph-export
  )
  if [[ -n "${GRASU_HOST}" ]]; then host_cmd+=(--grasu-host "${GRASU_HOST}"); fi
  if [[ -n "${GRASU_XCLBIN}" ]]; then host_cmd+=(--grasu-xclbin "${GRASU_XCLBIN}"); fi
  if [[ -n "${REGRAPH_HOST}" ]]; then host_cmd+=(--regraph-host "${REGRAPH_HOST}"); fi
  if [[ -n "${REGRAPH_XCLBIN}" ]]; then host_cmd+=(--regraph-xclbin "${REGRAPH_XCLBIN}"); fi
  if [[ -n "${COMBINED_XCLBIN}" ]]; then host_cmd+=(--combined-xclbin "${COMBINED_XCLBIN}"); fi
  if [[ -n "${XCL_EMULATION_MODE_VALUE}" ]]; then host_cmd+=(--xcl-emulation-mode "${XCL_EMULATION_MODE_VALUE}"); fi
  if [[ -n "${VITIS_SETTINGS}" ]]; then host_cmd+=(--vitis-settings "${VITIS_SETTINGS}"); fi
  if [[ -n "${GRASU_EMCONFIG_PATH}" ]]; then host_cmd+=(--grasu-emconfig-path "${GRASU_EMCONFIG_PATH}"); fi
  if [[ -n "${REGRAPH_EMCONFIG_PATH}" ]]; then host_cmd+=(--regraph-emconfig-path "${REGRAPH_EMCONFIG_PATH}"); fi
  if [[ "${DRY_RUN}" == "1" ]]; then host_cmd+=(--dry-run); fi
  run_cmd "${host_cmd[@]}"
fi

if [[ "${SKIP_HOST_IDENTITY}" == "0" ]]; then
  run_cmd "${SCRIPT_DIR}/check_pure_stage0_input_identity.py" \
    --input-identity "${INPUT_IDENTITY}" \
    --run-root "${HOST_OUT}" \
    --summary "${HOST_SUMMARY}" \
    --out-file "${HOST_IDENTITY_OUT}"
fi

if [[ "${SKIP_SPINE}" == "0" ]]; then
  spine_cmd=(
    "${SCRIPT_DIR}/run_spine_edge_file_sweep.sh"
    --chain-root "${HOST_OUT}"
    --out-root "${SPINE_OUT}"
    --timeout "${SPINE_TIMEOUT_SECONDS}"
  )
  if [[ -n "${SPINE_HOST}" ]]; then spine_cmd+=(--spine-host "${SPINE_HOST}"); fi
  if [[ -n "${SPINE_XCLBIN}" ]]; then spine_cmd+=(--spine-xclbin "${SPINE_XCLBIN}"); fi
  if [[ "${DRY_RUN}" == "1" ]]; then spine_cmd+=(--dry-run); fi
  run_cmd "${spine_cmd[@]}"
fi

{
  printf 'comparison_plan_sha256=%s\n' "$(sha_or_missing "${COMPARISON_PLAN}")"
  printf 'input_identity_sha256=%s\n' "$(sha_or_missing "${INPUT_IDENTITY}")"
  printf 'host_summary_sha256=%s\n' "$(sha_or_missing "${HOST_SUMMARY}")"
  printf 'host_identity_out_sha256=%s\n' "$(sha_or_missing "${HOST_IDENTITY_OUT}")"
  printf 'spine_summary_sha256=%s\n' "$(sha_or_missing "${SPINE_SUMMARY}")"
} >> "${RUN_ENV}"

write_status
echo "DONE run_env=${RUN_ENV}"
