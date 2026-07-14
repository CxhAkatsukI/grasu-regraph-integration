#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="sw_emu"
HOST="${GRI_ROOT}/.tmp_build/pure_pipeline_host_stage0/pure_pipeline_host"
XCLBIN=""
OUT_DIR=""
MANIFEST="${GRI_ROOT}/workloads/sssp_benchmark_smoke/manifest.tsv"
TIMEOUT_SECONDS=600
VITIS_SETTINGS="/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
PLATFORM_XPFM="/opt/xilinx/platforms/xilinx_u55c_gen3x16_xdma_3_202210_1/xilinx_u55c_gen3x16_xdma_3_202210_1.xpfm"
EMCONFIG_PATH=""
CASE_FILTER=""
FAMILY_FILTER=""
MAX_CASES=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Run the GraSU -> ReGraph pure-pipeline host over the smoke manifest.

Options:
  --target sw_emu|hw_emu|hw   Target mode. Default: ${TARGET}
  --host PATH                 pure_pipeline_host binary. Default: ${HOST}
  --xclbin PATH               Pure-pipeline xclbin. Default inferred from target.
  --manifest PATH             Smoke manifest TSV. Default: ${MANIFEST}
  --out-dir PATH              Output directory. Default: results/pure_pipeline_<target>_smoke_<timestamp>
  --timeout SECONDS           Per-case timeout. Default: ${TIMEOUT_SECONDS}
  --case LIST                 Run only comma-separated case names. Can be repeated.
  --family LIST               Run only comma-separated families. Can be repeated.
  --max-cases N               Stop after N selected cases. Default: all selected cases.
  --emconfig-path PATH        EMCONFIG_PATH for sw_emu/hw_emu. Default inferred.
  --platform-xpfm PATH        Platform path for emconfigutil. Default: ${PLATFORM_XPFM}
  --vitis-settings PATH       Vitis settings64.sh. Default: ${VITIS_SETTINGS}
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

csv_contains_or_empty() {
  local list="$1"
  local value="$2"
  [[ -z "${list}" || ",${list}," == *",${value},"* ]]
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --host) HOST="$(abs_path "$2")"; shift 2 ;;
    --xclbin) XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --manifest) MANIFEST="$(abs_path "$2")"; shift 2 ;;
    --out-dir) OUT_DIR="$(abs_path "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --case) CASE_FILTER="$(append_csv "${CASE_FILTER}" "$2")"; shift 2 ;;
    --family) FAMILY_FILTER="$(append_csv "${FAMILY_FILTER}" "$2")"; shift 2 ;;
    --max-cases) MAX_CASES="$2"; shift 2 ;;
    --emconfig-path) EMCONFIG_PATH="$(abs_path "$2")"; shift 2 ;;
    --platform-xpfm) PLATFORM_XPFM="$(abs_path "$2")"; shift 2 ;;
    --vitis-settings) VITIS_SETTINGS="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

if [[ -z "${XCLBIN}" ]]; then
  case "${TARGET}" in
    sw_emu)
      XCLBIN="${GRI_ROOT}/.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin"
      ;;
    hw_emu)
      XCLBIN="${GRI_ROOT}/.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin"
      ;;
    hw)
      XCLBIN="${GRI_ROOT}/.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin"
      ;;
  esac
fi

if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/results/pure_pipeline_${TARGET}_smoke_$(date +%Y%m%d_%H%M%S)"
fi

cd "${GRI_ROOT}"

if [[ ! -x "${HOST}" ]]; then
  echo "Missing executable host runner: ${HOST}" >&2
  exit 1
fi
if [[ ! -f "${XCLBIN}" ]]; then
  echo "Missing xclbin: ${XCLBIN}" >&2
  exit 1
fi
if [[ ! -f "${MANIFEST}" ]]; then
  echo "Missing manifest: ${MANIFEST}" >&2
  exit 1
fi
if [[ ! -f "${VITIS_SETTINGS}" ]]; then
  echo "Missing Vitis settings: ${VITIS_SETTINGS}" >&2
  exit 1
fi
if ! [[ "${MAX_CASES}" =~ ^[0-9]+$ ]]; then
  echo "Invalid --max-cases: ${MAX_CASES}" >&2
  exit 2
fi

mkdir -p "${OUT_DIR}"
SUMMARY="${OUT_DIR}/summary.tsv"
ENV_FILE="${OUT_DIR}/run.env"

