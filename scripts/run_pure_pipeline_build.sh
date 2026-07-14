#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw_emu"
BUILD_ROOT=""
LABEL=""
VITIS_SETTINGS="/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
PREPARE=0
SKIP_COMPILE=0
SKIP_LINK=0
STATUS_ONLY=0
DRY_RUN=0
REQUIRE_IDLE=0
WAIT_IDLE_SECONDS=0
IDLE_POLL_SECONDS=60

usage() {
  cat <<USAGE
Usage: $0 [options]

Run or inspect the reproducible GraSU -> ReGraph pure-pipeline Vitis build.
The script wraps the generated compile/link scripts and records logs, return
codes, source state, command hashes, XO hashes, and xclbin hash.

Options:
  --target sw_emu|hw_emu|hw   Build target. Default: ${TARGET}
  --build-root PATH           Build root. Default: .tmp_build/pure_pipeline_<target>_stage0
  --label NAME                Log/evidence suffix. Default: current git short hash.
  --vitis-settings PATH       Vitis settings64.sh. Default: ${VITIS_SETTINGS}
  --prepare                   Regenerate compile/link scripts before running.
  --skip-compile              Do not run compile_commands.sh.
  --skip-link                 Do not run link_command.sh.
  --status-only               Only collect evidence; do not run compile/link.
  --dry-run                   Print commands that would run and collect evidence.
  --require-idle              Refuse to start if Vitis/Vivado processes are active.
  --wait-idle SECONDS         Wait up to SECONDS for Vitis/Vivado to go idle; implies --require-idle.
  --idle-poll SECONDS         Poll interval for --wait-idle. Default: ${IDLE_POLL_SECONDS}
  -h, --help                  Show this help.

Examples:
  $0 --target hw_emu --label after_fa17c35
  $0 --target hw --label after_fa17c35 --skip-compile
  $0 --target hw_emu --status-only
  $0 --target hw_emu --label after_fa17c35 --require-idle
  $0 --target hw_emu --label after_fa17c35 --wait-idle 7200
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

active_vitis_vivado_processes() {
  ps -eo pid,ppid,etime,stat,pcpu,pmem,comm,args |
    awk '
      NR == 1 { next }
      {
        comm = $7
        is_builder = comm == "v++" || comm == "vpl" || comm == "vivado" ||
                     comm == "vrs" || comm == "xocc" || comm == "xsimk" ||
                     index(comm, "genericpcie") == 1
        if (is_builder) {
          print
        }
      }
    '
}

write_idle_check() {
  local out_file="$1"
  local active_processes="${2-}"
  if [[ $# -lt 2 ]]; then
    active_processes="$(active_vitis_vivado_processes || true)"
  fi
  {
    printf 'pure_pipeline_build_idle_check\n'
    printf 'timestamp=%s\n' "$(date --iso-8601=seconds)"
    printf 'target=%s\n' "${TARGET}"
    printf 'build_root=%s\n' "${BUILD_ROOT}"
    printf 'require_idle=%s\n' "${REQUIRE_IDLE}"
    printf 'wait_idle_seconds=%s\n' "${WAIT_IDLE_SECONDS}"
    printf 'idle_poll_seconds=%s\n' "${IDLE_POLL_SECONDS}"
    printf '\n'
    printf 'active_vitis_vivado_processes\n'
    printf '    PID    PPID     ELAPSED STAT %%CPU %%MEM COMMAND         ARGS\n'
    if [[ -n "${active_processes}" ]]; then
      printf '%s\n' "${active_processes}"
    else
      printf 'none\n'
    fi
  } > "${out_file}"
}

git_field() {
  local root="$1"
  local field="$2"
  if ! git -C "${root}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'not_git'
    return
  fi
  case "${field}" in
    head) git -C "${root}" rev-parse HEAD ;;
    branch) git -C "${root}" branch --show-current ;;
    dirty)
      if [[ -n "$(git -C "${root}" status --short --untracked-files=no)" ]]; then
        printf 'dirty'
      else
        printf 'clean'
      fi
      ;;
    untracked_count)
      git -C "${root}" status --short --untracked-files=all |
        awk '$1 == "??" { count++ } END { print count + 0 }'
      ;;
    *) printf 'unknown' ;;
  esac
}

