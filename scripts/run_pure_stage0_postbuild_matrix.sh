#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw"
MODE="gate"
LABEL=""
HOST="${GRI_ROOT}/.tmp_build/pure_pipeline_host_stage0/pure_pipeline_host"
XCLBIN=""
MANIFEST="${GRI_ROOT}/workloads/sssp_benchmark_pure_stage0/manifest.tsv"
PLAN_DIR=""
OUT_DIR=""
IDENTITY_DIR=""
COMPARE_OUT=""
HOST_SUMMARY=""
SPINE_SUMMARY=""
HOST_IDENTITY=""
BASELINE_LABEL=""
TIMEOUT_SECONDS=600
CASE_TIMEOUTS=""
CASE_FILTER=""
FAMILY_FILTER=""
MAX_CASES=0
SKIP_RUN=0
SKIP_IDENTITY=0
SKIP_COMPARE=0
REQUIRE_COMPARE=0
DRY_RUN=0

GATE_CASES=(
  tiny_chain_v16
  tiny_star_v16_u12
  tiny_spread_v16_u8
  tiny_hotdst_v64_u32
)

usage() {
  cat <<USAGE
Usage: $0 [options]

Run the tracked pure_stage0 workload matrix on an already-built pure-pipeline
xclbin, then audit that the run consumed the canonical manifest inputs.

This script is for post-build evidence collection. It does not build xclbins.

Options:
  --target sw_emu|hw_emu|hw   Target mode. Default: ${TARGET}
  --mode gate|full            gate runs the four required families; full runs all selected cases. Default: ${MODE}
  --label NAME                Result suffix. Default: after_<git short hash>.
  --host PATH                 pure_pipeline_host binary. Default: ${HOST}
  --xclbin PATH               Pure-pipeline xclbin. Default inferred from target.
  --manifest PATH             pure_stage0 manifest. Default: ${MANIFEST}
  --plan-dir PATH             Comparison-plan dir. Default: results/pure_stage0_comparison_plan_<label>
  --out-dir PATH              Pure run dir. Default: results/pure_pipeline_<target>_pure_stage0_<mode>_<label>
  --identity-dir PATH         Identity audit dir. Default: results/pure_pipeline_<target>_pure_stage0_identity_<mode>_<label>
  --compare-out PATH          Comparison dir. Default: results/pure_pipeline_<target>_pure_stage0_compare_<label>
  --host-summary PATH         Host baseline summary for comparison. Default inferred from --baseline-label.
  --spine-summary PATH        Spine summary for comparison. Default inferred from --baseline-label.
  --host-identity PATH        Host baseline input-identity audit. Default inferred from --baseline-label.
  --baseline-label NAME       Baseline result suffix. Default: --label.
  --timeout SECONDS           Per-case timeout. Default: ${TIMEOUT_SECONDS}
  --case-timeout CASE=SECONDS Override timeout for one case. Can be repeated.
  --case LIST                 Run only comma-separated case names. Can be repeated.
  --family LIST               Run only comma-separated families. Can be repeated.
  --max-cases N               Stop after N selected cases. Default: all selected cases.
  --skip-run                  Reuse an existing --out-dir; do not run the xclbin.
  --skip-identity             Do not run the input-identity audit.
  --skip-compare              Do not generate comparison.tsv.
  --require-compare           Fail unless host and Spine baseline summaries exist.
  --dry-run                   Print commands; do not execute them.
  -h, --help                  Show this help.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

append_csv() {
  local old="$1"
  local new="$2"
  if [[ -z "${old}" ]]; then
    printf '%s\n' "${new}"
  else
    printf '%s,%s\n' "${old}" "${new}"
  fi
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

validate_timeout_value() {
  local label="$1"
  local value="$2"
  if ! [[ "${value}" =~ ^[1-9][0-9]*$ ]]; then
    echo "Invalid ${label}: ${value}" >&2
    exit 2
  fi
}

validate_case_timeouts() {
  local entry case_name timeout_value
  local IFS=,
  for entry in ${CASE_TIMEOUTS}; do
    [[ -z "${entry}" ]] && continue
    if [[ "${entry}" != *=* ]]; then
      echo "Invalid --case-timeout entry, expected CASE=SECONDS: ${entry}" >&2
      exit 2
    fi
    case_name="${entry%%=*}"
    timeout_value="${entry#*=}"
    if [[ -z "${case_name}" || -z "${timeout_value}" ]]; then
      echo "Invalid --case-timeout entry, expected CASE=SECONDS: ${entry}" >&2
      exit 2
    fi
    validate_timeout_value "--case-timeout ${case_name}" "${timeout_value}"
  done
}

sha_or_missing() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    sha256sum "${path}" | awk '{print $1}'
  else
    printf 'MISSING'
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --host) HOST="$(abs_path "$2")"; shift 2 ;;
    --xclbin) XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --manifest) MANIFEST="$(abs_path "$2")"; shift 2 ;;
    --plan-dir) PLAN_DIR="$(abs_path "$2")"; shift 2 ;;
    --out-dir) OUT_DIR="$(abs_path "$2")"; shift 2 ;;
    --identity-dir) IDENTITY_DIR="$(abs_path "$2")"; shift 2 ;;
    --compare-out) COMPARE_OUT="$(abs_path "$2")"; shift 2 ;;
    --host-summary) HOST_SUMMARY="$(abs_path "$2")"; shift 2 ;;
    --spine-summary) SPINE_SUMMARY="$(abs_path "$2")"; shift 2 ;;
    --host-identity) HOST_IDENTITY="$(abs_path "$2")"; shift 2 ;;
    --baseline-label) BASELINE_LABEL="$2"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --case-timeout) CASE_TIMEOUTS="$(append_csv "${CASE_TIMEOUTS}" "$2")"; shift 2 ;;
    --case) CASE_FILTER="$(append_csv "${CASE_FILTER}" "$2")"; shift 2 ;;
    --family) FAMILY_FILTER="$(append_csv "${FAMILY_FILTER}" "$2")"; shift 2 ;;
    --max-cases) MAX_CASES="$2"; shift 2 ;;
    --skip-run) SKIP_RUN=1; shift ;;
    --skip-identity) SKIP_IDENTITY=1; shift ;;
    --skip-compare) SKIP_COMPARE=1; shift ;;
    --require-compare) REQUIRE_COMPARE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac
