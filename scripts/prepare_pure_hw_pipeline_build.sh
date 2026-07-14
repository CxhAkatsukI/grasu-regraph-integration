#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="sw_emu"
PLATFORM="xilinx_u55c_gen3x16_xdma_3_202210_1"
PLATFORM_XPFM="/opt/xilinx/platforms/${PLATFORM}/${PLATFORM}.xpfm"
KERNEL_FREQ=200
MAX_CACHE_SEGMENT="${GRASU_MAX_CACHE_SEGMENT:-131072}"
BUILD_ROOT=""
GRASU_BUILD_ROOT=""
REGRAPH_XCLBIN_DIR=""

usage() {
  cat <<USAGE
Usage: $0 [options]

Prepare reproducible Vitis compile/link commands for the first pure hardware
GraSU -> ReGraph pipeline. This script is generate-only; it does not run v++.

Options:
  --target sw_emu|hw_emu|hw      Build target. Default: ${TARGET}
  --platform NAME                Platform name. Default: ${PLATFORM}
  --platform-xpfm PATH           Platform xpfm. Default: ${PLATFORM_XPFM}
  --kernel-frequency MHz         Link frequency. Default: ${KERNEL_FREQ}
  --max-cache-segment N          GraSU max cache segment. Default: ${MAX_CACHE_SEGMENT}
  --build-root PATH              Output root. Default: .tmp_build/pure_pipeline_<target>_<timestamp>
  --grasu-build-root PATH        Existing GraSU build root for bin_search/dispatch XOs.
  --regraph-xclbin-dir PATH      Existing ReGraph SSSP XO directory for non-little-GS XOs.
  -h, --help                     Show this help.

Generated files:
  compile_commands.sh            Compile tokenized process_cache/process_ddr,
                                 pma_to_regraph_adapter, and stream little-GS XOs.
  link_command.sh                Link the pure pipeline xclbin.
  config/pure_pipeline_<target>.cfg
  manifest.env
  inputs.tsv
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
    --platform) PLATFORM="$2"; PLATFORM_XPFM="/opt/xilinx/platforms/${PLATFORM}/${PLATFORM}.xpfm"; shift 2 ;;
    --platform-xpfm) PLATFORM_XPFM="$(abs_path "$2")"; shift 2 ;;
    --kernel-frequency) KERNEL_FREQ="$2"; shift 2 ;;
    --max-cache-segment) MAX_CACHE_SEGMENT="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --grasu-build-root) GRASU_BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --regraph-xclbin-dir) REGRAPH_XCLBIN_DIR="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

if [[ -z "${BUILD_ROOT}" ]]; then
  BUILD_ROOT="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_$(date +%Y%m%d_%H%M%S)"
fi

if [[ -z "${GRASU_BUILD_ROOT}" ]]; then
  case "${TARGET}" in
    sw_emu) GRASU_BUILD_ROOT="${GRASU_ROOT}/.tmp_build/u55c_hbm/build" ;;
    hw_emu) GRASU_BUILD_ROOT="${GRASU_ROOT}/.tmp_build/u55c_hbm_hwemu/build" ;;
    hw) GRASU_BUILD_ROOT="${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/build" ;;
  esac
fi

if [[ -z "${REGRAPH_XCLBIN_DIR}" ]]; then
  case "${TARGET}" in
    sw_emu) REGRAPH_XCLBIN_DIR="/home/chuxiao/ReGraph_sssp_sw_emu_coldinit_scratch/xclbin_sw_emu_sssp" ;;
    hw_emu) REGRAPH_XCLBIN_DIR="/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/xclbin_hw_emu_sssp" ;;
    hw) REGRAPH_XCLBIN_DIR="/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp" ;;
  esac
fi

BUILD_DIR="${BUILD_ROOT}/build"
CFG_DIR="${BUILD_ROOT}/config"
LOG_DIR="${BUILD_ROOT}/logs"
REPORT_DIR="${BUILD_ROOT}/reports"
mkdir -p "${BUILD_DIR}" "${CFG_DIR}" "${LOG_DIR}" "${REPORT_DIR}" "${BUILD_ROOT}/ip_cache"

GRASU_CONFIG_ROOT="$(dirname "${GRASU_BUILD_ROOT}")/config"
if [[ ! -d "${GRASU_CONFIG_ROOT}" ]]; then
  GRASU_CONFIG_ROOT="${GRASU_ROOT}/u55c_hbm/config"