write_run_env() {
  local env_file="$1"
  {
    printf 'target=%s\n' "${TARGET}"
    printf 'build_root=%s\n' "${BUILD_ROOT}"
    printf 'label=%s\n' "${LABEL}"
    printf 'vitis_settings=%s\n' "${VITIS_SETTINGS}"
    printf 'prepare=%s\n' "${PREPARE}"
    printf 'skip_compile=%s\n' "${SKIP_COMPILE}"
    printf 'skip_link=%s\n' "${SKIP_LINK}"
    printf 'status_only=%s\n' "${STATUS_ONLY}"
    printf 'dry_run=%s\n' "${DRY_RUN}"
    printf 'require_idle=%s\n' "${REQUIRE_IDLE}"
    printf 'wait_idle_seconds=%s\n' "${WAIT_IDLE_SECONDS}"
    printf 'idle_poll_seconds=%s\n' "${IDLE_POLL_SECONDS}"
    printf 'integration_branch=%s\n' "$(git_field "${GRI_ROOT}" branch)"
    printf 'integration_head=%s\n' "$(git_field "${GRI_ROOT}" head)"
    printf 'integration_tracked_dirty=%s\n' "$(git_field "${GRI_ROOT}" dirty)"
    printf 'integration_untracked_count=%s\n' "$(git_field "${GRI_ROOT}" untracked_count)"
    printf 'grasu_branch=%s\n' "$(git_field "${GRASU_ROOT}" branch)"
    printf 'grasu_head=%s\n' "$(git_field "${GRASU_ROOT}" head)"
    printf 'grasu_tracked_dirty=%s\n' "$(git_field "${GRASU_ROOT}" dirty)"
    printf 'grasu_untracked_count=%s\n' "$(git_field "${GRASU_ROOT}" untracked_count)"
    printf 'regraph_branch=%s\n' "$(git_field "${REGRAPH_ROOT}" branch)"
    printf 'regraph_head=%s\n' "$(git_field "${REGRAPH_ROOT}" head)"
    printf 'regraph_tracked_dirty=%s\n' "$(git_field "${REGRAPH_ROOT}" dirty)"
    printf 'regraph_untracked_count=%s\n' "$(git_field "${REGRAPH_ROOT}" untracked_count)"
    printf 'manifest=%s\n' "${MANIFEST}"
    printf 'compile_commands=%s\n' "${COMPILE_COMMANDS}"
    printf 'link_command=%s\n' "${LINK_COMMAND}"
    printf 'out_xclbin=%s\n' "${OUT_XCLBIN}"
  } > "${env_file}"
}

write_artifact_evidence() {
  local out_file="$1"
  {
    printf 'kind\tpath\tsha256\tsize_bytes\n'
    for path in \
      "${MANIFEST}" \
      "${BUILD_ROOT}/inputs.tsv" \
      "${COMPILE_COMMANDS}" \
      "${LINK_COMMAND}" \
      "${OUT_XCLBIN}"; do
      printf 'core\t%s\t%s\t%s\n' "${path}" "$(sha_or_missing "${path}")" "$(size_or_missing "${path}")"
    done

    if [[ -d "${BUILD_ROOT}/build" ]]; then
      find "${BUILD_ROOT}/build" -maxdepth 1 -type f \( -name '*.xo' -o -name '*.xclbin' \) |
        sort |
        while IFS= read -r artifact; do
          printf 'build\t%s\t%s\t%s\n' "${artifact}" "$(sha_or_missing "${artifact}")" "$(size_or_missing "${artifact}")"
        done
    fi
  } > "${out_file}"
}

run_logged_script() {
  local script="$1"
  local log_file="$2"
  local rc_file="$3"

  printf '+ %q\n' "${script}"
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf 'dry_run: would execute %s\n' "${script}" | tee "${log_file}"
    printf '0\n' > "${rc_file}"
    return 0
  fi

  set +e
  "${script}" 2>&1 | tee "${log_file}"
  local rc=${PIPESTATUS[0]}
  set -e
  printf '%s\n' "${rc}" > "${rc_file}"
  return "${rc}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --vitis-settings) VITIS_SETTINGS="$(abs_path "$2")"; shift 2 ;;
    --prepare) PREPARE=1; shift ;;
    --skip-compile) SKIP_COMPILE=1; shift ;;
    --skip-link) SKIP_LINK=1; shift ;;
    --status-only) STATUS_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --require-idle) REQUIRE_IDLE=1; shift ;;
    --wait-idle) WAIT_IDLE_SECONDS="$2"; REQUIRE_IDLE=1; shift 2 ;;
    --idle-poll) IDLE_POLL_SECONDS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${WAIT_IDLE_SECONDS}" in
  ''|*[!0-9]*) echo "--wait-idle must be a non-negative integer" >&2; exit 2 ;;
esac
case "${IDLE_POLL_SECONDS}" in
  ''|*[!0-9]*) echo "--idle-poll must be a positive integer" >&2; exit 2 ;;
esac
if (( IDLE_POLL_SECONDS < 1 )); then
  echo "--idle-poll must be at least 1" >&2
  exit 2
fi

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

if [[ -z "${BUILD_ROOT}" ]]; then
  BUILD_ROOT="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_stage0"
fi
if [[ -z "${LABEL}" ]]; then
  LABEL="$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
fi

cd "${GRI_ROOT}"

if [[ "${PREPARE}" == "1" ]]; then
  prepare_cmd=("${SCRIPT_DIR}/prepare_pure_hw_pipeline_build.sh" --target "${TARGET}" --build-root "${BUILD_ROOT}")
  printf '+'
  printf ' %q' "${prepare_cmd[@]}"
  printf '\n'
  if [[ "${DRY_RUN}" == "0" ]]; then
    "${prepare_cmd[@]}"
  fi
fi

