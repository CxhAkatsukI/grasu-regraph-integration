#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

BUILD_ROOT=""
SESSION=""
IDLE_WARN_MINUTES=20

usage() {
  cat <<USAGE
Usage: $0 [options]

Summarize a running or completed combined GraSU + ReGraph Vitis link build.
This is intended for long real-hw builds where the visible log can sit at
"running" for a while.

Options:
  --build-root PATH        Combined build root. Default: newest combined_hw_coldinit_250mhz_*.
  --session NAME           Tmux session name. Default: basename of build root.
  --idle-warn-minutes N    Warn if no log/progress file changed for N minutes. Default: ${IDLE_WARN_MINUTES}.
  -h, --help               Show this help.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

latest_combined_hw_root() {
  find "${GRI_ROOT}/.tmp_build" -maxdepth 1 -type d \
    -name 'combined_hw_coldinit_250mhz_*' \
    -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | awk 'NR == 1 { sub(/^[^ ]+ /, ""); print }'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-root) BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --session) SESSION="$2"; shift 2 ;;
    --idle-warn-minutes) IDLE_WARN_MINUTES="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${IDLE_WARN_MINUTES}" in
  ''|*[!0-9]*) echo "--idle-warn-minutes must be a non-negative integer" >&2; exit 2 ;;
esac

if [[ -z "${BUILD_ROOT}" ]]; then
  BUILD_ROOT="$(latest_combined_hw_root)"
fi
if [[ -z "${BUILD_ROOT}" || ! -d "${BUILD_ROOT}" ]]; then
  echo "Missing combined build root. Pass --build-root PATH." >&2
  exit 1
fi
if [[ -z "${SESSION}" ]]; then
  SESSION="$(basename "${BUILD_ROOT}")"
fi

TMUX_STATUS="stopped"
if tmux has-session -t "${SESSION}" 2>/dev/null; then
  TMUX_STATUS="running"
fi

MANIFEST="${BUILD_ROOT}/manifest.env"
TARGET="hw"
if [[ -f "${MANIFEST}" ]]; then
  parsed_target="$(awk -F= '/^TARGET=/ { print $2 }' "${MANIFEST}" | tail -1)"
  if [[ -n "${parsed_target}" ]]; then
    TARGET="${parsed_target}"
  fi
fi

TOP_LOG="${BUILD_ROOT}/tmux_driver.log"
LINK_LOG="${BUILD_ROOT}/link_${TARGET}.log"
VPL_LOG="${BUILD_ROOT}/build/link/link/vivado/vpl/runme.log"
VIVADO_LOG="${BUILD_ROOT}/build/link/link/vivado/vpl/vivado.log"
IMPL_LOG="${BUILD_ROOT}/build/link/link/vivado/vpl/prj/prj.runs/impl_1/runme.log"
XCLBIN="${BUILD_ROOT}/build/grasu_regraph_combined.${TARGET}.xclbin"
LINK_SUMMARY="${BUILD_ROOT}/build/grasu_regraph_combined.${TARGET}.xclbin.link_summary"

newest_log_line=""
newest_activity_line=""
if [[ -d "${BUILD_ROOT}" ]]; then
  newest_log_line="$(
    find "${BUILD_ROOT}" -type f \( -name '*.log' -o -name '*.jou' -o -name '*.str' \) \
      -printf '%T@ %TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null \
      | sort -nr \
      | head -1 || true
  )"
  newest_activity_line="$(
    find "${BUILD_ROOT}" -type f \( \
      -name '*.log' -o -name '*.jou' -o -name '*.str' -o \
      -name '*.pb' -o -name '*.rst' -o -name '*.json' -o -name '*.xutil' \
    \) \
      -printf '%T@ %TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null \
      | sort -nr \
      | head -1 || true
  )"
fi

idle_seconds=""
if [[ -n "${newest_activity_line}" ]]; then
  newest_epoch="$(awk '{ print int($1) }' <<<"${newest_activity_line}")"
  now_epoch="$(date +%s)"
  idle_seconds=$(( now_epoch - newest_epoch ))
