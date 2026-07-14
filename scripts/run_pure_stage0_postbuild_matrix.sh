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
TIMEOUT_SECONDS=600
CASE_FILTER=""
FAMILY_FILTER=""
MAX_CASES=0
SKIP_RUN=0
SKIP_IDENTITY=0
SKIP_COMPARE=0
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
  --host-summary PATH         Host baseline summary for comparison. Optional.
  --spine-summary PATH        Spine summary for comparison. Optional.
  --timeout SECONDS           Per-case timeout. Default: ${TIMEOUT_SECONDS}
  --case LIST                 Run only comma-separated case names. Can be repeated.
  --family LIST               Run only comma-separated families. Can be repeated.
  --max-cases N               Stop after N selected cases. Default: all selected cases.
  --skip-run                  Reuse an existing --out-dir; do not run the xclbin.
  --skip-identity             Do not run the input-identity audit.
  --skip-compare              Do not generate comparison.tsv.
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
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --case) CASE_FILTER="$(append_csv "${CASE_FILTER}" "$2")"; shift 2 ;;
    --family) FAMILY_FILTER="$(append_csv "${FAMILY_FILTER}" "$2")"; shift 2 ;;
    --max-cases) MAX_CASES="$2"; shift 2 ;;
    --skip-run) SKIP_RUN=1; shift ;;
    --skip-identity) SKIP_IDENTITY=1; shift ;;
    --skip-compare) SKIP_COMPARE=1; shift ;;
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

cd "${GRI_ROOT}"

if [[ -z "${LABEL}" ]]; then
  LABEL="after_$(git -C "${GRI_ROOT}" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d_%H%M%S)"
fi
if [[ -z "${XCLBIN}" ]]; then
  XCLBIN="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_stage0/build/grasu_regraph_pure_pipeline.${TARGET}.xclbin"
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
  printf 'host_summary=%s\n' "${HOST_SUMMARY}"
  printf 'spine_summary=%s\n' "${SPINE_SUMMARY}"
  printf 'timeout_seconds=%s\n' "${TIMEOUT_SECONDS}"
  printf 'case_filter=%s\n' "${CASE_FILTER}"
  printf 'family_filter=%s\n' "${FAMILY_FILTER}"
  printf 'max_cases=%s\n' "${MAX_CASES}"
  printf 'skip_run=%s\n' "${SKIP_RUN}"
  printf 'skip_identity=%s\n' "${SKIP_IDENTITY}"
  printf 'skip_compare=%s\n' "${SKIP_COMPARE}"
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
  if [[ -z "${HOST_SUMMARY}" || ! -f "${HOST_SUMMARY}" ]]; then
    echo "Skipping comparison: missing --host-summary" >&2
  else
    compare_cmd=(
      python3 "${SCRIPT_DIR}/summarize_pure_pipeline_smoke.py"
      --host-summary "${HOST_SUMMARY}"
      --pure-summary "${SUMMARY}"
      --pure-env "${RUN_ENV}"
      --pure-target "${TARGET}"
      --out-dir "${COMPARE_OUT}"
    )
    if [[ -n "${SPINE_SUMMARY}" && -f "${SPINE_SUMMARY}" ]]; then
      compare_cmd+=(--spine-summary "${SPINE_SUMMARY}")
    fi
    run_cmd "${compare_cmd[@]}"
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
else
  echo "DONE compare_out=SKIPPED"
fi