MANIFEST="${BUILD_ROOT}/manifest.env"
if [[ ! -f "${MANIFEST}" ]]; then
  echo "Missing build manifest: ${MANIFEST}" >&2
  exit 1
fi

COMPILE_COMMANDS="$(manifest_value COMPILE_COMMANDS)"
LINK_COMMAND="$(manifest_value LINK_COMMAND)"
OUT_XCLBIN="$(manifest_value OUT_XCLBIN)"

if [[ -z "${COMPILE_COMMANDS}" || -z "${LINK_COMMAND}" || -z "${OUT_XCLBIN}" ]]; then
  echo "Build manifest is missing COMPILE_COMMANDS, LINK_COMMAND, or OUT_XCLBIN." >&2
  exit 1
fi
if [[ ! -x "${COMPILE_COMMANDS}" ]]; then
  echo "Missing executable compile script: ${COMPILE_COMMANDS}" >&2
  exit 1
fi
if [[ ! -x "${LINK_COMMAND}" ]]; then
  echo "Missing executable link script: ${LINK_COMMAND}" >&2
  exit 1
fi
if [[ ! -f "${VITIS_SETTINGS}" ]]; then
  echo "Missing Vitis settings: ${VITIS_SETTINGS}" >&2
  exit 1
fi

RUN_DIR="${BUILD_ROOT}/run_logs"
mkdir -p "${RUN_DIR}"
RUN_ENV="${RUN_DIR}/build_${LABEL}.env"
EVIDENCE="${RUN_DIR}/build_${LABEL}_evidence.tsv"
COMPILE_LOG="${RUN_DIR}/compile_${LABEL}.log"
LINK_LOG="${RUN_DIR}/link_${LABEL}.log"
COMPILE_RC="${RUN_DIR}/compile_${LABEL}.rc"
LINK_RC="${RUN_DIR}/link_${LABEL}.rc"
IDLE_CHECK="${RUN_DIR}/idle_check_${LABEL}.txt"

write_run_env "${RUN_ENV}"
write_artifact_evidence "${EVIDENCE}"

if [[ "${STATUS_ONLY}" == "1" ]]; then
  echo "DONE run_env=${RUN_ENV}"
  echo "DONE evidence=${EVIDENCE}"
  exit 0
fi

if [[ "${REQUIRE_IDLE}" == "1" ]]; then
  idle_start_epoch="$(date +%s)"
  while true; do
    active_processes="$(active_vitis_vivado_processes || true)"
    write_idle_check "${IDLE_CHECK}" "${active_processes}"
    if [[ -z "${active_processes}" ]]; then
      break
    fi

    now_epoch="$(date +%s)"
    idle_wait_elapsed=$((now_epoch - idle_start_epoch))
    if (( WAIT_IDLE_SECONDS == 0 || idle_wait_elapsed >= WAIT_IDLE_SECONDS )); then
      echo "Active Vitis/Vivado processes detected; refusing to start." >&2
      echo "Idle-check report: ${IDLE_CHECK}" >&2
      exit 3
    fi

    idle_wait_remaining=$((WAIT_IDLE_SECONDS - idle_wait_elapsed))
    sleep_seconds="${IDLE_POLL_SECONDS}"
    if (( sleep_seconds > idle_wait_remaining )); then
      sleep_seconds="${idle_wait_remaining}"
    fi
    if (( sleep_seconds < 1 )); then
      sleep_seconds=1
    fi
    echo "Active Vitis/Vivado processes detected; waiting ${sleep_seconds}s (${idle_wait_elapsed}/${WAIT_IDLE_SECONDS}s elapsed)." >&2
    echo "Idle-check report: ${IDLE_CHECK}" >&2
    sleep "${sleep_seconds}"
  done
fi

# shellcheck disable=SC1090
source "${VITIS_SETTINGS}"
export XILINX_XRT="${XILINX_XRT:-/opt/xilinx/xrt}"
export LD_LIBRARY_PATH="${XILINX_XRT}/lib:${LD_LIBRARY_PATH:-}"
export PATH="${XILINX_XRT}/bin:${PATH}"

compile_rc=0
link_rc=0
if [[ "${SKIP_COMPILE}" == "0" ]]; then
  run_logged_script "${COMPILE_COMMANDS}" "${COMPILE_LOG}" "${COMPILE_RC}" || compile_rc=$?
fi
if [[ "${SKIP_LINK}" == "0" && "${compile_rc}" == "0" ]]; then
  run_logged_script "${LINK_COMMAND}" "${LINK_LOG}" "${LINK_RC}" || link_rc=$?
fi

write_artifact_evidence "${EVIDENCE}"

echo "DONE run_env=${RUN_ENV}"
echo "DONE evidence=${EVIDENCE}"
echo "DONE compile_log=${COMPILE_LOG}"
echo "DONE link_log=${LINK_LOG}"
echo "DONE out_xclbin=${OUT_XCLBIN}"

if [[ "${compile_rc}" != "0" ]]; then
  exit "${compile_rc}"
fi
if [[ "${link_rc}" != "0" ]]; then
  exit "${link_rc}"
fi
