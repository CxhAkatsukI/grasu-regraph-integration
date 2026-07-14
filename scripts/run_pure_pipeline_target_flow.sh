#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw_emu"
LABEL=""
WAIT_IDLE_SECONDS=7200
IDLE_POLL_SECONDS=60
IDLE_SETTLE_SECONDS=0
MONITOR_TAIL_LINES=40
GATE_CASE="tiny_star_v16_u12"
GATE_TIMEOUT_SECONDS=""
TIMEOUT_SECONDS=""
BUILD_HOST=1
SKIP_BUILD=0
SKIP_FINALIZE=0
SKIP_AUDIT=0
CLEAN_BUILD_ARTIFACTS=0
READINESS_CHECK=1
STRICT_READINESS=0
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Run the reproducible pure-pipeline target flow:
  build with idle protection -> monitor -> staged finalize -> requirement audit.

Options:
  --target sw_emu|hw_emu|hw   Target mode. Default: ${TARGET}
  --label NAME                Evidence suffix. Default: after_<current git short hash>.
  --wait-idle SECONDS         Build wait-idle timeout. Default: ${WAIT_IDLE_SECONDS}
  --idle-poll SECONDS         Build wait-idle poll interval. Default: ${IDLE_POLL_SECONDS}
  --idle-settle SECONDS       Continuous idle required before build launch. Default: ${IDLE_SETTLE_SECONDS}
  --monitor-tail N            Monitor tail lines. Default: ${MONITOR_TAIL_LINES}
  --gate-case NAME            Finalize gate case. Default: ${GATE_CASE}
  --no-gate                   Do not run a staged gate before full smoke.
  --gate-timeout SECONDS      Finalize gate timeout. Default: target-specific.
  --timeout SECONDS           Full smoke timeout. Default: finalize wrapper default.
  --build-host                Rebuild pure_pipeline_host during finalize. Default.
  --no-build-host             Do not rebuild pure_pipeline_host during finalize.
  --clean-build-artifacts     Remove existing target build/ artifacts before launching.
  --readiness                 Record a build-readiness preflight report. Default.
  --no-readiness              Do not run the readiness preflight.
  --strict-readiness          Fail preflight when unrelated Vitis/Vivado builders are active.
  --skip-build                Do not run the build wrapper.
  --skip-finalize             Do not run finalize/smoke/compare.
  --skip-audit                Do not run requirement audit.
  --dry-run                   Print commands; do not execute them.
  -h, --help                  Show this help.
USAGE
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
    --label) LABEL="$2"; shift 2 ;;
    --wait-idle) WAIT_IDLE_SECONDS="$2"; shift 2 ;;
    --idle-poll) IDLE_POLL_SECONDS="$2"; shift 2 ;;
    --idle-settle) IDLE_SETTLE_SECONDS="$2"; shift 2 ;;
    --monitor-tail) MONITOR_TAIL_LINES="$2"; shift 2 ;;
    --gate-case) GATE_CASE="$2"; shift 2 ;;
    --no-gate) GATE_CASE=""; shift ;;
    --gate-timeout) GATE_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --build-host) BUILD_HOST=1; shift ;;
    --no-build-host) BUILD_HOST=0; shift ;;
    --clean-build-artifacts) CLEAN_BUILD_ARTIFACTS=1; shift ;;
    --readiness) READINESS_CHECK=1; shift ;;
    --no-readiness) READINESS_CHECK=0; shift ;;
    --strict-readiness) STRICT_READINESS=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --skip-finalize) SKIP_FINALIZE=1; shift ;;
    --skip-audit) SKIP_AUDIT=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac
for numeric in WAIT_IDLE_SECONDS IDLE_POLL_SECONDS IDLE_SETTLE_SECONDS MONITOR_TAIL_LINES; do
  value="${!numeric}"
  case "${value}" in
    ''|*[!0-9]*) echo "--${numeric,,} must be a non-negative integer" >&2; exit 2 ;;
  esac
done
if (( IDLE_POLL_SECONDS < 1 )); then
  echo "--idle-poll must be at least 1" >&2
  exit 2
fi
if (( MONITOR_TAIL_LINES < 1 )); then
  echo "--monitor-tail must be at least 1" >&2
  exit 2
fi

cd "${GRI_ROOT}"

git_short="$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
if [[ -z "${LABEL}" ]]; then
  LABEL="after_${git_short}"
fi
if [[ -z "${GATE_TIMEOUT_SECONDS}" ]]; then
  case "${TARGET}" in
    hw_emu) GATE_TIMEOUT_SECONDS=900 ;;
    hw) GATE_TIMEOUT_SECONDS=300 ;;
    sw_emu) GATE_TIMEOUT_SECONDS=180 ;;
  esac
fi

