#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw_emu"
LABEL=""
FLOW_LABEL=""
OUT_DIR=""
WAIT_IDLE_SECONDS=7200
IDLE_POLL_SECONDS=60
IDLE_SETTLE_SECONDS=120
GATE_CASE="tiny_star_v16_u12"
GATE_TIMEOUT_SECONDS=""
MIN_BUILD_FREE_GB=100
MIN_TMP_FREE_GB=1
PREPARE=0
CLEAN_BUILD_ARTIFACTS=1
ALLOW_ACTIVE_BUILDERS=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Create a reproducible launch packet for the GraSU -> ReGraph pure-pipeline
target flow. This script does not start Vitis. It records source-contract
status, build-readiness status, audit/evidence bundle paths, exact launch
command, git hashes, and artifact hashes.

Options:
  --target sw_emu|hw_emu|hw   Target mode. Default: ${TARGET}
  --label NAME                Packet suffix. Default: launch_packet_<target>_after_<git short>.
  --flow-label NAME           Label to use in the generated target-flow command.
                              Default: after_<git short>.
  --out-dir PATH              Packet output dir. Default: .tmp_build/pure_pipeline_launch_packet_<label>
  --wait-idle SECONDS         Generated target-flow wait-idle timeout. Default: ${WAIT_IDLE_SECONDS}
  --idle-poll SECONDS         Generated target-flow idle poll interval. Default: ${IDLE_POLL_SECONDS}
  --idle-settle SECONDS       Generated target-flow idle settle window. Default: ${IDLE_SETTLE_SECONDS}
  --gate-case NAME            Generated target-flow gate case. Default: ${GATE_CASE}
  --no-gate                   Omit the generated target-flow gate case.
  --gate-timeout SECONDS      Generated target-flow gate timeout. Default: target-specific.
  --min-build-free-gb N       Required free GB on build-root filesystem. Default: ${MIN_BUILD_FREE_GB}
  --min-tmp-free-gb N         Required free GB on /tmp. Default: ${MIN_TMP_FREE_GB}
  --prepare                   Regenerate target compile/link/config scripts before checks.
  --no-clean-build-artifacts  Omit --clean-build-artifacts from generated launch command.
  --allow-active-builders     Record active Vitis/Vivado builders as warnings instead of blockers.
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

run_capture_status() {
  print_cmd "$@"
  set +e
  "$@"
  local status=$?
  set -e
  return "${status}"
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

git_value() {
  local root="$1"
  local field="$2"
  if ! git -C "${root}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'not_git'
    return
  fi
  case "${field}" in
    head) git -C "${root}" rev-parse HEAD ;;
    short) git -C "${root}" rev-parse --short HEAD ;;
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --flow-label) FLOW_LABEL="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$(abs_path "$2")"; shift 2 ;;
    --wait-idle) WAIT_IDLE_SECONDS="$2"; shift 2 ;;
    --idle-poll) IDLE_POLL_SECONDS="$2"; shift 2 ;;
    --idle-settle) IDLE_SETTLE_SECONDS="$2"; shift 2 ;;
    --gate-case) GATE_CASE="$2"; shift 2 ;;
    --no-gate) GATE_CASE=""; shift ;;
    --gate-timeout) GATE_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --min-build-free-gb) MIN_BUILD_FREE_GB="$2"; shift 2 ;;
    --min-tmp-free-gb) MIN_TMP_FREE_GB="$2"; shift 2 ;;
    --prepare) PREPARE=1; shift ;;
    --no-clean-build-artifacts) CLEAN_BUILD_ARTIFACTS=0; shift ;;
    --allow-active-builders) ALLOW_ACTIVE_BUILDERS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac
for numeric in WAIT_IDLE_SECONDS IDLE_POLL_SECONDS IDLE_SETTLE_SECONDS MIN_BUILD_FREE_GB MIN_TMP_FREE_GB; do
  value="${!numeric}"
  case "${value}" in
    ''|*[!0-9]*) echo "--${numeric,,} must be a non-negative integer" >&2; exit 2 ;;
  esac
done
if (( IDLE_POLL_SECONDS < 1 )); then
  echo "--idle-poll must be at least 1" >&2
  exit 2
fi

cd "${GRI_ROOT}"

git_short="$(git_value "${GRI_ROOT}" short)"
if [[ -z "${FLOW_LABEL}" ]]; then
  FLOW_LABEL="after_${git_short}"
fi
if [[ -z "${LABEL}" ]]; then
  LABEL="launch_packet_${TARGET}_${FLOW_LABEL}"
fi
if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/.tmp_build/pure_pipeline_launch_packet_${LABEL}"
fi
if [[ -z "${GATE_TIMEOUT_SECONDS}" ]]; then
  case "${TARGET}" in
    hw_emu) GATE_TIMEOUT_SECONDS=900 ;;
    hw) GATE_TIMEOUT_SECONDS=300 ;;
    sw_emu) GATE_TIMEOUT_SECONDS=180 ;;
  esac
