#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
OUT_DIR=""

usage() {
  cat <<USAGE
Usage: $0 [--out-dir PATH]

Run lightweight C++ syntax checks for the GraSU PMA writer kernels with the
completion-token macro disabled and enabled. This does not synthesize XOs.
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
    --out-dir) OUT_DIR="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

KERNEL_SRC="${GRASU_ROOT}/GraSU/GraSU_kernels/src"
if [[ ! -d "${KERNEL_SRC}" ]]; then
  echo "Missing GraSU kernel source directory: ${KERNEL_SRC}" >&2
  exit 1
fi
if [[ ! -d "${HLS_INCLUDE}" ]]; then
  echo "Missing Vitis HLS include directory: ${HLS_INCLUDE}" >&2
  exit 1
fi

if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/.tmp_build/grasu_completion_token_check_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "${OUT_DIR}"

compile_one() {
  local mode="$1"
  local src="$2"
  local extra_define="$3"
  local stem
  stem="$(basename "${src}" .cpp).${mode}"
  local obj="${OUT_DIR}/${stem}.o"
  local log="${OUT_DIR}/${stem}.log"

  g++ -std=c++17 -w ${extra_define} \
    -I"${HLS_INCLUDE}" \
    -I"${KERNEL_SRC}" \
    -c "${src}" \
    -o "${obj}" \
    > "${log}" 2>&1
}

{
  echo "timestamp=$(date -Is)"
  echo "GRI_ROOT=${GRI_ROOT}"
  echo "GRASU_ROOT=${GRASU_ROOT}"
  echo "KERNEL_SRC=${KERNEL_SRC}"
  echo "HLS_INCLUDE=${HLS_INCLUDE}"
} > "${OUT_DIR}/manifest.env"

compile_one no_token "${KERNEL_SRC}/kernel_process_cache.cpp" ""
compile_one no_token "${KERNEL_SRC}/kernel_process_ddr.cpp" ""
compile_one token "${KERNEL_SRC}/kernel_process_cache.cpp" "-DGRASU_ENABLE_COMPLETION_TOKEN"
compile_one token "${KERNEL_SRC}/kernel_process_ddr.cpp" "-DGRASU_ENABLE_COMPLETION_TOKEN"

{
  sha256sum "${KERNEL_SRC}/kernel_config.h"
  sha256sum "${KERNEL_SRC}/kernel_process_cache.cpp"
  sha256sum "${KERNEL_SRC}/kernel_process_ddr.cpp"
  find "${OUT_DIR}" -maxdepth 1 -type f \( -name '*.o' -o -name '*.log' \) -print \
    | LC_ALL=C sort \
    | xargs -r sha256sum
} > "${OUT_DIR}/SHA256SUMS"

echo "GraSU completion-token syntax checks passed:"
echo "  ${OUT_DIR}"