BUILD_ROOT="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_stage0"
RUN_DIR="${BUILD_ROOT}/run_logs"
mkdir -p "${RUN_DIR}"
FLOW_ENV="${RUN_DIR}/target_flow_${LABEL}.env"
READINESS_OUT="${RUN_DIR}/readiness_target_flow_${LABEL}.txt"
MONITOR_OUT="${RUN_DIR}/monitor_after_${LABEL}.txt"
AUDIT_OUT="${GRI_ROOT}/results/pure_pipeline_requirement_audit_${LABEL}"

{
  printf 'target=%s\n' "${TARGET}"
  printf 'label=%s\n' "${LABEL}"
  printf 'wait_idle_seconds=%s\n' "${WAIT_IDLE_SECONDS}"
  printf 'idle_poll_seconds=%s\n' "${IDLE_POLL_SECONDS}"
  printf 'idle_settle_seconds=%s\n' "${IDLE_SETTLE_SECONDS}"
  printf 'monitor_tail_lines=%s\n' "${MONITOR_TAIL_LINES}"
  printf 'gate_case=%s\n' "${GATE_CASE}"
  printf 'gate_timeout_seconds=%s\n' "${GATE_TIMEOUT_SECONDS}"
  printf 'timeout_seconds=%s\n' "${TIMEOUT_SECONDS}"
  printf 'build_host=%s\n' "${BUILD_HOST}"
  printf 'clean_build_artifacts=%s\n' "${CLEAN_BUILD_ARTIFACTS}"
  printf 'readiness_check=%s\n' "${READINESS_CHECK}"
  printf 'strict_readiness=%s\n' "${STRICT_READINESS}"
  printf 'skip_build=%s\n' "${SKIP_BUILD}"
  printf 'skip_finalize=%s\n' "${SKIP_FINALIZE}"
  printf 'skip_audit=%s\n' "${SKIP_AUDIT}"
  printf 'dry_run=%s\n' "${DRY_RUN}"
  printf 'git_head=%s\n' "$(git -C "${GRI_ROOT}" rev-parse HEAD)"
  printf 'readiness_out=%s\n' "${READINESS_OUT}"
  printf 'monitor_out=%s\n' "${MONITOR_OUT}"
  printf 'audit_out=%s\n' "${AUDIT_OUT}"
} > "${FLOW_ENV}"

if [[ "${READINESS_CHECK}" == "1" ]]; then
  readiness_cmd=(
    "${SCRIPT_DIR}/check_pure_pipeline_build_readiness.sh"
    --target "${TARGET}"
    --label "target_flow_${LABEL}"
    --out-file "${READINESS_OUT}"
  )
  if [[ "${STRICT_READINESS}" == "0" ]]; then
    readiness_cmd+=(--allow-active-builders)
  fi
  run_cmd "${readiness_cmd[@]}"
fi

if [[ "${SKIP_BUILD}" == "0" ]]; then
  build_cmd=(
    "${SCRIPT_DIR}/run_pure_pipeline_build.sh"
    --target "${TARGET}"
    --label "${LABEL}"
    --wait-idle "${WAIT_IDLE_SECONDS}"
    --idle-poll "${IDLE_POLL_SECONDS}"
    --idle-settle "${IDLE_SETTLE_SECONDS}"
  )
  if [[ "${CLEAN_BUILD_ARTIFACTS}" == "1" ]]; then
    build_cmd+=(--clean-build-artifacts)
  fi
  run_cmd "${build_cmd[@]}"
fi

run_cmd "${SCRIPT_DIR}/monitor_pure_pipeline_build.sh" \
  --target "${TARGET}" \
  --tail-lines "${MONITOR_TAIL_LINES}" \
  --out-file "${MONITOR_OUT}"

if [[ "${SKIP_FINALIZE}" == "0" ]]; then
  finalize_cmd=(
    "${SCRIPT_DIR}/finalize_pure_pipeline_build.sh"
    --target "${TARGET}"
    --label "${LABEL}"
  )
  if [[ "${BUILD_HOST}" == "1" ]]; then
    finalize_cmd+=(--build-host)
  fi
  if [[ -n "${GATE_CASE}" ]]; then
    finalize_cmd+=(--gate-case "${GATE_CASE}" --gate-timeout "${GATE_TIMEOUT_SECONDS}")
  fi
  if [[ -n "${TIMEOUT_SECONDS}" ]]; then
    finalize_cmd+=(--timeout "${TIMEOUT_SECONDS}")
  fi
  run_cmd "${finalize_cmd[@]}"
fi

if [[ "${SKIP_AUDIT}" == "0" ]]; then
  run_cmd "${SCRIPT_DIR}/audit_pure_pipeline_status.py" \
    --label "${LABEL}" \
    --out-dir "${AUDIT_OUT}"
fi

echo "DONE flow_env=${FLOW_ENV}"
echo "DONE readiness_out=${READINESS_OUT}"
echo "DONE monitor_out=${MONITOR_OUT}"
echo "DONE audit_out=${AUDIT_OUT}"
