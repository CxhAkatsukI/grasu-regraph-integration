#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

LABEL=""
TARGETS=(hw_emu hw)
ALLOW_ACTIVE_BUILDERS=0
MIN_BUILD_FREE_GB=100
MIN_TMP_FREE_GB=1
AUDIT_DIR=""
BUNDLE_DIR=""

usage() {
  cat <<USAGE
Usage: $0 [options]

Refresh current pure-pipeline build readiness for target modes and export a
compact audit/evidence bundle. This script never starts Vitis.

Options:
  --label NAME                Evidence suffix. Default: refresh_after_<git short hash>.
  --target sw_emu|hw_emu|hw   Add a target to refresh. May be repeated.
                              Default: hw_emu and hw.
  --allow-active-builders     Record active builders as warnings instead of blockers.
  --min-build-free-gb N       Required free GB on build-root filesystem. Default: ${MIN_BUILD_FREE_GB}
  --min-tmp-free-gb N         Required free GB on /tmp. Default: ${MIN_TMP_FREE_GB}
  --audit-dir PATH            Audit output dir. Default: results/pure_pipeline_requirement_audit_<label>
  --bundle-dir PATH           Bundle output dir. Default: results/pure_pipeline_evidence_bundle_<label>
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

run_readiness() {
  local target="$1"
  local cmd=(
    "${SCRIPT_DIR}/check_pure_pipeline_build_readiness.sh"
    --target "${target}"
    --label "${LABEL}"
    --min-build-free-gb "${MIN_BUILD_FREE_GB}"
    --min-tmp-free-gb "${MIN_TMP_FREE_GB}"
  )
  if [[ "${ALLOW_ACTIVE_BUILDERS}" == "1" ]]; then
    cmd+=(--allow-active-builders)
  fi

  print_cmd "${cmd[@]}"
  set +e
  "${cmd[@]}"
  local status=$?
  set -e
  if (( status != 0 )); then
    echo "WARN readiness target=${target} exit=${status}" >&2
  fi
  return "${status}"
}

user_targets=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --label) LABEL="$2"; shift 2 ;;
    --target)
      if (( user_targets == 0 )); then
        TARGETS=()
        user_targets=1
      fi
      TARGETS+=("$2")
      shift 2
      ;;
    --allow-active-builders) ALLOW_ACTIVE_BUILDERS=1; shift ;;
    --min-build-free-gb) MIN_BUILD_FREE_GB="$2"; shift 2 ;;
    --min-tmp-free-gb) MIN_TMP_FREE_GB="$2"; shift 2 ;;
    --audit-dir) AUDIT_DIR="$(abs_path "$2")"; shift 2 ;;
    --bundle-dir) BUNDLE_DIR="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if (( ${#TARGETS[@]} == 0 )); then
  echo "At least one --target is required." >&2
  exit 2
fi

for target in "${TARGETS[@]}"; do
  case "${target}" in
    sw_emu|hw_emu|hw) ;;
    *) echo "Invalid --target: ${target}" >&2; exit 2 ;;
  esac
done
for numeric in MIN_BUILD_FREE_GB MIN_TMP_FREE_GB; do
  value="${!numeric}"
  case "${value}" in
    ''|*[!0-9]*) echo "--${numeric,,} must be a non-negative integer" >&2; exit 2 ;;
  esac
done

cd "${GRI_ROOT}"

git_short="$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
if [[ -z "${LABEL}" ]]; then
  LABEL="refresh_after_${git_short}"
fi
if [[ -z "${AUDIT_DIR}" ]]; then
  AUDIT_DIR="${GRI_ROOT}/results/pure_pipeline_requirement_audit_${LABEL}"
fi
if [[ -z "${BUNDLE_DIR}" ]]; then
  BUNDLE_DIR="${GRI_ROOT}/results/pure_pipeline_evidence_bundle_${LABEL}"
fi

overall_status=0
for target in "${TARGETS[@]}"; do
  if run_readiness "${target}"; then
    :
  else
    status=$?
    if (( overall_status == 0 )); then
      overall_status="${status}"
    fi
  fi
done

audit_cmd=(
  "${SCRIPT_DIR}/audit_pure_pipeline_status.py"
  --label "${LABEL}"
  --out-dir "${AUDIT_DIR}"
)
print_cmd "${audit_cmd[@]}"
"${audit_cmd[@]}"

bundle_cmd=(
  "${SCRIPT_DIR}/export_pure_pipeline_evidence_bundle.py"
  --audit "${AUDIT_DIR}/audit.json"
  --out-dir "${BUNDLE_DIR}"
)
print_cmd "${bundle_cmd[@]}"
"${bundle_cmd[@]}"

echo "DONE label=${LABEL}"
echo "DONE audit_dir=${AUDIT_DIR}"
echo "DONE bundle_dir=${BUNDLE_DIR}"
exit "${overall_status}"