case "${MODE}" in
  gate|full) ;;
  *) echo "Invalid --mode: ${MODE}" >&2; exit 2 ;;
esac
if ! [[ "${MAX_CASES}" =~ ^[0-9]+$ ]]; then
  echo "Invalid --max-cases: ${MAX_CASES}" >&2
  exit 2
fi
validate_timeout_value "--timeout" "${TIMEOUT_SECONDS}"
validate_case_timeouts

cd "${GRI_ROOT}"

if [[ -z "${LABEL}" ]]; then
  LABEL="after_$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
fi
if [[ -z "${BASELINE_LABEL}" ]]; then
  BASELINE_LABEL="${LABEL}"
fi
if [[ -z "${XCLBIN}" ]]; then
  XCLBIN="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_stage0/build/grasu_regraph_pure_pipeline.${TARGET}.xclbin"
fi
if [[ -z "${HOST_SUMMARY}" ]]; then
  HOST_SUMMARY="${GRI_ROOT}/results/grasu_regraph_sssp_pure_stage0_${BASELINE_LABEL}/summary.tsv"
fi
if [[ -z "${SPINE_SUMMARY}" ]]; then
  SPINE_SUMMARY="${GRI_ROOT}/results/spine_edge_file_pure_stage0_${BASELINE_LABEL}/summary.tsv"
fi
if [[ -z "${HOST_IDENTITY}" ]]; then
  HOST_IDENTITY="${GRI_ROOT}/results/grasu_regraph_sssp_pure_stage0_identity_${BASELINE_LABEL}/input_identity_check.tsv"
fi
if [[ -z "${PLAN_DIR}" ]]; then
  PLAN_DIR="${GRI_ROOT}/results/pure_stage0_comparison_plan_${LABEL}"
fi
if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/results/pure_pipeline_${TARGET}_pure_stage0_${MODE}_${LABEL}"
fi
if [[ -z "${IDENTITY_DIR}" ]]; then
  IDENTITY_DIR="${GRI_ROOT}/results/pure_pipeline_${TARGET}_pure_stage0_identity_${MODE}_${LABEL}"
fi
if [[ -z "${COMPARE_OUT}" ]]; then
  COMPARE_OUT="${GRI_ROOT}/results/pure_pipeline_${TARGET}_pure_stage0_compare_${LABEL}"
fi

if [[ "${MODE}" == "gate" && -z "${CASE_FILTER}" ]]; then
  CASE_FILTER="$(IFS=,; printf '%s' "${GATE_CASES[*]}")"
fi

PLAN_ENV="${PLAN_DIR}/run.env"
INPUT_IDENTITY="${PLAN_DIR}/input_identity.tsv"
SUMMARY="${OUT_DIR}/summary.tsv"
RUN_ENV="${OUT_DIR}/run.env"
IDENTITY_OUT="${IDENTITY_DIR}/input_identity_check.tsv"
POSTBUILD_ENV="${OUT_DIR}/postbuild_matrix.env"
STAGE0_ACCEPTANCE_GATES="${COMPARE_OUT}/acceptance_gates_stage0_${MODE}.tsv"
STAGE0_ACCEPTANCE_CHECK="${COMPARE_OUT}/acceptance_check_stage0_${MODE}.tsv"

