#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw_emu"
BUILD_ROOT=""
LABEL=""
OUT_FILE=""
VITIS_SETTINGS="/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
MIN_BUILD_FREE_GB=100
MIN_TMP_FREE_GB=1
ALLOW_ACTIVE_BUILDERS=0
NO_WRITE=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Check whether the GraSU -> ReGraph pure-pipeline target is ready to start a
long hw_emu/hw build. This script does not start Vitis. It records generated
command-script hashes, required environment files, disk headroom, existing
xclbin status, and active Vitis/Vivado builders.

Options:
  --target sw_emu|hw_emu|hw   Target mode. Default: ${TARGET}
  --build-root PATH           Build root. Default: .tmp_build/pure_pipeline_<target>_stage0
  --label NAME                Report suffix. Default: current git short hash.
  --out-file PATH             Report path. Default: <build-root>/run_logs/readiness_<label>.txt
  --vitis-settings PATH       Vitis settings64.sh. Default: ${VITIS_SETTINGS}
  --min-build-free-gb N       Required free GB on build-root filesystem. Default: ${MIN_BUILD_FREE_GB}
  --min-tmp-free-gb N         Required free GB on /tmp. Default: ${MIN_TMP_FREE_GB}
  --allow-active-builders     Report active builders but do not fail readiness on them.
  --no-write                  Print report only; do not write a report file.
  -h, --help                  Show this help.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

manifest_value() {
  local key="$1"
  awk -F= -v key="${key}" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "${MANIFEST}"
}

sha_or_missing() {
  local path="$1"
  if [[ -f "${path}" ]]; then
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

free_kb_or_zero() {
  local path="$1"
  df -Pk "${path}" 2>/dev/null | awk 'NR == 2 { print $4; found = 1 } END { if (!found) print 0 }'
}

kb_to_gb() {
  local kb="$1"
  awk -v kb="${kb}" 'BEGIN { printf "%.1f", kb / 1024 / 1024 }'
}

active_builder_processes() {
  ps -eo pid,ppid,etime,stat,pcpu,pmem,comm,args |
    awk '
      NR == 1 { next }
      {
        comm = $7
        is_builder = comm == "v++" || comm == "vpl" ||
                     comm == "vivado" || comm == "vrs" ||
                     comm == "xocc" || comm == "xsimk" ||
                     index(comm, "genericpcie") == 1
        if (is_builder) {
          print
        }
      }
    '
}

count_lines() {
  local text="$1"
  if [[ -z "${text}" ]]; then
    printf '0'
  else
    printf '%s\n' "${text}" | wc -l | awk '{print $1}'
  fi
}

emit_process_block() {
  local title="$1"
  local rows="$2"
  printf '%s\n' "${title}"
  printf '    PID    PPID     ELAPSED STAT %%CPU %%MEM COMMAND         ARGS\n'
  if [[ -n "${rows}" ]]; then
    printf '%s\n' "${rows}"
  else
    printf 'none\n'
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --out-file) OUT_FILE="$(abs_path "$2")"; shift 2 ;;
    --vitis-settings) VITIS_SETTINGS="$(abs_path "$2")"; shift 2 ;;
    --min-build-free-gb) MIN_BUILD_FREE_GB="$2"; shift 2 ;;
    --min-tmp-free-gb) MIN_TMP_FREE_GB="$2"; shift 2 ;;
    --allow-active-builders) ALLOW_ACTIVE_BUILDERS=1; shift ;;
    --no-write) NO_WRITE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac
for numeric in MIN_BUILD_FREE_GB MIN_TMP_FREE_GB; do
  value="${!numeric}"
  case "${value}" in
    ''|*[!0-9]*) echo "--${numeric,,} must be a non-negative integer" >&2; exit 2 ;;
  esac
done

cd "${GRI_ROOT}"

if [[ -z "${BUILD_ROOT}" ]]; then
  BUILD_ROOT="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_stage0"
