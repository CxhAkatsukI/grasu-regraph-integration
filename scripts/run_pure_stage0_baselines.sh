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
COMPARISON_OUT=""
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
SPINE_PARTITIONED_SPLIT_VALUE="${SPINE_PARTITIONED_SPLIT_VALUE:-1}"
SETUP_RUNTIME_ENV=1
SKIP_PLAN=0
SKIP_HOST=0
SKIP_HOST_IDENTITY=0
SKIP_SPINE=0
SKIP_COMPARISON=0
STATUS_ONLY=0
DRY_RUN=0

DEFAULT_GRASU_HOST="${GRI_ROOT}/repos/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c_export"
DEFAULT_REGRAPH_HOST="/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp"
DEFAULT_COMBINED_XCLBIN="${GRI_ROOT}/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin"
DEFAULT_SPINE_HOST="${GRI_ROOT}/.tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge"
DEFAULT_SPINE_XCLBIN="/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin"

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
  --comparison-out PATH       Stage0 comparison dir. Default: results/pure_stage0_comparison_<label>
  --timeout SECONDS           Host per-case timeout. Default: ${TIMEOUT_SECONDS}
  --spine-timeout SECONDS     Spine per-case timeout. Default: ${SPINE_TIMEOUT_SECONDS}
  --grasu-host PATH           Passed to run_grasu_regraph_sssp_sweep.sh.
  --grasu-xclbin PATH         Passed to run_grasu_regraph_sssp_sweep.sh.
  --regraph-host PATH         Passed to run_grasu_regraph_sssp_sweep.sh.
  --regraph-xclbin PATH       Passed to run_grasu_regraph_sssp_sweep.sh.
  --combined-xclbin PATH      Use one xclbin for GraSU and ReGraph host baseline.
  --spine-host PATH           Passed to run_spine_edge_file_sweep.sh.
  --spine-xclbin PATH         Passed to run_spine_edge_file_sweep.sh.
  --spine-partitioned-split 0|1
                              Set SPINE_PARTITIONED_SPLIT_VALUE. Default: ${SPINE_PARTITIONED_SPLIT_VALUE}
  --xcl-emulation-mode MODE   Passed to host baseline, e.g. hw_emu.
  --vitis-settings PATH       Passed to host baseline for hw_emu.
                              Also sourced by this wrapper for real-hw runs.
  --grasu-emconfig-path PATH  Passed to host baseline for hw_emu.
  --regraph-emconfig-path PATH
                              Passed to host baseline for hw_emu.
  --no-runtime-env            Do not source Vitis settings or set XRT env.
  --skip-plan                 Reuse an existing comparison plan.
  --skip-host                 Do not run host baseline.
  --skip-host-identity        Do not audit host baseline input identity.
  --skip-spine                Do not run Spine baseline.
  --skip-comparison           Do not generate the stage0 comparison table.
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
    --comparison-out) COMPARISON_OUT="$(abs_path "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --spine-timeout) SPINE_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --grasu-host) GRASU_HOST="$(abs_path "$2")"; shift 2 ;;
    --grasu-xclbin) GRASU_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --regraph-host) REGRAPH_HOST="$(abs_path "$2")"; shift 2 ;;
    --regraph-xclbin) REGRAPH_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --combined-xclbin) COMBINED_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --spine-host) SPINE_HOST="$(abs_path "$2")"; shift 2 ;;
    --spine-xclbin) SPINE_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --spine-partitioned-split) SPINE_PARTITIONED_SPLIT_VALUE="$2"; shift 2 ;;
    --xcl-emulation-mode) XCL_EMULATION_MODE_VALUE="$2"; shift 2 ;;
    --vitis-settings) VITIS_SETTINGS="$(abs_path "$2")"; shift 2 ;;
    --grasu-emconfig-path) GRASU_EMCONFIG_PATH="$(abs_path "$2")"; shift 2 ;;
    --regraph-emconfig-path) REGRAPH_EMCONFIG_PATH="$(abs_path "$2")"; shift 2 ;;
    --no-runtime-env) SETUP_RUNTIME_ENV=0; shift ;;
    --skip-plan) SKIP_PLAN=1; shift ;;
    --skip-host) SKIP_HOST=1; shift ;;
    --skip-host-identity) SKIP_HOST_IDENTITY=1; shift ;;
    --skip-spine) SKIP_SPINE=1; shift ;;
    --skip-comparison) SKIP_COMPARISON=1; shift ;;
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
if [[ -z "${COMPARISON_OUT}" ]]; then
  COMPARISON_OUT="${GRI_ROOT}/results/pure_stage0_comparison_${LABEL}"
fi
if [[ -z "${GRASU_HOST}" ]]; then
  GRASU_HOST="${DEFAULT_GRASU_HOST}"