fi
GRASU_LINK_CFG="${GRASU_CONFIG_ROOT}/GraSU-link.cfg"
GRASU_STREAM_CFG="${GRASU_CONFIG_ROOT}/stream_connect.ini"
REGRAPH_CONNECTIVITY_CFG="$(dirname "${REGRAPH_XCLBIN_DIR}")/acc_template/connectivity.cfg"

if [[ ! -f "${GRASU_LINK_CFG}" || ! -f "${GRASU_STREAM_CFG}" ]]; then
  echo "Missing GraSU generated link/stream config under ${GRASU_CONFIG_ROOT}" >&2
  exit 1
fi
if [[ ! -f "${REGRAPH_CONNECTIVITY_CFG}" ]]; then
  echo "Missing ReGraph connectivity config: ${REGRAPH_CONNECTIVITY_CFG}" >&2
  exit 1
fi

write_compile_cfg() {
  local kernel="$1"
  local file="$2"
  {
    echo "platform=${PLATFORM_XPFM}"
    echo "save-temps=1"
    echo "kernel=${kernel}"
    echo "messageDb=${BUILD_DIR}/${kernel}.mdb"
    echo "temp_dir=${BUILD_DIR}/${kernel}"
    echo "report_dir=${REPORT_DIR}/${kernel}"
    echo "log_dir=${LOG_DIR}/${kernel}"
    echo
    echo "[advanced]"
    echo "misc=solution_name=${kernel}"
  } > "${file}"
}

copy_connectivity_body() {
  local file="$1"
  awk '
    BEGIN { in_conn = 0 }
    /^\[connectivity\]/ { in_conn = 1; next }
    in_conn == 1 { print }
  ' "${file}"
}

write_regraph_stream_connectivity() {
  local file="$1"
  awk '
    BEGIN { in_conn = 0 }
    /^\[connectivity\]/ { in_conn = 1; next }
    in_conn == 0 { next }
    {
      line = $0
      gsub("littleKernelScatterGather_1", "littleKernelScatterGatherStream_1", line)
      if (line ~ /^nk=littleKernelScatterGather:1/) {
        line = "nk=littleKernelScatterGatherStream:1:littleKernelScatterGatherStream_1"
      }
      if (line ~ /^sp=littleKernelScatterGatherStream_1\.part_edge_array:/) {
        next
      }
      print line
    }
  ' "${file}"
}

write_compile_cfg process_cache "${CFG_DIR}/process_cache_token_compile.cfg"
write_compile_cfg process_ddr "${CFG_DIR}/process_ddr_token_compile.cfg"
write_compile_cfg pma_to_regraph_adapter "${CFG_DIR}/pma_to_regraph_adapter_compile.cfg"
write_compile_cfg littleKernelScatterGatherStream "${CFG_DIR}/little_gs_stream_compile.cfg"

LINK_CFG="${CFG_DIR}/pure_pipeline_${TARGET}.cfg"
OUT_XCLBIN="${BUILD_DIR}/grasu_regraph_pure_pipeline.${TARGET}.xclbin"
COMPILE_COMMANDS="${BUILD_ROOT}/compile_commands.sh"
LINK_COMMAND="${BUILD_ROOT}/link_command.sh"
MANIFEST="${BUILD_ROOT}/manifest.env"
INPUTS="${BUILD_ROOT}/inputs.tsv"

