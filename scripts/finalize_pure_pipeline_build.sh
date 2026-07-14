#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw_emu"
BUILD_ROOT=""
HOST="${GRI_ROOT}/.tmp_build/pure_pipeline_host_stage0/pure_pipeline_host"
XCLBIN=""
LABEL=""
SMOKE_OUT=""
COMPARE_OUT=""
HOST_SUMMARY="${GRI_ROOT}/results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv"
SPINE_SUMMARY="${GRI_ROOT}/results/spine_edge_file_smoke_hw_stage2_split_xclbin/summary.tsv"
TIMEOUT_SECONDS=""
VITIS_SETTINGS="/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
PLATFORM_XPFM="/opt/xilinx/platforms/xilinx_u55c_gen3x16_xdma_3_202210_1/xilinx_u55c_gen3x16_xdma_3_202210_1.xpfm"
EMCONFIG_PATH=""
BUILD_HOST=0
SKIP_SMOKE=0
SKIP_COMPARE=0
STATUS_ONLY=0
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Finalize a pure-pipeline xclbin: collect artifact evidence, optionally run the
smoke correctness suite, and optionally generate the same-input comparison
against the current host/zero-cost and Spine baselines.

Options:
  --target sw_emu|hw_emu|hw   Target mode. Default: ${TARGET}
  --build-root PATH           Build root. Default: .tmp_build/pure_pipeline_<target>_stage0
  --host PATH                 pure_pipeline_host binary. Default: ${HOST}
  --xclbin PATH               Pure-pipeline xclbin. Default inferred from target/build-root.
  --label NAME                Result/evidence suffix. Default: current git short hash.
  --smoke-out PATH            Smoke output dir. Default: results/pure_pipeline_<target>_smoke_<label>
  --compare-out PATH          Comparison dir. Default: results/pure_pipeline_<target>_compare_<label>
  --host-summary PATH         Host baseline summary. Default: ${HOST_SUMMARY}
  --spine-summary PATH        Spine summary. Default: ${SPINE_SUMMARY}
  --timeout SECONDS           Per-case smoke timeout. Default: 1800 for hw_emu, 600 otherwise.
  --vitis-settings PATH       Vitis settings64.sh. Default: ${VITIS_SETTINGS}
  --platform-xpfm PATH        Platform path for emconfigutil. Default: ${PLATFORM_XPFM}
  --emconfig-path PATH        EMCONFIG_PATH for sw_emu/hw_emu. Default inferred by smoke runner.
  --build-host                Rebuild pure_pipeline_host before smoke.
  --skip-smoke                Only collect artifact evidence.
  --skip-compare              Do not generate same-input comparison.
  --status-only               Collect evidence even if xclbin is missing; run nothing.
  --dry-run                   Print commands that would run; do not execute smoke/compare.
  -h, --help                  Show this help.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

sha_or_missing() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    sha256sum "${path}" | awk '{print $1}'
  else
    printf 'MISSING'
  fi
}

size_or_missing() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    stat -c '%s' "${path}"
  else
    printf 'MISSING'
  fi
}

git_value() {
  local root="$1"
  local field="$2"
  if ! git -C "${root}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'not_git'
    return
  fi
  case "${field}" in
    head) git -C "${root}" rev-parse HEAD ;;
    branch) git -C "${root}" branch --show-current ;;
    tracked_dirty)
      if [[ -n "$(git -C "${root}" status --short --untracked-files=no)" ]]; then
        printf 'dirty'
      else
        printf 'clean'
      fi
      ;;
    *) printf 'unknown' ;;
  esac
}