fi
if [[ -z "${REGRAPH_HOST}" ]]; then
  REGRAPH_HOST="${DEFAULT_REGRAPH_HOST}"
fi
if [[ -z "${COMBINED_XCLBIN}" && -z "${GRASU_XCLBIN}" && -z "${REGRAPH_XCLBIN}" ]]; then
  COMBINED_XCLBIN="${DEFAULT_COMBINED_XCLBIN}"
fi
if [[ -z "${SPINE_HOST}" ]]; then
  SPINE_HOST="${DEFAULT_SPINE_HOST}"
fi
if [[ -z "${SPINE_XCLBIN}" ]]; then
  SPINE_XCLBIN="${DEFAULT_SPINE_XCLBIN}"
fi
if [[ -z "${VITIS_SETTINGS}" ]]; then
  VITIS_SETTINGS="/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
fi

INPUT_IDENTITY="${PLAN_DIR}/input_identity.tsv"
COMPARISON_PLAN="${PLAN_DIR}/comparison_plan.tsv"
HOST_SUMMARY="${HOST_OUT}/summary.tsv"
HOST_IDENTITY_OUT="${HOST_IDENTITY_DIR}/input_identity_check.tsv"
SPINE_SUMMARY="${SPINE_OUT}/summary.tsv"
COMPARISON_TSV="${COMPARISON_OUT}/comparison.tsv"
COMPARISON_MD="${COMPARISON_OUT}/comparison.md"
RUN_ENV="${PLAN_DIR}/baseline_run.env"

write_status() {
  cat <<STATUS
pure_stage0_baselines_status
label=${LABEL}
plan_dir=${PLAN_DIR}
comparison_plan=$(exists_yes_no "${COMPARISON_PLAN}") sha256=$(sha_or_missing "${COMPARISON_PLAN}")
input_identity=$(exists_yes_no "${INPUT_IDENTITY}") sha256=$(sha_or_missing "${INPUT_IDENTITY}")
host_out=${HOST_OUT}
grasu_host=${GRASU_HOST} sha256=$(sha_or_missing "${GRASU_HOST}")
combined_xclbin=${COMBINED_XCLBIN} sha256=$(sha_or_missing "${COMBINED_XCLBIN}")
regraph_host=${REGRAPH_HOST} sha256=$(sha_or_missing "${REGRAPH_HOST}")
host_summary=$(exists_yes_no "${HOST_SUMMARY}") sha256=$(sha_or_missing "${HOST_SUMMARY}")
host_identity_out=$(exists_yes_no "${HOST_IDENTITY_OUT}") sha256=$(sha_or_missing "${HOST_IDENTITY_OUT}")
spine_out=${SPINE_OUT}
spine_host=${SPINE_HOST} sha256=$(sha_or_missing "${SPINE_HOST}")
spine_xclbin=${SPINE_XCLBIN} sha256=$(sha_or_missing "${SPINE_XCLBIN}")
spine_partitioned_split=${SPINE_PARTITIONED_SPLIT_VALUE}
setup_runtime_env=${SETUP_RUNTIME_ENV}
vitis_settings=${VITIS_SETTINGS} sha256=$(sha_or_missing "${VITIS_SETTINGS}")
spine_summary=$(exists_yes_no "${SPINE_SUMMARY}") sha256=$(sha_or_missing "${SPINE_SUMMARY}")
comparison_out=${COMPARISON_OUT}
comparison_tsv=$(exists_yes_no "${COMPARISON_TSV}") sha256=$(sha_or_missing "${COMPARISON_TSV}")
comparison_md=$(exists_yes_no "${COMPARISON_MD}") sha256=$(sha_or_missing "${COMPARISON_MD}")
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
  printf 'comparison_out=%s\n' "${COMPARISON_OUT}"
  printf 'comparison_tsv=%s\n' "${COMPARISON_TSV}"
  printf 'comparison_md=%s\n' "${COMPARISON_MD}"
  printf 'grasu_host=%s\n' "${GRASU_HOST}"
  printf 'grasu_host_sha256=%s\n' "$(sha_or_missing "${GRASU_HOST}")"
  printf 'grasu_xclbin=%s\n' "${GRASU_XCLBIN}"
  printf 'grasu_xclbin_sha256=%s\n' "$(sha_or_missing "${GRASU_XCLBIN}")"
  printf 'regraph_host=%s\n' "${REGRAPH_HOST}"
  printf 'regraph_host_sha256=%s\n' "$(sha_or_missing "${REGRAPH_HOST}")"
  printf 'regraph_xclbin=%s\n' "${REGRAPH_XCLBIN}"
  printf 'regraph_xclbin_sha256=%s\n' "$(sha_or_missing "${REGRAPH_XCLBIN}")"
  printf 'combined_xclbin=%s\n' "${COMBINED_XCLBIN}"
  printf 'combined_xclbin_sha256=%s\n' "$(sha_or_missing "${COMBINED_XCLBIN}")"
  printf 'spine_host=%s\n' "${SPINE_HOST}"
  printf 'spine_host_sha256=%s\n' "$(sha_or_missing "${SPINE_HOST}")"
  printf 'spine_xclbin=%s\n' "${SPINE_XCLBIN}"
  printf 'spine_xclbin_sha256=%s\n' "$(sha_or_missing "${SPINE_XCLBIN}")"
  printf 'spine_partitioned_split=%s\n' "${SPINE_PARTITIONED_SPLIT_VALUE}"
  printf 'setup_runtime_env=%s\n' "${SETUP_RUNTIME_ENV}"
  printf 'vitis_settings=%s\n' "${VITIS_SETTINGS}"
  printf 'vitis_settings_sha256=%s\n' "$(sha_or_missing "${VITIS_SETTINGS}")"
  printf 'timeout_seconds=%s\n' "${TIMEOUT_SECONDS}"
  printf 'spine_timeout_seconds=%s\n' "${SPINE_TIMEOUT_SECONDS}"
  printf 'skip_plan=%s\n' "${SKIP_PLAN}"
  printf 'skip_host=%s\n' "${SKIP_HOST}"
  printf 'skip_host_identity=%s\n' "${SKIP_HOST_IDENTITY}"
  printf 'skip_spine=%s\n' "${SKIP_SPINE}"
  printf 'skip_comparison=%s\n' "${SKIP_COMPARISON}"
  printf 'dry_run=%s\n' "${DRY_RUN}"
  printf 'git_head=%s\n' "$(git -C "${GRI_ROOT}" rev-parse HEAD)"
} > "${RUN_ENV}"

