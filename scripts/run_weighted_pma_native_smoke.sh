#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="sw_emu"
HOST="${GRI_ROOT}/.tmp_build/weighted_pma_native_host/weighted_pma_native_host"
XCLBIN=""
GRAPH="${GRI_ROOT}/workloads/weighted_pma_native_tiny/weighted_pma_native_tiny.graph"
OUT_DIR=""
SOURCE_EXTERNAL=0
SUPERSTEPS=4
TIMEOUT_SECONDS=120
PLATFORM_XPFM="/opt/xilinx/platforms/xilinx_u55c_gen3x16_xdma_3_202210_1/xilinx_u55c_gen3x16_xdma_3_202210_1.xpfm"
VITIS_SETTINGS="/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
EMCONFIG_PATH=""
GIT_HEAD_AT_START="$(git -C "${GRI_ROOT}" rev-parse HEAD)"
GIT_DIRTY_AT_START="$([[ -n "$(git -C "${GRI_ROOT}" status --short)" ]] && echo 1 || echo 0)"

usage() {
  cat <<USAGE
Usage: $0 --xclbin PATH [options]

Run the weighted PMA-native GraSU -> ReGraph correctness smoke.

Options:
  --target TARGET          sw_emu, hw_emu, or hw. Default: ${TARGET}
  --host PATH              Host binary. Default: ${HOST}
  --xclbin PATH            Matching weighted-axis xclbin. Required.
  --graph PATH             Weighted graph/update input. Default: ${GRAPH}
  --out-dir PATH           Evidence output directory.
  --source N               External source vertex. Default: ${SOURCE_EXTERNAL}
  --supersteps N           Synchronous SSSP rounds. Default: ${SUPERSTEPS}
  --timeout SECONDS        Watchdog. Default: ${TIMEOUT_SECONDS}
  --platform-xpfm PATH     Platform for emconfigutil.
  --vitis-settings PATH    Vitis settings64.sh.
  --emconfig-path PATH     Existing/generated emconfig directory.
  -h, --help               Show this help.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --host) HOST="$(abs_path "$2")"; shift 2 ;;
    --xclbin) XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --graph) GRAPH="$(abs_path "$2")"; shift 2 ;;
    --out-dir) OUT_DIR="$(abs_path "$2")"; shift 2 ;;
    --source) SOURCE_EXTERNAL="$2"; shift 2 ;;
    --supersteps) SUPERSTEPS="$2"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --platform-xpfm) PLATFORM_XPFM="$(abs_path "$2")"; shift 2 ;;
    --vitis-settings) VITIS_SETTINGS="$(abs_path "$2")"; shift 2 ;;
    --emconfig-path) EMCONFIG_PATH="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac
if [[ -z "${XCLBIN}" ]]; then
  echo "--xclbin is required" >&2
  exit 2
fi
for numeric in SOURCE_EXTERNAL SUPERSTEPS TIMEOUT_SECONDS; do
  value="${!numeric}"
  if ! [[ "${value}" =~ ^[0-9]+$ ]]; then
    echo "Invalid numeric ${numeric}=${value}" >&2
    exit 2
  fi
done
if [[ "${SUPERSTEPS}" == 0 || "${TIMEOUT_SECONDS}" == 0 ]]; then
  echo "--supersteps and --timeout must be greater than zero" >&2
  exit 2
fi
if [[ ! -x "${HOST}" ]]; then
  echo "Missing executable host: ${HOST}" >&2
  exit 1
fi
if [[ ! -f "${XCLBIN}" ]]; then
  echo "Missing xclbin: ${XCLBIN}" >&2
  exit 1
fi
if [[ ! -f "${GRAPH}" ]]; then
  echo "Missing graph: ${GRAPH}" >&2
  exit 1
fi
if [[ ! -f "${VITIS_SETTINGS}" ]]; then
  echo "Missing Vitis settings: ${VITIS_SETTINGS}" >&2
  exit 1