write_finalize_env() {
  local path="$1"
  {
    printf 'target=%s\n' "${TARGET}"
    printf 'build_root=%s\n' "${BUILD_ROOT}"
    printf 'label=%s\n' "${LABEL}"
    printf 'host=%s\n' "${HOST}"
    printf 'xclbin=%s\n' "${XCLBIN}"
    printf 'smoke_out=%s\n' "${SMOKE_OUT}"
    printf 'compare_out=%s\n' "${COMPARE_OUT}"
    printf 'host_summary=%s\n' "${HOST_SUMMARY}"
    printf 'spine_summary=%s\n' "${SPINE_SUMMARY}"
    printf 'timeout_seconds=%s\n' "${TIMEOUT_SECONDS}"
    printf 'vitis_settings=%s\n' "${VITIS_SETTINGS}"
    printf 'platform_xpfm=%s\n' "${PLATFORM_XPFM}"
    printf 'emconfig_path=%s\n' "${EMCONFIG_PATH}"
    printf 'build_host=%s\n' "${BUILD_HOST}"
    printf 'skip_smoke=%s\n' "${SKIP_SMOKE}"
    printf 'skip_compare=%s\n' "${SKIP_COMPARE}"
    printf 'status_only=%s\n' "${STATUS_ONLY}"
    printf 'dry_run=%s\n' "${DRY_RUN}"
    printf 'integration_branch=%s\n' "$(git_value "${GRI_ROOT}" branch)"
    printf 'integration_head=%s\n' "$(git_value "${GRI_ROOT}" head)"
    printf 'integration_tracked_dirty=%s\n' "$(git_value "${GRI_ROOT}" tracked_dirty)"
    printf 'grasu_branch=%s\n' "$(git_value "${GRASU_ROOT}" branch)"
    printf 'grasu_head=%s\n' "$(git_value "${GRASU_ROOT}" head)"
    printf 'grasu_tracked_dirty=%s\n' "$(git_value "${GRASU_ROOT}" tracked_dirty)"
    printf 'regraph_branch=%s\n' "$(git_value "${REGRAPH_ROOT}" branch)"
    printf 'regraph_head=%s\n' "$(git_value "${REGRAPH_ROOT}" head)"
    printf 'regraph_tracked_dirty=%s\n' "$(git_value "${REGRAPH_ROOT}" tracked_dirty)"
  } > "${path}"
}

write_evidence() {
  local path="$1"
  {
    printf 'kind\tpath\tsha256\tsize_bytes\n'
    for artifact in \
      "${HOST}" \
      "${XCLBIN}" \
      "${BUILD_ROOT}/manifest.env" \
      "${BUILD_ROOT}/inputs.tsv" \
      "${BUILD_ROOT}/compile_commands.sh" \
      "${BUILD_ROOT}/link_command.sh" \
      "${SMOKE_OUT}/run.env" \
      "${SMOKE_OUT}/summary.tsv" \
      "${COMPARE_OUT}/comparison.tsv" \
      "${COMPARE_OUT}/comparison.md"; do
      printf 'artifact\t%s\t%s\t%s\n' "${artifact}" "$(sha_or_missing "${artifact}")" "$(size_or_missing "${artifact}")"
    done
  } > "${path}"
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --host) HOST="$(abs_path "$2")"; shift 2 ;;
    --xclbin) XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --smoke-out) SMOKE_OUT="$(abs_path "$2")"; shift 2 ;;
    --compare-out) COMPARE_OUT="$(abs_path "$2")"; shift 2 ;;
    --host-summary) HOST_SUMMARY="$(abs_path "$2")"; shift 2 ;;
    --spine-summary) SPINE_SUMMARY="$(abs_path "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --vitis-settings) VITIS_SETTINGS="$(abs_path "$2")"; shift 2 ;;
    --platform-xpfm) PLATFORM_XPFM="$(abs_path "$2")"; shift 2 ;;
    --emconfig-path) EMCONFIG_PATH="$(abs_path "$2")"; shift 2 ;;
    --build-host) BUILD_HOST=1; shift ;;
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    --skip-compare) SKIP_COMPARE=1; shift ;;
    --status-only) STATUS_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

cd "${GRI_ROOT}"

if [[ -z "${BUILD_ROOT}" ]]; then
  BUILD_ROOT="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_stage0"