# shellcheck disable=SC1090
source "${VITIS_SETTINGS}"
export XILINX_XRT="${XILINX_XRT:-/opt/xilinx/xrt}"
export LD_LIBRARY_PATH="${XILINX_XRT}/lib:${LD_LIBRARY_PATH:-}"
export PATH="${XILINX_XRT}/bin:${PATH}"

if [[ "${TARGET}" != "hw" ]]; then
  export XCL_EMULATION_MODE="${TARGET}"
  if [[ -z "${EMCONFIG_PATH}" ]]; then
    EMCONFIG_PATH="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_stage0/run"
  fi
  mkdir -p "${EMCONFIG_PATH}"
  if [[ ! -f "${EMCONFIG_PATH}/emconfig.json" ]]; then
    emconfigutil --platform "${PLATFORM_XPFM}" --od "${EMCONFIG_PATH}"
  fi
  export EMCONFIG_PATH
else
  unset XCL_EMULATION_MODE || true
fi

{
  printf 'target=%s\n' "${TARGET}"
  printf 'host=%s\n' "${HOST}"
  printf 'xclbin=%s\n' "${XCLBIN}"
  printf 'manifest=%s\n' "${MANIFEST}"
  printf 'out_dir=%s\n' "${OUT_DIR}"
  printf 'timeout_seconds=%s\n' "${TIMEOUT_SECONDS}"
  printf 'case_filter=%s\n' "${CASE_FILTER}"
  printf 'family_filter=%s\n' "${FAMILY_FILTER}"
  printf 'max_cases=%s\n' "${MAX_CASES}"
  printf 'xcl_emulation_mode=%s\n' "${XCL_EMULATION_MODE:-}"
  printf 'emconfig_path=%s\n' "${EMCONFIG_PATH:-}"
  printf 'host_sha256='
  sha256sum "${HOST}" | awk '{print $1}'
  printf 'xclbin_sha256='
  sha256sum "${XCLBIN}" | awk '{print $1}'
  printf 'git_head='
  git -C "${GRI_ROOT}" rev-parse HEAD
} > "${ENV_FILE}"

printf 'case\tfamily\tvertices\tupdates\tfinal_edges\tsource\tsupersteps\texit_code\tstatus\tlog\tresult_line\ttiming_line\n' > "${SUMMARY}"

failures=0
selected=0
while IFS=$'\t' read -r case family vertices static_edges updates final_edges source supersteps weight graph result regraph_edges expected metadata; do
  if [[ "${case}" == "case" ]]; then
    continue
  fi
  if ! csv_contains_or_empty "${CASE_FILTER}" "${case}"; then
    continue
  fi
  if ! csv_contains_or_empty "${FAMILY_FILTER}" "${family}"; then
    continue
  fi
  if [[ "${MAX_CASES}" != "0" && "${selected}" -ge "${MAX_CASES}" ]]; then
    continue
  fi
  selected=$((selected + 1))

  log="${OUT_DIR}/${case}.log"
  echo "running ${case} (${family}) source=${source} supersteps=${supersteps}"
  set +e
  timeout "${TIMEOUT_SECONDS}s" "${HOST}" "${XCLBIN}" "${graph}" "${result}" "${source}" "${supersteps}" \
    2>&1 | tee "${log}"
  rc=${PIPESTATUS[0]}
  set -e

  result_line="$(grep 'PURE_PIPELINE_RESULT' "${log}" | tail -n 1 || true)"
  timing_line="$(grep 'PURE_PIPELINE_TIMING' "${log}" | tail -n 1 || true)"
  status="FAIL"
  if [[ ${rc} -eq 0 && "${result_line}" == *"status=PASS"* ]]; then
    status="PASS"
  else
    failures=$((failures + 1))
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${case}" "${family}" "${vertices}" "${updates}" "${final_edges}" \
    "${source}" "${supersteps}" "${rc}" "${status}" "${log}" \
    "${result_line//$'\t'/ }" "${timing_line//$'\t'/ }" >> "${SUMMARY}"
done < "${MANIFEST}"

if [[ "${selected}" -eq 0 ]]; then
  echo "pure pipeline smoke selected no cases" >&2
  exit 1
fi

echo "summary: ${SUMMARY}"
if [[ ${failures} -ne 0 ]]; then
  echo "pure pipeline smoke failures: ${failures}" >&2
  exit 1
fi

echo "pure pipeline smoke passed"