fi

mkdir -p "${OUT_DIR}"

BUILD_ROOT="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_stage0"
SOURCE_CONTRACT_OUT="${OUT_DIR}/source_contracts.tsv"
READINESS_OUT="${OUT_DIR}/readiness_${TARGET}.txt"
AUDIT_DIR="${OUT_DIR}/audit"
BUNDLE_DIR="${OUT_DIR}/evidence_bundle"
COMMANDS_SH="${OUT_DIR}/launch_command.sh"
PACKET_ENV="${OUT_DIR}/launch_packet.env"
SUMMARY_MD="${OUT_DIR}/README.md"
HASHES_TSV="${OUT_DIR}/artifact_hashes.tsv"

OUT_XCLBIN="${BUILD_ROOT}/build/grasu_regraph_pure_pipeline.${TARGET}.xclbin"
HOST_BIN="${GRI_ROOT}/.tmp_build/pure_pipeline_host_stage0/pure_pipeline_host"
SW_XCLBIN="${GRI_ROOT}/.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin"

if [[ "${PREPARE}" == "1" ]]; then
  run_capture_status "${SCRIPT_DIR}/prepare_pure_hw_pipeline_build.sh" \
    --target "${TARGET}" \
    --build-root "${BUILD_ROOT}"
fi

source_status=0
if run_capture_status "${SCRIPT_DIR}/check_pure_pipeline_source_contracts.py" \
  --label "${LABEL}" \
  --out-file "${SOURCE_CONTRACT_OUT}"; then
  source_status=0
else
  source_status=$?
fi

readiness_cmd=(
  "${SCRIPT_DIR}/check_pure_pipeline_build_readiness.sh"
  --target "${TARGET}"
  --label "${LABEL}"
  --out-file "${READINESS_OUT}"
  --min-build-free-gb "${MIN_BUILD_FREE_GB}"
  --min-tmp-free-gb "${MIN_TMP_FREE_GB}"
)
if [[ "${ALLOW_ACTIVE_BUILDERS}" == "1" ]]; then
  readiness_cmd+=(--allow-active-builders)
fi
readiness_status=0
if run_capture_status "${readiness_cmd[@]}"; then
  readiness_status=0
else
  readiness_status=$?
fi

audit_status=0
if run_capture_status "${SCRIPT_DIR}/audit_pure_pipeline_status.py" \
  --label "${LABEL}" \
  --out-dir "${AUDIT_DIR}"; then
  audit_status=0
else
  audit_status=$?
fi

bundle_status=0
if [[ -f "${AUDIT_DIR}/audit.json" ]]; then
  if run_capture_status "${SCRIPT_DIR}/export_pure_pipeline_evidence_bundle.py" \
    --audit "${AUDIT_DIR}/audit.json" \
    --out-dir "${BUNDLE_DIR}"; then
    bundle_status=0
  else
    bundle_status=$?
  fi
else
  bundle_status=2
fi

launch_cmd=(
  "./scripts/run_pure_pipeline_target_flow.sh"
  --target "${TARGET}"
  --label "${FLOW_LABEL}"
  --prepare
  --wait-idle "${WAIT_IDLE_SECONDS}"
  --idle-poll "${IDLE_POLL_SECONDS}"
  --idle-settle "${IDLE_SETTLE_SECONDS}"
)
if [[ "${CLEAN_BUILD_ARTIFACTS}" == "1" ]]; then
  launch_cmd+=(--clean-build-artifacts)
fi
if [[ -n "${GATE_CASE}" ]]; then
  launch_cmd+=(--gate-case "${GATE_CASE}" --gate-timeout "${GATE_TIMEOUT_SECONDS}")
else
  launch_cmd+=(--no-gate)
fi

{
  printf '#!/usr/bin/env bash\n'
  printf 'set -euo pipefail\n'
  printf 'cd %q\n' "${GRI_ROOT}"
  printf 'exec'
  printf ' %q' "${launch_cmd[@]}"
  printf '\n'
} > "${COMMANDS_SH}"
chmod +x "${COMMANDS_SH}"