fi
if [[ -z "${LABEL}" ]]; then
  LABEL="$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
fi

RUN_DIR="${BUILD_ROOT}/run_logs"
mkdir -p "${RUN_DIR}"
if [[ -z "${OUT_FILE}" ]]; then
  OUT_FILE="${RUN_DIR}/readiness_${LABEL}.txt"
fi

MANIFEST="${BUILD_ROOT}/manifest.env"
COMPILE_COMMANDS=""
LINK_COMMAND=""
OUT_XCLBIN="${BUILD_ROOT}/build/grasu_regraph_pure_pipeline.${TARGET}.xclbin"
if [[ -f "${MANIFEST}" ]]; then
  COMPILE_COMMANDS="$(manifest_value COMPILE_COMMANDS)"
  LINK_COMMAND="$(manifest_value LINK_COMMAND)"
  manifest_xclbin="$(manifest_value OUT_XCLBIN)"
  if [[ -n "${manifest_xclbin}" ]]; then
    OUT_XCLBIN="${manifest_xclbin}"
  fi
fi

blocking_count=0
warning_count=0

manifest_status="PASS"
if [[ ! -f "${MANIFEST}" ]]; then
  manifest_status="FAIL"
  blocking_count=$((blocking_count + 1))
fi

compile_status="PASS"
if [[ -z "${COMPILE_COMMANDS}" || ! -x "${COMPILE_COMMANDS}" ]]; then
  compile_status="FAIL"
  blocking_count=$((blocking_count + 1))
fi

link_status="PASS"
if [[ -z "${LINK_COMMAND}" || ! -x "${LINK_COMMAND}" ]]; then
  link_status="FAIL"
  blocking_count=$((blocking_count + 1))
fi

vitis_status="PASS"
if [[ ! -f "${VITIS_SETTINGS}" ]]; then
  vitis_status="FAIL"
  blocking_count=$((blocking_count + 1))
fi

build_free_kb="$(free_kb_or_zero "${BUILD_ROOT}")"
tmp_free_kb="$(free_kb_or_zero /tmp)"
min_build_free_kb=$((MIN_BUILD_FREE_GB * 1024 * 1024))
min_tmp_free_kb=$((MIN_TMP_FREE_GB * 1024 * 1024))

build_space_status="PASS"
if (( build_free_kb < min_build_free_kb )); then
  build_space_status="FAIL"
  blocking_count=$((blocking_count + 1))
fi

tmp_space_status="PASS"
if (( tmp_free_kb < min_tmp_free_kb )); then
  tmp_space_status="FAIL"
  blocking_count=$((blocking_count + 1))
fi

all_builders="$(active_builder_processes || true)"
related_builders=""
external_builders=""
if [[ -n "${all_builders}" ]]; then
  related_builders="$(
    printf '%s\n' "${all_builders}" |
      awk -v root="${BUILD_ROOT}" -v xclbin="${OUT_XCLBIN}" '
        index($0, root) || index($0, xclbin) || index($0, "run_pure_pipeline") ||
        index($0, "compile_commands.sh") || index($0, "link_command.sh") { print }
      '
  )"
  external_builders="$(
    printf '%s\n' "${all_builders}" |
      awk -v root="${BUILD_ROOT}" -v xclbin="${OUT_XCLBIN}" '
        !(index($0, root) || index($0, xclbin) || index($0, "run_pure_pipeline") ||
          index($0, "compile_commands.sh") || index($0, "link_command.sh")) { print }
      '
  )"
fi

related_count="$(count_lines "${related_builders}")"
external_count="$(count_lines "${external_builders}")"
builder_status="PASS"
if (( related_count > 0 || external_count > 0 )); then
  builder_status="FAIL"
  if [[ "${ALLOW_ACTIVE_BUILDERS}" == "0" ]]; then
    blocking_count=$((blocking_count + 1))
  else
    warning_count=$((warning_count + 1))
  fi
fi