fi
if [[ -z "${XCLBIN}" ]]; then
  XCLBIN="${BUILD_ROOT}/build/grasu_regraph_pure_pipeline.${TARGET}.xclbin"
fi
if [[ -z "${LABEL}" ]]; then
  LABEL="$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
fi
if [[ -z "${TIMEOUT_SECONDS}" ]]; then
  if [[ "${TARGET}" == "hw_emu" ]]; then
    TIMEOUT_SECONDS=1800
  else
    TIMEOUT_SECONDS=600
  fi
fi
if [[ -z "${SMOKE_OUT}" ]]; then
  SMOKE_OUT="${GRI_ROOT}/results/pure_pipeline_${TARGET}_smoke_${LABEL}"
fi
if [[ -z "${COMPARE_OUT}" ]]; then
  COMPARE_OUT="${GRI_ROOT}/results/pure_pipeline_${TARGET}_compare_${LABEL}"
fi

RUN_DIR="${BUILD_ROOT}/run_logs"
mkdir -p "${RUN_DIR}"
FINALIZE_ENV="${RUN_DIR}/finalize_${LABEL}.env"
FINALIZE_EVIDENCE="${RUN_DIR}/finalize_${LABEL}_evidence.tsv"

write_finalize_env "${FINALIZE_ENV}"
write_evidence "${FINALIZE_EVIDENCE}"

if [[ "${STATUS_ONLY}" == "1" ]]; then
  echo "DONE finalize_env=${FINALIZE_ENV}"
  echo "DONE evidence=${FINALIZE_EVIDENCE}"
  exit 0
fi

if [[ "${BUILD_HOST}" == "1" ]]; then
  run_cmd "${SCRIPT_DIR}/build_pure_pipeline_host.sh" \
    --out-dir "$(dirname "${HOST}")" \
    --out-bin "${HOST}"
fi

if [[ "${DRY_RUN}" == "0" ]]; then
  if [[ ! -x "${HOST}" ]]; then
    echo "Missing executable pure pipeline host: ${HOST}" >&2
    exit 1
  fi
  if [[ ! -f "${XCLBIN}" ]]; then
    echo "Missing pure pipeline xclbin: ${XCLBIN}" >&2
    exit 1
  fi
fi

if [[ "${SKIP_SMOKE}" == "0" ]]; then
  smoke_cmd=(
    "${SCRIPT_DIR}/run_pure_pipeline_smoke.sh"
    --target "${TARGET}"
    --host "${HOST}"
    --xclbin "${XCLBIN}"
    --out-dir "${SMOKE_OUT}"
    --timeout "${TIMEOUT_SECONDS}"
    --vitis-settings "${VITIS_SETTINGS}"
    --platform-xpfm "${PLATFORM_XPFM}"
  )
  if [[ -n "${EMCONFIG_PATH}" ]]; then
    smoke_cmd+=(--emconfig-path "${EMCONFIG_PATH}")
  fi
  run_cmd "${smoke_cmd[@]}"
fi

if [[ "${SKIP_COMPARE}" == "0" && "${SKIP_SMOKE}" == "0" ]]; then
  compare_cmd=(
    python3 "${SCRIPT_DIR}/summarize_pure_pipeline_smoke.py"
    --host-summary "${HOST_SUMMARY}"
    --pure-summary "${SMOKE_OUT}/summary.tsv"
    --pure-env "${SMOKE_OUT}/run.env"
    --out-dir "${COMPARE_OUT}"
  )
  if [[ -f "${SPINE_SUMMARY}" ]]; then
    compare_cmd+=(--spine-summary "${SPINE_SUMMARY}")
  fi
  run_cmd "${compare_cmd[@]}"
fi

write_finalize_env "${FINALIZE_ENV}"
write_evidence "${FINALIZE_EVIDENCE}"

echo "DONE finalize_env=${FINALIZE_ENV}"
echo "DONE evidence=${FINALIZE_EVIDENCE}"
echo "DONE smoke_out=${SMOKE_OUT}"
echo "DONE compare_out=${COMPARE_OUT}"
