#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw_emu"
BUILD_ROOT=""
OUT_FILE=""
TAIL_LINES=40
NO_WRITE=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Inspect a GraSU -> ReGraph pure-pipeline Vitis build root. This is intended
for long hw_emu/hw builds: it reports xclbin status, command-script hashes,
latest run logs, return-code files, matching Vitis/Vivado processes, and recent
error lines.

Options:
  --target sw_emu|hw_emu|hw   Build target. Default: ${TARGET}
  --build-root PATH           Build root. Default: .tmp_build/pure_pipeline_<target>_stage0
  --out-file PATH             Report path. Default: <build-root>/run_logs/monitor_<timestamp>.txt
  --tail-lines N              Lines to scan from each log. Default: ${TAIL_LINES}
  --no-write                  Print report only; do not write a monitor file.
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

mtime_or_missing() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    stat -c '%y' "${path}"
  else
    printf 'MISSING'
  fi
}

emit_file_row() {
  local label="$1"
  local path="$2"
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "${label}" "${path}" "$(sha_or_missing "${path}")" \
    "$(size_or_missing "${path}")" "$(mtime_or_missing "${path}")"
}

latest_matching_file() {
  local pattern="$1"
  find "${RUN_DIR}" -maxdepth 1 -type f -name "${pattern}" \
    -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR == 1 { sub(/^[^ ]+ /, ""); print }'
}

emit_log_summary() {
  local label="$1"
  local log_path="$2"
  local rc_path="$3"
  if [[ -z "${log_path}" || ! -f "${log_path}" ]]; then
    printf '%s_log\tMISSING\n' "${label}"
    return
  fi

  printf '%s_log\t%s\tbytes=%s\tmtime=%s\n' \
    "${label}" "${log_path}" "$(size_or_missing "${log_path}")" \
    "$(mtime_or_missing "${log_path}")"
  if [[ -n "${rc_path}" && -f "${rc_path}" ]]; then
    printf '%s_rc\t%s\n' "${label}" "$(tr -d '\n' < "${rc_path}")"
  else
    printf '%s_rc\tMISSING\n' "${label}"
  fi

  printf '%s_recent_errors\n' "${label}"
  tail -n "${TAIL_LINES}" "${log_path}" |
    grep -Ei '(^|[^A-Za-z])(error|failed|failure|critical warning|segmentation|aborted)([^A-Za-z]|$)' ||
    printf 'none\n'
}

emit_processes() {
  printf 'matching_processes\n'
  ps -eo pid,ppid,etime,stat,pcpu,pmem,args |
    awk -v root="${BUILD_ROOT}" -v xclbin="${OUT_XCLBIN}" '
      NR == 1 { header = $0; next }
      {
        if (index($0, "awk -v root=") ||
            index($0, "monitor_pure_pipeline_build.sh")) {
          next
        }
        is_builder = index($0, "v++") || index($0, "vivado") ||
                     index($0, "vitis") || index($0, "xocc") ||
                     index($0, "run_pure_pipeline_build") ||
                     index($0, "compile_commands.sh") ||
                     index($0, "link_command.sh")
        is_related = index($0, root) || index($0, xclbin) ||
                     index($0, "pure_pipeline")
        if (is_builder && is_related) {
          if (!printed) {
            print header
            printed = 1
          }
          print
        }
      }
      END {
        if (!printed) {
          print header
          print "none"
        }
      }
    ' || true
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --out-file) OUT_FILE="$(abs_path "$2")"; shift 2 ;;
    --tail-lines) TAIL_LINES="$2"; shift 2 ;;
    --no-write) NO_WRITE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

if [[ -z "${BUILD_ROOT}" ]]; then
  BUILD_ROOT="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_stage0"
fi

cd "${GRI_ROOT}"
MANIFEST="${BUILD_ROOT}/manifest.env"
if [[ ! -f "${MANIFEST}" ]]; then
  echo "Missing build manifest: ${MANIFEST}" >&2
  exit 1
fi

COMPILE_COMMANDS="$(manifest_value COMPILE_COMMANDS)"
LINK_COMMAND="$(manifest_value LINK_COMMAND)"
OUT_XCLBIN="$(manifest_value OUT_XCLBIN)"
RUN_DIR="${BUILD_ROOT}/run_logs"
mkdir -p "${RUN_DIR}"

if [[ -z "${OUT_FILE}" ]]; then
  OUT_FILE="${RUN_DIR}/monitor_$(date +%Y%m%d_%H%M%S).txt"
fi

compile_log="$(latest_matching_file 'compile_*.log')"
compile_rc=""
if [[ -n "${compile_log}" ]]; then
  compile_rc="${compile_log%.log}.rc"
fi
link_log="$(latest_matching_file 'link_*.log')"
link_rc=""
if [[ -n "${link_log}" ]]; then
  link_rc="${link_log%.log}.rc"
fi

report="$(
  {
    printf 'pure_pipeline_build_monitor\n'
    printf 'timestamp=%s\n' "$(date --iso-8601=seconds)"
    printf 'target=%s\n' "${TARGET}"
    printf 'build_root=%s\n' "${BUILD_ROOT}"
    printf 'out_xclbin=%s\n' "${OUT_XCLBIN}"
    printf '\n'

    printf 'core_artifacts\n'
    printf 'label\tpath\tsha256\tsize_bytes\tmtime\n'
    emit_file_row manifest "${MANIFEST}"
    emit_file_row inputs "${BUILD_ROOT}/inputs.tsv"
    emit_file_row compile_commands "${COMPILE_COMMANDS}"
    emit_file_row link_command "${LINK_COMMAND}"
    emit_file_row out_xclbin "${OUT_XCLBIN}"
    printf '\n'

    emit_processes
    printf '\n'

    printf 'latest_logs\n'
    emit_log_summary compile "${compile_log}" "${compile_rc}"
    printf '\n'
    emit_log_summary link "${link_log}" "${link_rc}"
  }
)"

printf '%s\n' "${report}"
if [[ "${NO_WRITE}" == "0" ]]; then
  printf '%s\n' "${report}" > "${OUT_FILE}"
  echo "DONE monitor_report=${OUT_FILE}"
fi
