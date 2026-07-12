#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw"
OUT_ROOT=""
GRASU_BUILD_ROOT=""
REGRAPH_BUILD_ROOT=""
COMBINED_BUILD_ROOT=""
GRASU_HOST=""
GRASU_XCLBIN=""
REGRAPH_HOST=""
REGRAPH_XCLBIN=""
COMBINED_XCLBIN=""

usage() {
  cat <<USAGE
Usage: $0 [options]

Collect and compare real-hw resource evidence for:
  1. standalone GraSU
  2. standalone ReGraph weighted SSSP
  3. combined GraSU + ReGraph xclbin

The script does not build or run hardware. It only packages existing artifacts
and produces resource-delta tables for review.

Options:
  --target hw|hw_emu              Evidence target. Default: ${TARGET}
  --out-root PATH                 Output evidence root. Default: results/resource_evidence_<timestamp>_combined_<target>
  --grasu-build-root PATH         GraSU build root. Default is derived from --target.
  --regraph-build-root PATH       ReGraph build root. Default is derived from --target.
  --combined-build-root PATH      Combined build root. Default is derived from --target.
  --grasu-host PATH               GraSU host executable.
  --grasu-xclbin PATH             GraSU xclbin.
  --regraph-host PATH             ReGraph host executable.
  --regraph-xclbin PATH           ReGraph standalone xclbin.
  --combined-xclbin PATH          Combined xclbin.
  -h, --help                      Show this help.
USAGE
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${PWD}" "$1" ;;
  esac
}

manifest_value() {
  local file="$1"
  local key="$2"
  awk -F= -v key="${key}" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "${file}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --out-root) OUT_ROOT="$(abs_path "$2")"; shift 2 ;;
    --grasu-build-root) GRASU_BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --regraph-build-root) REGRAPH_BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --combined-build-root) COMBINED_BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --grasu-host) GRASU_HOST="$(abs_path "$2")"; shift 2 ;;
    --grasu-xclbin) GRASU_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --regraph-host) REGRAPH_HOST="$(abs_path "$2")"; shift 2 ;;
    --regraph-xclbin) REGRAPH_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    --combined-xclbin) COMBINED_XCLBIN="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  hw|hw_emu) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

if [[ -z "${OUT_ROOT}" ]]; then
  OUT_ROOT="${GRI_ROOT}/results/resource_evidence_$(date +%Y%m%d_%H%M%S)_combined_${TARGET}"
fi

if [[ -z "${COMBINED_BUILD_ROOT}" ]]; then
  if [[ "${TARGET}" == "hw_emu" ]]; then
    COMBINED_BUILD_ROOT="${GRI_ROOT}/.tmp_build/combined_hw_emu_host_compatible"
  else
    COMBINED_BUILD_ROOT="${GRI_ROOT}/.tmp_build/combined_hw_coldinit_250mhz"
  fi
fi

MANIFEST="${COMBINED_BUILD_ROOT}/manifest.env"
MANIFEST_GRASU_BUILD_ROOT=""
MANIFEST_REGRAPH_XCLBIN_DIR=""
if [[ -f "${MANIFEST}" ]]; then
  MANIFEST_GRASU_BUILD_ROOT="$(manifest_value "${MANIFEST}" GRASU_BUILD_ROOT)"
  MANIFEST_REGRAPH_XCLBIN_DIR="$(manifest_value "${MANIFEST}" REGRAPH_XCLBIN_DIR)"
fi

if [[ -z "${GRASU_BUILD_ROOT}" && -n "${MANIFEST_GRASU_BUILD_ROOT}" ]]; then
  GRASU_BUILD_ROOT="$(dirname "${MANIFEST_GRASU_BUILD_ROOT}")"
fi
if [[ -z "${REGRAPH_BUILD_ROOT}" ]]; then
  if [[ -n "${MANIFEST_REGRAPH_XCLBIN_DIR}" ]]; then
    REGRAPH_BUILD_ROOT="$(dirname "${MANIFEST_REGRAPH_XCLBIN_DIR}")"
  elif [[ "${TARGET}" == "hw_emu" ]]; then
    REGRAPH_BUILD_ROOT="/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch"
  else
    REGRAPH_BUILD_ROOT="/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch"
  fi
fi
if [[ -z "${GRASU_BUILD_ROOT}" ]]; then
  if [[ "${TARGET}" == "hw_emu" ]]; then
    GRASU_BUILD_ROOT="${GRASU_ROOT}/.tmp_build/u55c_hbm_hwemu"
  else
    GRASU_BUILD_ROOT="${GRASU_ROOT}/.tmp_build/u55c_hbm_hw"
  fi
fi

REGRAPH_LABEL="regraph_sssp_${TARGET}_manifest_baseline"
if [[ "${REGRAPH_BUILD_ROOT}" == *coldinit* ]]; then
  REGRAPH_LABEL="regraph_sssp_${TARGET}_coldinit_250mhz"
fi

if [[ -z "${GRASU_HOST}" ]]; then
  GRASU_HOST="${GRASU_BUILD_ROOT}/GraSU_host_u55c"
fi
if [[ -z "${GRASU_XCLBIN}" ]]; then
  GRASU_XCLBIN="${GRASU_BUILD_ROOT}/build/GraSU_u55c_hbm.${TARGET}.xclbin"
fi
if [[ -z "${REGRAPH_HOST}" ]]; then
  REGRAPH_HOST="${REGRAPH_BUILD_ROOT}/host_graph_fpga_sssp"