mkdir -p "${OUT_DIR}" "${IDENTITY_DIR}"
{
  printf 'target=%s\n' "${TARGET}"
  printf 'mode=%s\n' "${MODE}"
  printf 'label=%s\n' "${LABEL}"
  printf 'host=%s\n' "${HOST}"
  printf 'host_sha256=%s\n' "$(sha_or_missing "${HOST}")"
  printf 'xclbin=%s\n' "${XCLBIN}"
  printf 'xclbin_sha256=%s\n' "$(sha_or_missing "${XCLBIN}")"
  printf 'manifest=%s\n' "${MANIFEST}"
  printf 'manifest_sha256=%s\n' "$(sha_or_missing "${MANIFEST}")"
  printf 'plan_dir=%s\n' "${PLAN_DIR}"
  printf 'input_identity=%s\n' "${INPUT_IDENTITY}"
  printf 'out_dir=%s\n' "${OUT_DIR}"
  printf 'summary=%s\n' "${SUMMARY}"
  printf 'run_env=%s\n' "${RUN_ENV}"
  printf 'identity_dir=%s\n' "${IDENTITY_DIR}"
  printf 'identity_out=%s\n' "${IDENTITY_OUT}"
  printf 'compare_out=%s\n' "${COMPARE_OUT}"
  printf 'stage0_acceptance_gates=%s\n' "${STAGE0_ACCEPTANCE_GATES}"
  printf 'stage0_acceptance_check=%s\n' "${STAGE0_ACCEPTANCE_CHECK}"
  printf 'host_summary=%s\n' "${HOST_SUMMARY}"
  printf 'host_summary_sha256=%s\n' "$(sha_or_missing "${HOST_SUMMARY}")"
  printf 'host_identity=%s\n' "${HOST_IDENTITY}"
  printf 'host_identity_sha256=%s\n' "$(sha_or_missing "${HOST_IDENTITY}")"
  printf 'spine_summary=%s\n' "${SPINE_SUMMARY}"
  printf 'spine_summary_sha256=%s\n' "$(sha_or_missing "${SPINE_SUMMARY}")"
  printf 'baseline_label=%s\n' "${BASELINE_LABEL}"
  printf 'timeout_seconds=%s\n' "${TIMEOUT_SECONDS}"
  printf 'case_timeout_overrides=%s\n' "${CASE_TIMEOUTS}"
  printf 'case_filter=%s\n' "${CASE_FILTER}"
  printf 'family_filter=%s\n' "${FAMILY_FILTER}"
  printf 'max_cases=%s\n' "${MAX_CASES}"
  printf 'skip_run=%s\n' "${SKIP_RUN}"
  printf 'skip_identity=%s\n' "${SKIP_IDENTITY}"
  printf 'skip_compare=%s\n' "${SKIP_COMPARE}"
  printf 'require_compare=%s\n' "${REQUIRE_COMPARE}"
  printf 'dry_run=%s\n' "${DRY_RUN}"
  printf 'git_head=%s\n' "$(git -C "${GRI_ROOT}" rev-parse HEAD)"
} > "${POSTBUILD_ENV}"

run_cmd "${SCRIPT_DIR}/export_pure_stage0_comparison_plan.py" \
  --manifest "${MANIFEST}" \
  --label "${LABEL}" \
  --out-dir "${PLAN_DIR}"

if [[ "${SKIP_RUN}" == "0" ]]; then
  smoke_cmd=(
    "${SCRIPT_DIR}/run_pure_pipeline_smoke.sh"
    --target "${TARGET}"
    --host "${HOST}"
    --xclbin "${XCLBIN}"
    --manifest "${MANIFEST}"
    --out-dir "${OUT_DIR}"
    --timeout "${TIMEOUT_SECONDS}"
  )
  if [[ -n "${CASE_TIMEOUTS}" ]]; then
    IFS=',' read -r -a case_timeout_args <<< "${CASE_TIMEOUTS}"
    for case_timeout in "${case_timeout_args[@]}"; do
      smoke_cmd+=(--case-timeout "${case_timeout}")
    done
  fi
  if [[ -n "${CASE_FILTER}" ]]; then
    smoke_cmd+=(--case "${CASE_FILTER}")
  fi
  if [[ -n "${FAMILY_FILTER}" ]]; then
    smoke_cmd+=(--family "${FAMILY_FILTER}")
  fi
  if [[ "${MAX_CASES}" != "0" ]]; then
    smoke_cmd+=(--max-cases "${MAX_CASES}")
  fi
  run_cmd "${smoke_cmd[@]}"
fi

