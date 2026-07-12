#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

SPINE_SPLIT_ROOT="${SPINE_SPLIT_ROOT:-/home/feiyang/dev_space/spine-dynamic-graph}"
BUILD_ROOT="${BUILD_ROOT:-${GRI_ROOT}/.tmp_build/spine_split_edge_host_$(date +%Y%m%d_%H%M%S)}"
SOURCE_VITIS="${SOURCE_VITIS:-1}"
SOURCE_XRT="${SOURCE_XRT:-1}"
TARGET="${TARGET:-hw}"
MAX_N="${MAX_N:-16777216}"
VS_PARTITION_SIZE="${VS_PARTITION_SIZE:-1048576}"
MAX_SORT_N="${MAX_SORT_N:-131072}"
EDGE_BUF_CHUNK_SIZE="${EDGE_BUF_CHUNK_SIZE:-33554432}"
OUTPUT_NAME="${OUTPUT_NAME:-host_partitioned_csr_e2e_smoke_edge}"

usage() {
  cat <<USAGE
Usage: $0 [options]

Build a scratch Spine split-capable partitioned CSR E2E host with --edge-file
support. The source is copied from a split-capable Spine checkout and patched in
the scratch build directory; the source checkout is not modified.

Options:
  --spine-root PATH           Split-capable Spine checkout.
                              Default: ${SPINE_SPLIT_ROOT}
  --build-root PATH           Scratch build directory.
                              Default: ${BUILD_ROOT}
  --target hw|hw_emu|sw_emu   Host compile target macro. Default: ${TARGET}
  --no-source-vitis           Do not source Vitis settings64.sh.
  --no-source-xrt             Do not source XRT setup.sh.
  -h, --help                  Show this help.

Output:
  BUILD_ROOT/${OUTPUT_NAME}
USAGE
}

abs_under_root() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${GRI_ROOT}" "$1" ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --spine-root) SPINE_SPLIT_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --no-source-vitis) SOURCE_VITIS=0; shift ;;
    --no-source-xrt) SOURCE_XRT=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  hw|hw_emu|sw_emu) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

SPINE_SPLIT_ROOT="$(abs_under_root "${SPINE_SPLIT_ROOT}")"
BUILD_ROOT="$(abs_under_root "${BUILD_ROOT}")"
SPINE_TI="${SPINE_SPLIT_ROOT}/tests/test_integration"
SPINE_SRC="${SPINE_SPLIT_ROOT}/src"
PATCH_FILE="${GRI_ROOT}/patches/spine_split_host_edge_file.patch"
SOURCE_CPP="${SPINE_TI}/host_partitioned_csr_e2e_smoke.cpp"
XCL2_CPP="${SPINE_TI}/xcl2.cpp"
BUILD_CPP="${BUILD_ROOT}/host_partitioned_csr_e2e_smoke.cpp"
HOST_OUT="${BUILD_ROOT}/${OUTPUT_NAME}"

for required in "${SOURCE_CPP}" "${XCL2_CPP}" "${PATCH_FILE}" "${SPINE_TI}/host_split.hpp"; do
  if [[ ! -e "${required}" ]]; then
    echo "Missing required path: ${required}" >&2
    exit 1
  fi
done

mkdir -p "${BUILD_ROOT}"
cp "${SOURCE_CPP}" "${BUILD_CPP}"
(cd "${BUILD_ROOT}" && patch -p0 < "${PATCH_FILE}")

if [[ "${SOURCE_VITIS}" == "1" ]]; then
  set +u +e
  # shellcheck disable=SC1091
  source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
  vitis_status=$?
  set -euo pipefail
  if [[ "${vitis_status}" -ne 0 ]]; then
    echo "Vitis setup returned ${vitis_status}" >&2
    exit "${vitis_status}"
  fi
fi

if [[ "${SOURCE_XRT}" == "1" ]]; then
  set +u +e
  # shellcheck disable=SC1091
  source /opt/xilinx/xrt/setup.sh
  xrt_status=$?
  set -euo pipefail
  if [[ "${xrt_status}" -ne 0 ]]; then
    echo "XRT setup returned ${xrt_status}" >&2
    exit "${xrt_status}"
  fi
fi

if [[ -z "${XILINX_VITIS:-}" ]]; then
  echo "XILINX_VITIS is not set" >&2
  exit 1
fi
if [[ -z "${XILINX_XRT:-}" ]]; then
  echo "XILINX_XRT is not set" >&2
  exit 1
fi

cxxflags=(
  -std=c++17 -O3 -Wall -g
  -I"${SPINE_TI}"
  -I"${SPINE_TI}/stubs"
  -I"${SPINE_SRC}"
  -I"${XILINX_VITIS}/include"
  -I"${XILINX_XRT}/include"
  -DMAX_N="${MAX_N}"
  -DVS_PARTITION_SIZE="${VS_PARTITION_SIZE}"
  -DMAX_SORT_N="${MAX_SORT_N}"
  -DEDGE_BUF_CHUNK_SIZE="${EDGE_BUF_CHUNK_SIZE}"
  -DCL_DEVICE_HALF_FP_CONFIG=0x1033
)
if [[ "${TARGET}" == "sw_emu" || "${TARGET}" == "hw_emu" ]]; then
  cxxflags+=(-DEMULATION)
fi
if [[ -n "${XILINX_HLS:-}" ]]; then
  cxxflags+=(-I"${XILINX_HLS}/include")
fi

g++ "${cxxflags[@]}" \
  "${BUILD_CPP}" "${XCL2_CPP}" \
  -o "${HOST_OUT}" \
  -L"${XILINX_XRT}/lib" -lOpenCL -lxrt_coreutil -lstdc++ -lrt -pthread

{
  echo "spine_split_root=${SPINE_SPLIT_ROOT}"
  echo "build_root=${BUILD_ROOT}"
  echo "target=${TARGET}"
  echo "source_cpp=${SOURCE_CPP}"
  echo "patch_file=${PATCH_FILE}"
  echo "host_out=${HOST_OUT}"
  sha256sum "${SOURCE_CPP}" "${PATCH_FILE}" "${HOST_OUT}"
} > "${BUILD_ROOT}/manifest.env"

echo "DONE host=${HOST_OUT}"
echo "DONE manifest=${BUILD_ROOT}/manifest.env"