fi
if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/results/weighted_pma_native_${TARGET}_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "${OUT_DIR}"

# shellcheck disable=SC1090
source "${VITIS_SETTINGS}"
export XILINX_XRT="${XILINX_XRT:-/opt/xilinx/xrt}"
export LD_LIBRARY_PATH="${XILINX_XRT}/lib:${LD_LIBRARY_PATH:-}"
export PATH="${XILINX_XRT}/bin:${PATH}"
if [[ "${TARGET}" != "hw" ]]; then
  export XCL_EMULATION_MODE="${TARGET}"
  if [[ -z "${EMCONFIG_PATH}" ]]; then
    EMCONFIG_PATH="${OUT_DIR}/emconfig"
  fi
  mkdir -p "${EMCONFIG_PATH}"
  if [[ ! -f "${EMCONFIG_PATH}/emconfig.json" ]]; then
    emconfigutil --platform "${PLATFORM_XPFM}" --od "${EMCONFIG_PATH}"
  fi
  export EMCONFIG_PATH
else
  unset XCL_EMULATION_MODE || true
fi

RUN_LOG="${OUT_DIR}/run.log"
RESULT_FILE="${OUT_DIR}/result.txt"
RUN_ENV="${OUT_DIR}/run.env"
SUMMARY="${OUT_DIR}/summary.tsv"

set +e
timeout --signal=TERM --kill-after=15s "${TIMEOUT_SECONDS}s" \
  "${HOST}" "${XCLBIN}" "${GRAPH}" "${RESULT_FILE}" \
  "${SOURCE_EXTERNAL}" "${SUPERSTEPS}" 2>&1 | tee "${RUN_LOG}"
host_exit=${PIPESTATUS[0]}
set -e

result_count="$(rg -c '^WEIGHTED_PMA_NATIVE_RESULT ' "${RUN_LOG}" || true)"
result_line="$(rg '^WEIGHTED_PMA_NATIVE_RESULT ' "${RUN_LOG}" | tail -n 1 || true)"
timing_line="$(rg '^WEIGHTED_PMA_NATIVE_TIMING ' "${RUN_LOG}" | tail -n 1 || true)"
bitsize_warnings="$(rg -c 'Bitsize mismatch|Bitsize mismach' "${RUN_LOG}" || true)"

build_root="$(dirname "$(dirname "${XCLBIN}")")"
BUILD_METADATA_DIR="${OUT_DIR}/build_metadata"
mkdir -p "${BUILD_METADATA_DIR}"
BUILD_METADATA_INDEX="${BUILD_METADATA_DIR}/files.tsv"
printf 'role\tsha256\tbytes\toriginal_path\tcopy\n' >"${BUILD_METADATA_INDEX}"

copy_build_metadata() {
  local role="$1"
  local source_path="$2"
  local copy_name="$3"
  if [[ ! -f "${source_path}" ]]; then
    return
  fi
  cp "${source_path}" "${BUILD_METADATA_DIR}/${copy_name}"
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "${role}" \
    "$(sha256sum "${source_path}" | awk '{print $1}')" \
    "$(stat --printf '%s' "${source_path}")" \
    "${source_path}" \
    "build_metadata/${copy_name}" >>"${BUILD_METADATA_INDEX}"
}

for build_input in manifest.env inputs.tsv compile_commands.sh link_command.sh; do
  copy_build_metadata build_input "${build_root}/${build_input}" "${build_input}"
done
if [[ -d "${build_root}/logs" ]]; then
  while IFS= read -r -d '' steps_log; do
    parent="$(basename "$(dirname "${steps_log}")")"
    copy_build_metadata build_steps "${steps_log}" \
      "${parent}_$(basename "${steps_log}")"
  done < <(find "${build_root}/logs" -type f -name '*.steps.log' -print0 | sort -z)
fi