fi
if [[ -z "${REGRAPH_XCLBIN}" ]]; then
  REGRAPH_XCLBIN="${REGRAPH_BUILD_ROOT}/xclbin_${TARGET}_sssp/graph_fpga.${TARGET}.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin"
fi
if [[ -z "${COMBINED_XCLBIN}" ]]; then
  COMBINED_XCLBIN="${COMBINED_BUILD_ROOT}/build/grasu_regraph_combined.${TARGET}.xclbin"
fi

missing=0
for path in \
  "${GRASU_BUILD_ROOT}" \
  "${REGRAPH_BUILD_ROOT}" \
  "${COMBINED_BUILD_ROOT}" \
  "${GRASU_HOST}" \
  "${GRASU_XCLBIN}" \
  "${REGRAPH_HOST}" \
  "${REGRAPH_XCLBIN}" \
  "${COMBINED_XCLBIN}"; do
  if [[ ! -e "${path}" ]]; then
    echo "Missing required evidence input: ${path}" >&2
    missing=1
  fi
done
if [[ "${missing}" == "1" ]]; then
  echo "Evidence collection stopped before writing partial comparison output." >&2
  exit 1
fi

mkdir -p "${OUT_ROOT}"

"${SCRIPT_DIR}/collect_vitis_evidence.py" \
  --label "grasu_${TARGET}_u55c" \
  --build-root "${GRASU_BUILD_ROOT}" \
  --out-dir "${OUT_ROOT}/grasu_${TARGET}" \
  --artifact "${GRASU_HOST}" \
  --artifact "${GRASU_XCLBIN}" \
  --note "GraSU standalone U55C ${TARGET} baseline."

"${SCRIPT_DIR}/collect_vitis_evidence.py" \
  --label "${REGRAPH_LABEL}" \
  --build-root "${REGRAPH_BUILD_ROOT}" \
  --out-dir "${OUT_ROOT}/${REGRAPH_LABEL}" \
  --artifact "${REGRAPH_HOST}" \
  --artifact "${REGRAPH_XCLBIN}" \
  --note "ReGraph weighted SSSP ${TARGET} baseline matched to the combined build manifest when available."

"${SCRIPT_DIR}/collect_vitis_evidence.py" \
  --label "grasu_regraph_combined_${TARGET}" \
  --build-root "${COMBINED_BUILD_ROOT}" \
  --out-dir "${OUT_ROOT}/combined_${TARGET}" \
  --artifact "${GRASU_HOST}" \
  --artifact "${REGRAPH_HOST}" \
  --artifact "${COMBINED_XCLBIN}" \
  --note "Combined GraSU + ReGraph weighted SSSP ${TARGET} xclbin."

"${SCRIPT_DIR}/compare_vitis_resources.py" \
  --label "grasu_${TARGET}_vs_combined_${TARGET}" \
  --before "${OUT_ROOT}/grasu_${TARGET}" \
  --after "${OUT_ROOT}/combined_${TARGET}" \
  --out-dir "${OUT_ROOT}/compare_grasu_${TARGET}_vs_combined"

"${SCRIPT_DIR}/compare_vitis_resources.py" \
  --label "regraph_${TARGET}_vs_combined_${TARGET}" \
  --before "${OUT_ROOT}/${REGRAPH_LABEL}" \
  --after "${OUT_ROOT}/combined_${TARGET}" \
  --out-dir "${OUT_ROOT}/compare_regraph_${TARGET}_vs_combined"

{
  echo "# Combined ${TARGET} Evidence Bundle"
  echo
  echo "- GraSU evidence: \`${OUT_ROOT}/grasu_${TARGET}\`"
  echo "- ReGraph evidence: \`${OUT_ROOT}/${REGRAPH_LABEL}\`"
  echo "- Combined evidence: \`${OUT_ROOT}/combined_${TARGET}\`"
  echo "- GraSU comparison: \`${OUT_ROOT}/compare_grasu_${TARGET}_vs_combined\`"
  echo "- ReGraph comparison: \`${OUT_ROOT}/compare_regraph_${TARGET}_vs_combined\`"
  echo
  echo "## Inputs"
  echo
  printf -- "- GraSU host: \`%s\`\n" "${GRASU_HOST}"
  printf -- "- GraSU xclbin: \`%s\`\n" "${GRASU_XCLBIN}"
  printf -- "- ReGraph host: \`%s\`\n" "${REGRAPH_HOST}"
  printf -- "- ReGraph xclbin: \`%s\`\n" "${REGRAPH_XCLBIN}"
  printf -- "- Combined xclbin: \`%s\`\n" "${COMBINED_XCLBIN}"
  if [[ -f "${MANIFEST}" ]]; then
    printf -- "- Combined manifest: \`%s\`\n" "${MANIFEST}"
  fi
  echo
  echo "## Review Gate"
  echo
  echo "Open the two comparison summaries and check same-component changes first:"
  echo
  printf -- "- \`%s\`\n" "${OUT_ROOT}/compare_grasu_${TARGET}_vs_combined/summary.md"
  printf -- "- \`%s\`\n" "${OUT_ROOT}/compare_regraph_${TARGET}_vs_combined/summary.md"
  echo
  echo "Same-component resource or CU-count changes require an explanation before"
  echo "using the combined xclbin for final performance claims."
} > "${OUT_ROOT}/README.md"

echo "DONE combined_${TARGET}_evidence=${OUT_ROOT}"