{
  echo "platform=${PLATFORM_XPFM}"
  echo "save-temps=1"
  echo "messageDb=${BUILD_DIR}/grasu_regraph_pure_pipeline.mdb"
  echo "temp_dir=${BUILD_DIR}/link"
  echo "report_dir=${REPORT_DIR}/link"
  echo "log_dir=${LOG_DIR}/link"
  echo "remote_ip_cache=${BUILD_ROOT}/ip_cache"
  echo
  echo "[advanced]"
  echo "misc=solution_name=link"
  echo "param=compiler.enablePerformanceTrace=1"
  echo
  echo "[connectivity]"
  echo "# GraSU U55C connectivity"
  copy_connectivity_body "${GRASU_LINK_CFG}"
  echo
  echo "# GraSU internal update streams"
  copy_connectivity_body "${GRASU_STREAM_CFG}"
  echo
  echo "# GraSU PMA completion barrier into adapter"
  echo "stream_connect=process_cache_1.completion_token:pma_to_regraph_adapter_1.done0:16"
  echo "stream_connect=process_ddr_1.completion_token:pma_to_regraph_adapter_1.done1:16"
  echo "stream_connect=process_cache_2.completion_token:pma_to_regraph_adapter_1.done2:16"
  echo "stream_connect=process_ddr_2.completion_token:pma_to_regraph_adapter_1.done3:16"
  echo "stream_connect=pma_to_regraph_adapter_1.edge_burst_out:littleKernelScatterGatherStream_1.edge_burst_in:32"
  echo
  echo "# PMA-to-ReGraph adapter"
  echo "nk=pma_to_regraph_adapter:1:pma_to_regraph_adapter_1"
  echo "sp=pma_to_regraph_adapter_1.pma0:HBM[0]"
  echo "sp=pma_to_regraph_adapter_1.pma1:HBM[1]"
  echo "sp=pma_to_regraph_adapter_1.pma2:HBM[2]"
  echo "sp=pma_to_regraph_adapter_1.pma3:HBM[3]"
  echo "sp=pma_to_regraph_adapter_1.row_offset:HBM[0]"
  echo "slr=pma_to_regraph_adapter_1:SLR1"
  echo
  echo "# ReGraph SSSP connectivity with stream-input little GS"
  write_regraph_stream_connectivity "${REGRAPH_CONNECTIVITY_CFG}"
} > "${LINK_CFG}"

declare -a EXISTING_XOS=(
  "${GRASU_BUILD_ROOT}/bin_search.${TARGET}.xo"
  "${GRASU_BUILD_ROOT}/dispatch.${TARGET}.xo"
  "${REGRAPH_XCLBIN_DIR}/kernelApply.${TARGET}.${PLATFORM}.xo"
  "${REGRAPH_XCLBIN_DIR}/kernelHBMWrapper.${TARGET}.${PLATFORM}.xo"
  "${REGRAPH_XCLBIN_DIR}/kernelLittleGSMerger.${TARGET}.${PLATFORM}.xo"
  "${REGRAPH_XCLBIN_DIR}/bigKernelScatterGather.${TARGET}.${PLATFORM}.xo"
  "${REGRAPH_XCLBIN_DIR}/kernelBigGSMerger.${TARGET}.${PLATFORM}.xo"
)

declare -a GENERATED_XOS=(
  "${BUILD_DIR}/process_cache.${TARGET}.xo"
  "${BUILD_DIR}/process_ddr.${TARGET}.xo"
  "${BUILD_DIR}/pma_to_regraph_adapter.${TARGET}.xo"
  "${BUILD_DIR}/littleKernelScatterGatherStream.${TARGET}.xo"
)

{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  echo
  printf 'v++ --target %q --compile -DGRASU_COMPACT_HBM_PORTS -DGRASU_ENABLE_COMPLETION_TOKEN -DGRASU_MAX_CACHE_SEGMENT=%q -I%q -I%q -I%q --config %q -o %q %q\n' \
    "${TARGET}" "${MAX_CACHE_SEGMENT}" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src" "${GRASU_ROOT}/GraSU/GraSU/src" \
    "/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include/etc" \
    "${CFG_DIR}/process_cache_token_compile.cfg" \
    "${BUILD_DIR}/process_cache.${TARGET}.xo" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_process_cache.cpp"
  printf 'v++ --target %q --compile -DGRASU_COMPACT_HBM_PORTS -DGRASU_ENABLE_COMPLETION_TOKEN -DGRASU_MAX_CACHE_SEGMENT=%q -I%q -I%q -I%q --config %q -o %q %q\n' \
    "${TARGET}" "${MAX_CACHE_SEGMENT}" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src" "${GRASU_ROOT}/GraSU/GraSU/src" \
    "/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include/etc" \
    "${CFG_DIR}/process_ddr_token_compile.cfg" \
    "${BUILD_DIR}/process_ddr.${TARGET}.xo" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_process_ddr.cpp"
  printf 'v++ --target %q --compile --config %q -I%q -o %q %q\n' \
    "${TARGET}" "${CFG_DIR}/pma_to_regraph_adapter_compile.cfg" \
    "/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include" \
    "${BUILD_DIR}/pma_to_regraph_adapter.${TARGET}.xo" \
    "${GRI_ROOT}/kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
  printf 'v++ --target %q --compile -O3 --config %q -DHAVE_EDGE_PROP=1 -DHAVE_UNSIGNED_PROP=1 -DHAVE_APPLY_OUTDEG=0 -DHAVE_VERTEX_PROP=1 -DPARTITION_SIZE=65536 -DLITTLE_KERNEL_DST_BUFFER_SIZE=65536 -DBIG_KERNEL_DST_BUFFER_SIZE=524288 -DSRC_BUFFER_SIZE=4096 -DLOG2_SRC_BUFFER_SIZE=12 -DVERTEX_REORDER_ENABLE=1 -DENABLE_COMPRESSED_EDGE_INPUT=0 -DBIG_KERNEL_NUM=1 -DLITTLE_KERNEL_NUM=1 -I%q -I%q -I%q -I%q -I%q -I%q -o %q %q\n' \
    "${TARGET}" "${CFG_DIR}/little_gs_stream_compile.cfg" \
    "${REGRAPH_ROOT}/acc_udfs/sssp" "${REGRAPH_ROOT}" "${REGRAPH_ROOT}/acc_template" \
    "${REGRAPH_ROOT}/acc_template/common" "${REGRAPH_ROOT}/acc_udfs" \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs" \
    "${BUILD_DIR}/littleKernelScatterGatherStream.${TARGET}.xo" \
    "${GRI_ROOT}/kernels/regraph_stream_little_gs/little_gs_stream.cpp"
} > "${COMPILE_COMMANDS}"
chmod +x "${COMPILE_COMMANDS}"