if [[ "${SETUP_RUNTIME_ENV}" == "1" && "${DRY_RUN}" == "0" ]]; then
  if [[ ! -f "${VITIS_SETTINGS}" ]]; then
    echo "Missing Vitis settings: ${VITIS_SETTINGS}" >&2
    exit 1
  fi
  set +u
  # shellcheck disable=SC1090
  source "${VITIS_SETTINGS}"
  set -u
  export XILINX_XRT="${XILINX_XRT:-/opt/xilinx/xrt}"
  export LD_LIBRARY_PATH="${XILINX_XRT}/lib:${LD_LIBRARY_PATH:-}"
  export PATH="${XILINX_XRT}/bin:${PATH}"
fi

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
  spine_cmd+=(--no-source-xrt)
  if [[ "${DRY_RUN}" == "1" ]]; then spine_cmd+=(--dry-run); fi
  run_cmd env "SPINE_PARTITIONED_SPLIT_VALUE=${SPINE_PARTITIONED_SPLIT_VALUE}" "${spine_cmd[@]}"
fi

if [[ "${SKIP_COMPARISON}" == "0" ]]; then
  if [[ "${DRY_RUN}" == "0" && ! -f "${HOST_SUMMARY}" ]]; then
    echo "Skipping stage0 comparison: missing host summary ${HOST_SUMMARY}" >&2
  else
    comparison_cmd=(
      "${SCRIPT_DIR}/summarize_pure_stage0_comparison.py"
      --label "${LABEL}"
      --manifest "${MANIFEST}"
      --input-identity "${INPUT_IDENTITY}"
      --host-summary "${HOST_SUMMARY}"
      --host-identity "${HOST_IDENTITY_OUT}"
      --out-dir "${COMPARISON_OUT}"
    )
    if [[ "${DRY_RUN}" == "1" || -f "${SPINE_SUMMARY}" ]]; then
      comparison_cmd+=(--spine-summary "${SPINE_SUMMARY}")
    fi
    run_cmd "${comparison_cmd[@]}"
  fi
fi

{
  printf 'comparison_plan_sha256=%s\n' "$(sha_or_missing "${COMPARISON_PLAN}")"
  printf 'input_identity_sha256=%s\n' "$(sha_or_missing "${INPUT_IDENTITY}")"
  printf 'host_summary_sha256=%s\n' "$(sha_or_missing "${HOST_SUMMARY}")"
  printf 'host_identity_out_sha256=%s\n' "$(sha_or_missing "${HOST_IDENTITY_OUT}")"
  printf 'spine_summary_sha256=%s\n' "$(sha_or_missing "${SPINE_SUMMARY}")"
  printf 'comparison_tsv_sha256=%s\n' "$(sha_or_missing "${COMPARISON_TSV}")"
  printf 'comparison_md_sha256=%s\n' "$(sha_or_missing "${COMPARISON_MD}")"
} >> "${RUN_ENV}"

write_status
echo "DONE run_env=${RUN_ENV}"