if [[ "${SKIP_IDENTITY}" == "0" ]]; then
  identity_cmd=(
    "${SCRIPT_DIR}/check_pure_stage0_input_identity.py"
    --input-identity "${INPUT_IDENTITY}"
    --run-root "${OUT_DIR}"
    --summary "${SUMMARY}"
    --out-file "${IDENTITY_OUT}"
  )
  if [[ "${MODE}" == "gate" || -n "${CASE_FILTER}" || -n "${FAMILY_FILTER}" || "${MAX_CASES}" != "0" ]]; then
    identity_cmd+=(--allow-subset)
  fi
  run_cmd "${identity_cmd[@]}"
fi

if [[ "${SKIP_COMPARE}" == "0" ]]; then
  missing_compare_inputs=0
  if [[ ! -f "${HOST_SUMMARY}" ]]; then
    echo "Missing host baseline summary: ${HOST_SUMMARY}" >&2
    missing_compare_inputs=1
  fi
  if [[ ! -f "${SPINE_SUMMARY}" ]]; then
    echo "Missing Spine summary: ${SPINE_SUMMARY}" >&2
    if [[ "${REQUIRE_COMPARE}" == "1" ]]; then
      missing_compare_inputs=1
    fi
  fi
  if [[ ! -f "${HOST_IDENTITY}" ]]; then
    echo "Missing host identity audit: ${HOST_IDENTITY}" >&2
    if [[ "${REQUIRE_COMPARE}" == "1" ]]; then
      missing_compare_inputs=1
    fi
  fi
  if [[ "${REQUIRE_COMPARE}" == "1" && "${missing_compare_inputs}" != "0" ]]; then
    echo "Comparison is required. Generate the same-input baseline with:" >&2
    echo "  ${SCRIPT_DIR}/export_pure_stage0_comparison_plan.py --label ${BASELINE_LABEL}" >&2
    echo "then run the host-baseline and Spine commands listed in the generated plan." >&2
    exit 1
  fi
  if [[ ! -f "${HOST_SUMMARY}" ]]; then
    echo "Skipping comparison: host baseline summary is missing." >&2
  else
    compare_cmd=(
      python3 "${SCRIPT_DIR}/summarize_pure_stage0_comparison.py"
      --manifest "${MANIFEST}"
      --input-identity "${INPUT_IDENTITY}"
      --host-summary "${HOST_SUMMARY}"
      --pure-summary "${SUMMARY}"
      --pure-env "${RUN_ENV}"
      --pure-target "${TARGET}"
      --label "${LABEL}"
      --out-dir "${COMPARE_OUT}"
    )
    if [[ -n "${SPINE_SUMMARY}" && -f "${SPINE_SUMMARY}" ]]; then
      compare_cmd+=(--spine-summary "${SPINE_SUMMARY}")
    else
      echo "Comparison will omit Spine columns because the Spine summary is missing." >&2
    fi
    if [[ -n "${HOST_IDENTITY}" && -f "${HOST_IDENTITY}" ]]; then
      compare_cmd+=(--host-identity "${HOST_IDENTITY}")
    else
      echo "Comparison will omit host identity counts because the host identity audit is missing." >&2
    fi
    run_cmd "${compare_cmd[@]}"
    if [[ "${DRY_RUN}" == "0" ]]; then
      mkdir -p "${COMPARE_OUT}"
      {
        printf 'gate\trequired\tevidence_path\tdetail\n'
        printf 'same_input_compare\tyes\t%s\tstage0 comparison covers gate families with PASS status, zero mismatches, and split timing fields\n' \
          "${COMPARE_OUT}/comparison.tsv"
      } > "${STAGE0_ACCEPTANCE_GATES}"
    else
      echo "+ write ${STAGE0_ACCEPTANCE_GATES}"
    fi
    run_cmd "${SCRIPT_DIR}/check_pure_pipeline_acceptance_gates.py" \
      --acceptance-gates "${STAGE0_ACCEPTANCE_GATES}" \
      --mode postrun \
      --out-file "${STAGE0_ACCEPTANCE_CHECK}"
  fi
fi

echo "DONE postbuild_env=${POSTBUILD_ENV}"
echo "DONE plan_env=${PLAN_ENV}"
echo "DONE input_identity=${INPUT_IDENTITY}"
echo "DONE summary=${SUMMARY}"
if [[ "${SKIP_IDENTITY}" == "0" ]]; then
  echo "DONE identity_out=${IDENTITY_OUT}"
else
  echo "DONE identity_out=SKIPPED"
fi
if [[ "${SKIP_COMPARE}" == "0" ]]; then
  echo "DONE compare_out=${COMPARE_OUT}"
  echo "DONE stage0_acceptance_gates=${STAGE0_ACCEPTANCE_GATES}"
  echo "DONE stage0_acceptance_check=${STAGE0_ACCEPTANCE_CHECK}"
else
  echo "DONE compare_out=SKIPPED"
  echo "DONE stage0_acceptance_gates=SKIPPED"
  echo "DONE stage0_acceptance_check=SKIPPED"
fi