status="FAIL"
if [[ "${host_exit}" == 0 && "${result_count}" == 1 &&
      "${result_line}" == *"status=PASS"* &&
      "${result_line}" == *"mismatches=0"* &&
      "${result_line}" == *"conversion_cost=absent"* ]]; then
  status="PASS"
fi

{
  printf 'STATUS=%s\n' "${status}"
  printf 'CLAIM_CLASS=whole_system_%s_correctness\n' "${TARGET}"
  printf 'PERFORMANCE_CLAIM_ALLOWED=%s\n' "$([[ "${TARGET}" == hw ]] && echo 1 || echo 0)"
  printf 'TARGET=%s\n' "${TARGET}"
  printf 'PIPELINE_MODE=weighted-axis\n'
  printf 'CONVERSION_COST=absent\n'
  printf 'HOST_EXIT=%s\n' "${host_exit}"
  printf 'RESULT_LINE_COUNT=%s\n' "${result_count}"
  printf 'BITSIZE_WARNINGS=%s\n' "${bitsize_warnings}"
  printf 'SOURCE_EXTERNAL=%s\n' "${SOURCE_EXTERNAL}"
  printf 'SUPERSTEPS=%s\n' "${SUPERSTEPS}"
  printf 'TIMEOUT_SECONDS=%s\n' "${TIMEOUT_SECONDS}"
  printf 'HOST=%s\n' "${HOST}"
  printf 'XCLBIN=%s\n' "${XCLBIN}"
  printf 'GRAPH=%s\n' "${GRAPH}"
  printf 'GIT_HEAD_AT_START=%s\n' "${GIT_HEAD_AT_START}"
  printf 'GIT_DIRTY_AT_START=%s\n' "${GIT_DIRTY_AT_START}"
  printf 'HOST_SHA256=%s\n' "$(sha256sum "${HOST}" | awk '{print $1}')"
  printf 'XCLBIN_SHA256=%s\n' "$(sha256sum "${XCLBIN}" | awk '{print $1}')"
  printf 'GRAPH_SHA256=%s\n' "$(sha256sum "${GRAPH}" | awk '{print $1}')"
  printf 'RUN_LOG_SHA256=%s\n' "$(sha256sum "${RUN_LOG}" | awk '{print $1}')"
  for build_input in manifest.env inputs.tsv compile_commands.sh link_command.sh; do
    if [[ -f "${build_root}/${build_input}" ]]; then
      key="$(printf '%s' "${build_input}" | tr '[:lower:].' '[:upper:]_')"
      printf 'BUILD_%s=%s\n' "${key}" "${build_root}/${build_input}"
      printf 'BUILD_%s_SHA256=%s\n' "${key}" \
        "$(sha256sum "${build_root}/${build_input}" | awk '{print $1}')"
    fi
  done
  if [[ -f "${RESULT_FILE}" ]]; then
    printf 'RESULT_SHA256=%s\n' "$(sha256sum "${RESULT_FILE}" | awk '{print $1}')"
  fi
  printf 'RESULT_LINE=%s\n' "${result_line}"
  printf 'TIMING_LINE=%s\n' "${timing_line}"
} >"${RUN_ENV}"

printf 'target\tstatus\thost_exit\tresult_count\tbitsize_warnings\tresult_line\ttiming_line\n' >"${SUMMARY}"
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
  "${TARGET}" "${status}" "${host_exit}" "${result_count}" \
  "${bitsize_warnings}" "${result_line}" "${timing_line}" >>"${SUMMARY}"

(
  cd "${OUT_DIR}"
  find . -type f ! -name evidence.sha256 -print0 | sort -z |
    xargs -0 sha256sum
) >"${OUT_DIR}/evidence.sha256"

printf 'WEIGHTED_PMA_NATIVE_SMOKE status=%s target=%s evidence=%s\n' \
  "${status}" "${TARGET}" "${OUT_DIR}"
[[ "${status}" == PASS ]]
