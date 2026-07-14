#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${OUT_DIR:-${GRI_ROOT}/.tmp_build/pure_pipeline_host}"
OUT_BIN="${OUT_BIN:-}"
VITIS_HLS="${VITIS_HLS:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1}"

usage() {
  cat <<USAGE
Usage: $0 [options]

Build the first-stage pure pipeline host runner.

Options:
  --out-dir PATH    Output directory. Default: ${OUT_DIR}
  --out-bin PATH    Output binary. Default: <out-dir>/pure_pipeline_host
  -h, --help        Show this help.
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
    --out-bin) OUT_BIN="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

mkdir -p "${OUT_DIR}"
if [[ -z "${OUT_BIN}" ]]; then
  OUT_BIN="${OUT_DIR}/pure_pipeline_host"
fi

g++ -std=c++17 -O2 \
  -DGRASU_MAX_CACHE_SEGMENT=131072 \
  -I"${XILINX_XRT}/include" \
  -I"${VITIS_HLS}/include" \
  -I"${VITIS_HLS}/include/etc" \
  -I"${GRASU_ROOT}/GraSU/GraSU/src" \
  "${GRI_ROOT}/tools/pure_pipeline_host.cpp" \
  -L"${XILINX_XRT}/lib" \
  -lxilinxopencl -lpthread \
  -o "${OUT_BIN}"

sha256sum "${OUT_BIN}" | tee "${OUT_DIR}/pure_pipeline_host.sha256"
printf 'built %s\n' "${OUT_BIN}"