{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  printf 'v++ --target %q --link --kernel_frequency %q --config %q -o %q' \
    "${TARGET}" "${KERNEL_FREQ}" "${LINK_CFG}" "${OUT_XCLBIN}"
  for xo in "${EXISTING_XOS[@]}" "${GENERATED_XOS[@]}"; do
    printf ' %q' "${xo}"
  done
  printf '\n'
} > "${LINK_COMMAND}"
chmod +x "${LINK_COMMAND}"

{
  echo "GRI_ROOT=${GRI_ROOT}"
  echo "GRASU_ROOT=${GRASU_ROOT}"
  echo "REGRAPH_ROOT=${REGRAPH_ROOT}"
  echo "TARGET=${TARGET}"
  echo "PLATFORM=${PLATFORM}"
  echo "PLATFORM_XPFM=${PLATFORM_XPFM}"
  echo "KERNEL_FREQ=${KERNEL_FREQ}"
  echo "MAX_CACHE_SEGMENT=${MAX_CACHE_SEGMENT}"
  echo "BUILD_ROOT=${BUILD_ROOT}"
  echo "GRASU_BUILD_ROOT=${GRASU_BUILD_ROOT}"
  echo "REGRAPH_XCLBIN_DIR=${REGRAPH_XCLBIN_DIR}"
  echo "LINK_CFG=${LINK_CFG}"
  echo "OUT_XCLBIN=${OUT_XCLBIN}"
  echo "COMPILE_COMMANDS=${COMPILE_COMMANDS}"
  echo "LINK_COMMAND=${LINK_COMMAND}"
} > "${MANIFEST}"

{
  printf 'role\tstatus\tsha256\tbytes\tpath\n'
  for xo in "${EXISTING_XOS[@]}"; do
    if [[ -f "${xo}" ]]; then
      printf 'existing_xo\tpresent\t'
      sha256sum "${xo}" | awk '{printf "%s\t", $1}'
      stat --printf '%s\t%n\n' "${xo}"
    else
      printf 'existing_xo\tmissing\t-\t-\t%s\n' "${xo}"
    fi
  done
  for xo in "${GENERATED_XOS[@]}"; do
    if [[ -f "${xo}" ]]; then
      printf 'generated_xo\tpresent\t'
      sha256sum "${xo}" | awk '{printf "%s\t", $1}'
      stat --printf '%s\t%n\n' "${xo}"
    else
      printf 'generated_xo\tpending\t-\t-\t%s\n' "${xo}"
    fi
  done
} > "${INPUTS}"

echo "Prepared pure pipeline build commands:"
echo "  ${BUILD_ROOT}"
echo
echo "Compile new/modified XOs:"
echo "  ${COMPILE_COMMANDS}"
echo
echo "Then link xclbin:"
echo "  ${LINK_COMMAND}"