{
  printf 'target=%s\n' "${TARGET}"
  printf 'label=%s\n' "${LABEL}"
  printf 'flow_label=%s\n' "${FLOW_LABEL}"
  printf 'out_dir=%s\n' "${OUT_DIR}"
  printf 'build_root=%s\n' "${BUILD_ROOT}"
  printf 'out_xclbin=%s\n' "${OUT_XCLBIN}"
  printf 'source_contract_out=%s\n' "${SOURCE_CONTRACT_OUT}"
  printf 'source_contract_status=%s\n' "${source_status}"
  printf 'readiness_out=%s\n' "${READINESS_OUT}"
  printf 'readiness_status=%s\n' "${readiness_status}"
  printf 'audit_dir=%s\n' "${AUDIT_DIR}"
  printf 'audit_status=%s\n' "${audit_status}"
  printf 'bundle_dir=%s\n' "${BUNDLE_DIR}"
  printf 'bundle_status=%s\n' "${bundle_status}"
  printf 'launch_command=%s\n' "${COMMANDS_SH}"
  printf 'integration_branch=%s\n' "$(git_value "${GRI_ROOT}" branch)"
  printf 'integration_head=%s\n' "$(git_value "${GRI_ROOT}" head)"
  printf 'integration_tracked_dirty=%s\n' "$(git_value "${GRI_ROOT}" tracked_dirty)"
  printf 'grasu_head=%s\n' "$(git_value "${GRASU_ROOT}" head)"
  printf 'grasu_tracked_dirty=%s\n' "$(git_value "${GRASU_ROOT}" tracked_dirty)"
  printf 'regraph_head=%s\n' "$(git_value "${REGRAPH_ROOT}" head)"
  printf 'regraph_tracked_dirty=%s\n' "$(git_value "${REGRAPH_ROOT}" tracked_dirty)"
} > "${PACKET_ENV}"

{
  printf 'role\tpath\tsha256\tsize_bytes\n'
  for artifact in \
    "${SW_XCLBIN}" \
    "${OUT_XCLBIN}" \
    "${HOST_BIN}" \
    "${BUILD_ROOT}/manifest.env" \
    "${BUILD_ROOT}/compile_commands.sh" \
    "${BUILD_ROOT}/link_command.sh" \
    "${SOURCE_CONTRACT_OUT}" \
    "${READINESS_OUT}" \
    "${AUDIT_DIR}/audit.json" \
    "${AUDIT_DIR}/audit.md" \
    "${BUNDLE_DIR}/summary.md" \
    "${BUNDLE_DIR}/bundle_manifest.json" \
    "${BUNDLE_DIR}/target_matrix.tsv" \
    "${COMMANDS_SH}" \
    "${PACKET_ENV}"; do
    printf 'artifact\t%s\t%s\t%s\n' "${artifact}" "$(sha_or_missing "${artifact}")" "$(size_or_missing "${artifact}")"
  done
} > "${HASHES_TSV}"

launch_line="$(printf '%q ' "${launch_cmd[@]}")"
{
  printf '# Pure Pipeline Launch Packet\n\n'
  printf 'Generated: `%s`\n\n' "$(date -Is)"
  printf 'Target: `%s`\n\n' "${TARGET}"
  printf 'Flow label: `%s`\n\n' "${FLOW_LABEL}"
  printf 'Integration commit: `%s`\n\n' "$(git_value "${GRI_ROOT}" head)"
  printf 'Source-contract exit: `%s`\n\n' "${source_status}"
  printf 'Readiness exit: `%s`\n\n' "${readiness_status}"
  printf 'Audit exit: `%s`\n\n' "${audit_status}"
  printf 'Bundle exit: `%s`\n\n' "${bundle_status}"
  printf '## Launch Command\n\n'
  printf '```bash\n'
  printf 'cd %s\n' "${GRI_ROOT}"
  printf '%s\n' "${launch_line% }"
  printf '```\n\n'
  printf 'Equivalent executable command file:\n\n'
  printf '```text\n%s\n```\n\n' "${COMMANDS_SH}"
  printf '## Evidence Files\n\n'
  printf '```text\n'
  printf '%s\n' "${SOURCE_CONTRACT_OUT}"
  printf '%s\n' "${READINESS_OUT}"
  printf '%s\n' "${AUDIT_DIR}/audit.json"
  printf '%s\n' "${BUNDLE_DIR}/summary.md"
  printf '%s\n' "${HASHES_TSV}"
  printf '```\n\n'
  printf '## Current XCLBIN State\n\n'
  printf '```text\n'
  printf 'sw_emu %s %s bytes %s\n' "$(sha_or_missing "${SW_XCLBIN}")" "$(size_or_missing "${SW_XCLBIN}")" "${SW_XCLBIN}"
  printf '%s %s %s bytes %s\n' "${TARGET}" "$(sha_or_missing "${OUT_XCLBIN}")" "$(size_or_missing "${OUT_XCLBIN}")" "${OUT_XCLBIN}"
  printf '```\n\n'
  printf 'If readiness is nonzero, inspect `readiness_%s.txt` before launching. A common expected blocker is an unrelated active Vitis/Vivado build.\n' "${TARGET}"
} > "${SUMMARY_MD}"

echo "DONE launch_packet=${OUT_DIR}"
echo "DONE launch_command=${COMMANDS_SH}"
echo "DONE source_contract_out=${SOURCE_CONTRACT_OUT}"
echo "DONE readiness_out=${READINESS_OUT}"
echo "DONE audit_dir=${AUDIT_DIR}"
echo "DONE bundle_dir=${BUNDLE_DIR}"

if (( source_status != 0 )); then
  exit "${source_status}"
fi
if (( readiness_status != 0 )); then
  exit "${readiness_status}"
fi
if (( audit_status != 0 )); then
  exit "${audit_status}"
fi
exit "${bundle_status}"