xclbin_status="MISSING"
if [[ -f "${OUT_XCLBIN}" ]]; then
  xclbin_status="PRESENT"
fi

ready="no"
if (( blocking_count == 0 )); then
  ready="yes"
fi

next_command="./scripts/run_pure_pipeline_target_flow.sh --target ${TARGET} --label after_$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || printf unknown) --wait-idle 7200 --idle-poll 60 --gate-case tiny_star_v16_u12"
case "${TARGET}" in
  hw_emu) next_command="${next_command} --gate-timeout 900" ;;
  hw) next_command="${next_command} --gate-timeout 300" ;;
  sw_emu) next_command="${next_command} --gate-timeout 180" ;;
esac

report="$(
  {
    printf 'pure_pipeline_build_readiness\n'
    printf 'timestamp=%s\n' "$(date --iso-8601=seconds)"
    printf 'target=%s\n' "${TARGET}"
    printf 'build_root=%s\n' "${BUILD_ROOT}"
    printf 'out_xclbin=%s\n' "${OUT_XCLBIN}"
    printf 'ready=%s\n' "${ready}"
    printf 'blocking_count=%s\n' "${blocking_count}"
    printf 'warning_count=%s\n' "${warning_count}"
    printf 'allow_active_builders=%s\n' "${ALLOW_ACTIVE_BUILDERS}"
    printf 'recommended_next_command=%s\n' "${next_command}"
    printf '\n'

    printf 'core_checks\n'
    printf 'check\tstatus\tdetail\n'
    printf 'manifest\t%s\t%s sha256=%s size=%s\n' "${manifest_status}" "${MANIFEST}" "$(sha_or_missing "${MANIFEST}")" "$(size_or_missing "${MANIFEST}")"
    printf 'compile_commands\t%s\t%s sha256=%s size=%s\n' "${compile_status}" "${COMPILE_COMMANDS:-MISSING}" "$(sha_or_missing "${COMPILE_COMMANDS:-}")" "$(size_or_missing "${COMPILE_COMMANDS:-}")"
    printf 'link_command\t%s\t%s sha256=%s size=%s\n' "${link_status}" "${LINK_COMMAND:-MISSING}" "$(sha_or_missing "${LINK_COMMAND:-}")" "$(size_or_missing "${LINK_COMMAND:-}")"
    printf 'vitis_settings\t%s\t%s\n' "${vitis_status}" "${VITIS_SETTINGS}"
    printf 'out_xclbin\t%s\t%s sha256=%s size=%s\n' "${xclbin_status}" "${OUT_XCLBIN}" "$(sha_or_missing "${OUT_XCLBIN}")" "$(size_or_missing "${OUT_XCLBIN}")"
    printf 'active_builders\t%s\trelated=%s external=%s\n' "${builder_status}" "${related_count}" "${external_count}"
    printf '\n'

    printf 'resources\n'
    printf 'resource\tstatus\tfree_gb\tminimum_gb\tpath\n'
    printf 'build_root_fs\t%s\t%s\t%s\t%s\n' "${build_space_status}" "$(kb_to_gb "${build_free_kb}")" "${MIN_BUILD_FREE_GB}" "${BUILD_ROOT}"
    printf 'tmp_fs\t%s\t%s\t%s\t/tmp\n' "${tmp_space_status}" "$(kb_to_gb "${tmp_free_kb}")" "${MIN_TMP_FREE_GB}"
    printf '\n'

    emit_process_block related_vitis_vivado_processes "${related_builders}"
    printf '\n'
    emit_process_block external_vitis_vivado_processes "${external_builders}"
  }
)"

printf '%s\n' "${report}"
if [[ "${NO_WRITE}" == "0" ]]; then
  printf '%s\n' "${report}" > "${OUT_FILE}"
  echo "DONE readiness_report=${OUT_FILE}"
fi

if [[ "${ready}" == "yes" ]]; then
  exit 0
fi
exit 3
