#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

CASE="tiny_spread_v16_u8"
VERTICES=16
UPDATES=8
SHAPE="spread"
WORK_DIR="${GRI_ROOT}/workloads/generated/${CASE}"
RESULT_DIR="${GRI_ROOT}/results/${CASE}_$(date +%Y%m%d_%H%M%S)"
GRAPH_FILE=""
RESULT_FILE=""
REGRAPH_NUM_DENSE=1
RESULT_BASE=16
DRY_RUN=0
SKIP_GRASU=0
SKIP_REGRAPH=0

GRASU_HOST="${GRASU_HOST:-${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/GraSU_host_u55c}"
GRASU_XCLBIN="${GRASU_XCLBIN:-${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/build/GraSU_u55c_hbm.hw.xclbin}"
REGRAPH_HOST="${REGRAPH_HOST:-${REGRAPH_ROOT}/host_graph_fpga_pr_baseline}"
REGRAPH_XCLBIN="${REGRAPH_XCLBIN:-${REGRAPH_ROOT}/xclbin_hw_pr_baseline/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin}"

usage() {
  cat <<USAGE
Usage: $0 [options]

Options:
  --case NAME              Case name for generated workload.
  --vertices N             Generated workload vertex count. Default: ${VERTICES}
  --updates N              Generated workload update count. Default: ${UPDATES}
  --shape NAME             spread | hot | delete-even. Default: ${SHAPE}
  --graph PATH             Existing GraSU graph input. Requires --result.
  --result PATH            Existing GraSU final-result file. Requires --graph.
  --work-dir PATH          Generated workload directory.
  --result-dir PATH        Output directory for logs and converted graph.
  --regraph-num-dense N    ReGraph numD argument. Default: ${REGRAPH_NUM_DENSE}
  --result-base BASE       GraSU result ID base: 10 | 16 | auto. Default: ${RESULT_BASE}
  --skip-grasu             Do not run GraSU; only convert and run ReGraph.
  --skip-regraph           Do not run ReGraph; stop after GraSU and conversion.
  --dry-run                Print commands without executing hardware runs.
  -h, --help               Show this help.
USAGE
}

run_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [[ "${DRY_RUN}" == "0" ]]; then
    "$@"
  fi
}

run_local_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  "$@"
}

abs_under_root() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${GRI_ROOT}" "$1" ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --case) CASE="$2"; shift 2 ;;
    --vertices) VERTICES="$2"; shift 2 ;;
    --updates) UPDATES="$2"; shift 2 ;;
    --shape) SHAPE="$2"; shift 2 ;;
    --graph) GRAPH_FILE="$2"; shift 2 ;;
    --result) RESULT_FILE="$2"; shift 2 ;;
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --result-dir) RESULT_DIR="$2"; shift 2 ;;
    --regraph-num-dense) REGRAPH_NUM_DENSE="$2"; shift 2 ;;
    --result-base) RESULT_BASE="$2"; shift 2 ;;
    --skip-grasu) SKIP_GRASU=1; shift ;;
    --skip-regraph) SKIP_REGRAPH=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

WORK_DIR="$(abs_under_root "${WORK_DIR}")"
RESULT_DIR="$(abs_under_root "${RESULT_DIR}")"
if [[ -n "${GRAPH_FILE}" ]]; then
  GRAPH_FILE="$(abs_under_root "${GRAPH_FILE}")"
fi
if [[ -n "${RESULT_FILE}" ]]; then
  RESULT_FILE="$(abs_under_root "${RESULT_FILE}")"
fi

mkdir -p "${RESULT_DIR}"

if [[ -z "${GRAPH_FILE}" || -z "${RESULT_FILE}" ]]; then
  WORK_DIR="${WORK_DIR%/}"
  mkdir -p "${WORK_DIR}"
  run_local_cmd "${SCRIPT_DIR}/generate_grasu_workload.py" \
    --out-dir "${WORK_DIR}" \
    --case "${CASE}" \
    --vertices "${VERTICES}" \
    --updates "${UPDATES}" \
    --shape "${SHAPE}" | tee "${RESULT_DIR}/generate.log"
  GRAPH_FILE="${WORK_DIR}/${CASE}.graph"
  RESULT_FILE="${WORK_DIR}/${CASE}.result"
fi

REGRAPH_GRAPH="${RESULT_DIR}/${CASE}.regraph.edges"

{
  echo "case=${CASE}"
  echo "graph=${GRAPH_FILE}"
  echo "result=${RESULT_FILE}"
  echo "regraph_graph=${REGRAPH_GRAPH}"
  echo "grasu_host=${GRASU_HOST}"
  echo "grasu_xclbin=${GRASU_XCLBIN}"
  echo "regraph_host=${REGRAPH_HOST}"
  echo "regraph_xclbin=${REGRAPH_XCLBIN}"
  echo "regraph_num_dense=${REGRAPH_NUM_DENSE}"
  echo "result_base=${RESULT_BASE}"
} > "${RESULT_DIR}/manifest.env"

for required in "${GRAPH_FILE}" "${RESULT_FILE}" "${GRASU_HOST}" "${GRASU_XCLBIN}" "${REGRAPH_HOST}" "${REGRAPH_XCLBIN}"; do
  if [[ ! -e "${required}" ]]; then
    echo "Missing required path: ${required}" >&2
    exit 1
  fi
done

unset XCL_EMULATION_MODE

if [[ "${SKIP_GRASU}" == "0" ]]; then
  echo "[1/3] Running GraSU update/check..."
  if [[ "${DRY_RUN}" == "0" ]]; then
    (
      cd "${GRASU_ROOT}"
      "${GRASU_HOST}" "${GRASU_XCLBIN}" "${GRAPH_FILE}" "${RESULT_FILE}"
    ) >"${RESULT_DIR}/grasu.log" 2>&1
  else
    echo "+ (cd ${GRASU_ROOT} && ${GRASU_HOST} ${GRASU_XCLBIN} ${GRAPH_FILE} ${RESULT_FILE})"
  fi
fi

echo "[2/3] Converting GraSU final-result graph for ReGraph..."
run_local_cmd "${SCRIPT_DIR}/grasu_result_to_regraph.py" \
  --input "${RESULT_FILE}" \
  --output "${REGRAPH_GRAPH}" \
  --base "${RESULT_BASE}" | tee "${RESULT_DIR}/convert.log"

if [[ "${SKIP_REGRAPH}" == "0" ]]; then
  echo "[3/3] Running ReGraph PR on converted final graph..."
  if [[ "${DRY_RUN}" == "0" ]]; then
    (
      cd "${REGRAPH_ROOT}"
      "${REGRAPH_HOST}" "${REGRAPH_XCLBIN}" "${REGRAPH_GRAPH}" "${REGRAPH_NUM_DENSE}"
    ) >"${RESULT_DIR}/regraph.log" 2>&1
  else
    echo "+ (cd ${REGRAPH_ROOT} && ${REGRAPH_HOST} ${REGRAPH_XCLBIN} ${REGRAPH_GRAPH} ${REGRAPH_NUM_DENSE})"
  fi
fi

echo "DONE result_dir=${RESULT_DIR}"