fi

echo "# Combined HW Build Monitor"
echo
printf 'build_root=%s\n' "${BUILD_ROOT}"
printf 'session=%s\n' "${SESSION}"
printf 'tmux=%s\n' "${TMUX_STATUS}"
printf 'target=%s\n' "${TARGET}"
printf 'checked_at=%s\n' "$(date -Ins)"
echo

echo "## Artifacts"
if [[ -f "${XCLBIN}" ]]; then
  ls -lah "${XCLBIN}"
  sha256sum "${XCLBIN}"
else
  printf 'xclbin=missing (%s)\n' "${XCLBIN}"
fi
if [[ -f "${LINK_SUMMARY}" ]]; then
  ls -lah "${LINK_SUMMARY}"
else
  printf 'link_summary=missing (%s)\n' "${LINK_SUMMARY}"
fi
echo

echo "## Log Activity"
if [[ -n "${newest_log_line}" ]]; then
  printf 'newest_log=%s\n' "$(awk '{ $1=""; sub(/^ /, ""); print }' <<<"${newest_log_line}")"
else
  echo "newest_log=none"
fi
if [[ -n "${newest_activity_line}" ]]; then
  printf 'newest_activity=%s\n' "$(awk '{ $1=""; sub(/^ /, ""); print }' <<<"${newest_activity_line}")"
  printf 'idle_seconds=%s\n' "${idle_seconds}"
  if (( idle_seconds >= IDLE_WARN_MINUTES * 60 )); then
    printf 'idle_warning=latest activity is older than %s minutes\n' "${IDLE_WARN_MINUTES}"
  else
    printf 'idle_warning=none\n'
  fi
else
  echo "newest_activity=none"
fi
echo

echo "## Latest VPL Progress"
if [[ -f "${VPL_LOG}" ]]; then
  rg -n 'Run vpl: Step|Block-level synthesis|Waiting for|Launched .*synth|place_design|phys_opt|route_design|write_bitstream|ERROR|CRITICAL WARNING' "${VPL_LOG}" \
    | tail -40 \
    | awk '{ if (length($0) > 240) print substr($0, 1, 240) "..."; else print }' || true
else
  printf 'vpl_log=missing (%s)\n' "${VPL_LOG}"
fi
echo

echo "## Top Driver Tail"
if [[ -f "${TOP_LOG}" ]]; then
  tail -30 "${TOP_LOG}"
else
  printf 'top_log=missing (%s)\n' "${TOP_LOG}"
fi
echo

echo "## Implementation Run Tail"
if [[ -f "${IMPL_LOG}" ]]; then
  rg -n 'Command:|Start |Finished |link_design|opt_design|place_design|phys_opt_design|route_design|write_bitstream|report_|WNS|TNS|ERROR|CRITICAL WARNING|WARNING' "${IMPL_LOG}" \
    | tail -50 \
    | awk '{ if (length($0) > 240) print substr($0, 1, 240) "..."; else print }' || true
else
  printf 'impl_log=missing (%s)\n' "${IMPL_LOG}"
fi
echo

echo "## Recent Errors And Warnings"
for log in "${TOP_LOG}" "${LINK_LOG}" "${VPL_LOG}" "${VIVADO_LOG}" "${IMPL_LOG}"; do
  if [[ -f "${log}" ]]; then
    rg -n 'ERROR|CRITICAL WARNING|FATAL|Killed|failed|Failed' "${log}" \
      | tail -20 \
      | awk '{ if (length($0) > 240) print substr($0, 1, 240) "..."; else print }' || true
  fi
done
echo

echo "## Matching Processes"
ps -u "${USER}" -o pid,ppid,stat,pcpu,pmem,etime,cmd \
  | rg -F "${BUILD_ROOT}" \
  | head -80 \
  | awk '{ if (length($0) > 240) print substr($0, 1, 240) "..."; else print }' || true
