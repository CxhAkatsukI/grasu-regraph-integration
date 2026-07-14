#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="sw_emu"
PLATFORM="xilinx_u55c_gen3x16_xdma_3_202210_1"
PLATFORM_XPFM="/opt/xilinx/platforms/${PLATFORM}/${PLATFORM}.xpfm"
KERNEL_FREQ=200
MAX_CACHE_SEGMENT="${GRASU_MAX_CACHE_SEGMENT:-131072}"
HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
HLS_INCLUDE_ETC="${HLS_INCLUDE_ETC:-${HLS_INCLUDE}/etc}"
SW_EMU_GTHREAD_DEFINE="-D_GTHREAD_USE_COND_INIT_FUNC"
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
  --hls-include PATH             Vitis HLS include directory. Default: ${HLS_INCLUDE}
  --hls-include-etc PATH         Vitis HLS include/etc directory. Default: ${HLS_INCLUDE_ETC}
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
    --hls-include) HLS_INCLUDE="$(abs_path "$2")"; shift 2 ;;
    --hls-include-etc) HLS_INCLUDE_ETC="$(abs_path "$2")"; shift 2 ;;
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
TMP_DIR="${BUILD_ROOT}/tmp"
GCC_COMPAT_INCLUDE="${BUILD_ROOT}/gcc_compat"
GCC_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu"
GCC_COMPILER_PATH="/usr/bin"
mkdir -p "${BUILD_DIR}" "${CFG_DIR}" "${LOG_DIR}" "${REPORT_DIR}" "${BUILD_ROOT}/ip_cache" "${TMP_DIR}" "${GCC_COMPAT_INCLUDE}/bits"

{
  echo "#ifndef _GTHREAD_USE_MUTEX_INIT_FUNC"
  echo "#define _GTHREAD_USE_MUTEX_INIT_FUNC 1"
  echo "#endif"
  echo "#ifndef _GTHREAD_USE_RECURSIVE_MUTEX_INIT_FUNC"
  echo "#define _GTHREAD_USE_RECURSIVE_MUTEX_INIT_FUNC 1"
  echo "#endif"
  echo "#ifndef _GTHREAD_USE_COND_INIT_FUNC"
  echo "#define _GTHREAD_USE_COND_INIT_FUNC 1"
  echo "#endif"
  echo "#include_next <bits/gthr-default.h>"
} > "${GCC_COMPAT_INCLUDE}/bits/gthr-default.h"

GRASU_CONFIG_ROOT="$(dirname "${GRASU_BUILD_ROOT}")/config"
if [[ ! -d "${GRASU_CONFIG_ROOT}" ]]; then
  GRASU_CONFIG_ROOT="${GRASU_ROOT}/u55c_hbm/config"
fi
GRASU_LINK_CFG="${GRASU_CONFIG_ROOT}/GraSU-link.cfg"
GRASU_STREAM_CFG="${GRASU_CONFIG_ROOT}/stream_connect.ini"
REGRAPH_CONNECTIVITY_CFG="${REGRAPH_ROOT}/acc_template/connectivity.cfg"
REGRAPH_LINK_ROOT="$(dirname "${REGRAPH_XCLBIN_DIR}")"

if [[ ! -f "${GRASU_LINK_CFG}" || ! -f "${GRASU_STREAM_CFG}" ]]; then
  echo "Missing GraSU generated link/stream config under ${GRASU_CONFIG_ROOT}" >&2
  exit 1
fi
if [[ ! -d "${HLS_INCLUDE}" ]]; then
  echo "Missing Vitis HLS include directory: ${HLS_INCLUDE}" >&2
  exit 1
fi
if [[ ! -d "${HLS_INCLUDE_ETC}" ]]; then
  echo "Missing Vitis HLS include/etc directory: ${HLS_INCLUDE_ETC}" >&2
  exit 1
fi
if [[ ! -f "${REGRAPH_CONNECTIVITY_CFG}" ]]; then
  echo "Missing ReGraph connectivity config: ${REGRAPH_CONNECTIVITY_CFG}" >&2
  exit 1
fi

REGRAPH_TARGET_DEFINE=""
case "${TARGET}" in
  sw_emu) REGRAPH_TARGET_DEFINE="-DSW_EMU" ;;
  hw_emu) REGRAPH_TARGET_DEFINE="-DHW_EMU" ;;
esac

declare -a GRASU_BASE_FLAGS=(
  "${SW_EMU_GTHREAD_DEFINE}"
  "-DGRASU_MAX_CACHE_SEGMENT=${MAX_CACHE_SEGMENT}"
  "-I${GRASU_ROOT}/GraSU/GraSU_kernels/src"
  "-I${GRASU_ROOT}/GraSU/GraSU/src"
  "-I${HLS_INCLUDE_ETC}"
)
case "${TARGET}" in
  sw_emu) GRASU_BASE_FLAGS+=("-DSW_EMU") ;;
  hw_emu|hw) GRASU_BASE_FLAGS+=("-DGRASU_COMPACT_HBM_PORTS") ;;
esac

declare -a REGRAPH_COMMON_FLAGS=(
  "${SW_EMU_GTHREAD_DEFINE}"
  "-O3"
  "-DHAVE_EDGE_PROP=1"
  "-DHAVE_UNSIGNED_PROP=1"
  "-DHAVE_APPLY_OUTDEG=0"
  "-DHAVE_VERTEX_PROP=1"
  "-DPARTITION_SIZE=65536"
  "-DLITTLE_KERNEL_DST_BUFFER_SIZE=65536"
  "-DBIG_KERNEL_DST_BUFFER_SIZE=524288"
  "-DSRC_BUFFER_SIZE=4096"
  "-DLOG2_SRC_BUFFER_SIZE=12"
  "-DVERTEX_REORDER_ENABLE=1"
  "-DENABLE_COMPRESSED_EDGE_INPUT=0"
  "-DBIG_KERNEL_NUM=1"
  "-DLITTLE_KERNEL_NUM=1"
  "-I${HLS_INCLUDE_ETC}"
  "-I${REGRAPH_ROOT}/acc_udfs/sssp"
  "-I${REGRAPH_ROOT}"
  "-I${REGRAPH_ROOT}/acc_template"
  "-I${REGRAPH_ROOT}/acc_template/common"
  "-I${REGRAPH_ROOT}/acc_udfs"
)
if [[ -n "${REGRAPH_TARGET_DEFINE}" ]]; then
  REGRAPH_COMMON_FLAGS+=("${REGRAPH_TARGET_DEFINE}")
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
      gsub("littleKernelScatterGather_1", "lksg_stream_1", line)
      if (line ~ /^nk=littleKernelScatterGather:1/) {
        line = "nk=lksg_stream:1:lksg_stream_1"
      }
      if (line ~ /^sp=lksg_stream_1\.part_edge_array:/) {
        next
      }
      print line
    }
  ' "${file}"
}

write_compile_cfg bin_search "${CFG_DIR}/bin_search_compile.cfg"
write_compile_cfg dispatch "${CFG_DIR}/dispatch_compile.cfg"
write_compile_cfg process_cache "${CFG_DIR}/process_cache_token_compile.cfg"
write_compile_cfg process_ddr "${CFG_DIR}/process_ddr_token_compile.cfg"
write_compile_cfg kernelApply "${CFG_DIR}/kernelApply_compile.cfg"
write_compile_cfg kernelHBMWrapper "${CFG_DIR}/kernelHBMWrapper_compile.cfg"
write_compile_cfg kernelLittleGSMerger "${CFG_DIR}/kernelLittleGSMerger_compile.cfg"
write_compile_cfg bigKernelScatterGather "${CFG_DIR}/bigKernelScatterGather_compile.cfg"
write_compile_cfg kernelBigGSMerger "${CFG_DIR}/kernelBigGSMerger_compile.cfg"
write_compile_cfg pma_completion_barrier "${CFG_DIR}/pma_completion_barrier_compile.cfg"
write_compile_cfg pma_to_regraph_adapter "${CFG_DIR}/pma_to_regraph_adapter_compile.cfg"
write_compile_cfg lksg_stream "${CFG_DIR}/little_gs_stream_compile.cfg"

emit_regraph_compile_command() {
  local kernel_dir="$1"
  local cfg="$2"
  local out="$3"
  local src="$4"
  printf 'v++ --target %q --compile' "${TARGET}"
  for flag in "${REGRAPH_COMMON_FLAGS[@]}"; do
    printf ' %q' "${flag}"
  done
  printf ' --config %q -I%q -o %q %q\n' \
    "${cfg}" "${kernel_dir}" "${out}" "${src}"
}

emit_grasu_compile_command() {
  local cfg="$1"
  local out="$2"
  local src="$3"
  shift 3
  printf 'v++ --target %q --compile' "${TARGET}"
  for flag in "${GRASU_BASE_FLAGS[@]}" "$@"; do
    printf ' %q' "${flag}"
  done
  printf ' --config %q -o %q %q\n' "${cfg}" "${out}" "${src}"
}

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
  echo "stream_connect=process_cache_1.completion_token:pma_completion_barrier_1.done0:16"
  echo "stream_connect=process_ddr_1.completion_token:pma_completion_barrier_1.done1:16"
  echo "stream_connect=process_cache_2.completion_token:pma_completion_barrier_1.done2:16"
  echo "stream_connect=process_ddr_2.completion_token:pma_completion_barrier_1.done3:16"
  echo "stream_connect=pma_to_regraph_adapter_1.edge_burst_out:lksg_stream_1.edge_burst_in:32"
  echo
  echo "# PMA completion barrier"
  echo "nk=pma_completion_barrier:1:pma_completion_barrier_1"
  echo "slr=pma_completion_barrier_1:SLR1"
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

declare -a EXISTING_XOS=()

declare -a GENERATED_XOS=(
  "${BUILD_DIR}/bin_search.${TARGET}.xo"
  "${BUILD_DIR}/dispatch.${TARGET}.xo"
  "${BUILD_DIR}/kernelApply.${TARGET}.${PLATFORM}.xo"
  "${BUILD_DIR}/kernelHBMWrapper.${TARGET}.${PLATFORM}.xo"
  "${BUILD_DIR}/kernelLittleGSMerger.${TARGET}.${PLATFORM}.xo"
  "${BUILD_DIR}/bigKernelScatterGather.${TARGET}.${PLATFORM}.xo"
  "${BUILD_DIR}/kernelBigGSMerger.${TARGET}.${PLATFORM}.xo"
  "${BUILD_DIR}/process_cache.${TARGET}.xo"
  "${BUILD_DIR}/process_ddr.${TARGET}.xo"
  "${BUILD_DIR}/pma_completion_barrier.${TARGET}.xo"
  "${BUILD_DIR}/pma_to_regraph_adapter.${TARGET}.xo"
  "${BUILD_DIR}/lksg_stream.${TARGET}.xo"
)

{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  printf 'export TMPDIR=%q\n' "${TMP_DIR}"
  printf 'export TMP=%q\n' "${TMP_DIR}"
  printf 'export TEMP=%q\n' "${TMP_DIR}"
  printf 'export CPLUS_INCLUDE_PATH=%q${CPLUS_INCLUDE_PATH:+:${CPLUS_INCLUDE_PATH}}\n' "${GCC_COMPAT_INCLUDE}"
  printf 'export LIBRARY_PATH=%q${LIBRARY_PATH:+:${LIBRARY_PATH}}\n' "${GCC_LIBRARY_PATH}"
  printf 'export COMPILER_PATH=%q${COMPILER_PATH:+:${COMPILER_PATH}}\n' "${GCC_COMPILER_PATH}"
  echo
  emit_grasu_compile_command \
    "${CFG_DIR}/bin_search_compile.cfg" \
    "${BUILD_DIR}/bin_search.${TARGET}.xo" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_bin_search.cpp"
  emit_grasu_compile_command \
    "${CFG_DIR}/dispatch_compile.cfg" \
    "${BUILD_DIR}/dispatch.${TARGET}.xo" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_dispatch.cpp"
  emit_grasu_compile_command \
    "${CFG_DIR}/process_cache_token_compile.cfg" \
    "${BUILD_DIR}/process_cache.${TARGET}.xo" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_process_cache.cpp" \
    "-DGRASU_ENABLE_COMPLETION_TOKEN"
  emit_grasu_compile_command \
    "${CFG_DIR}/process_ddr_token_compile.cfg" \
    "${BUILD_DIR}/process_ddr.${TARGET}.xo" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_process_ddr.cpp" \
    "-DGRASU_ENABLE_COMPLETION_TOKEN"
  emit_regraph_compile_command \
    "${REGRAPH_ROOT}/acc_template/kernel_apply" \
    "${CFG_DIR}/kernelApply_compile.cfg" \
    "${BUILD_DIR}/kernelApply.${TARGET}.${PLATFORM}.xo" \
    "${REGRAPH_ROOT}/acc_template/kernel_apply/kernel_apply.cpp"
  emit_regraph_compile_command \
    "${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper" \
    "${CFG_DIR}/kernelHBMWrapper_compile.cfg" \
    "${BUILD_DIR}/kernelHBMWrapper.${TARGET}.${PLATFORM}.xo" \
    "${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper/kernel_hbm_wrapper.cpp"
  emit_regraph_compile_command \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs_merger" \
    "${CFG_DIR}/kernelLittleGSMerger_compile.cfg" \
    "${BUILD_DIR}/kernelLittleGSMerger.${TARGET}.${PLATFORM}.xo" \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs_merger/kernel_little_gs_merger.cpp"
  emit_regraph_compile_command \
    "${REGRAPH_ROOT}/acc_template/kernel_big_gs" \
    "${CFG_DIR}/bigKernelScatterGather_compile.cfg" \
    "${BUILD_DIR}/bigKernelScatterGather.${TARGET}.${PLATFORM}.xo" \
    "${REGRAPH_ROOT}/acc_template/kernel_big_gs/kernel_scatter_gather.cpp"
  emit_regraph_compile_command \
    "${REGRAPH_ROOT}/acc_template/kernel_big_gs_merger" \
    "${CFG_DIR}/kernelBigGSMerger_compile.cfg" \
    "${BUILD_DIR}/kernelBigGSMerger.${TARGET}.${PLATFORM}.xo" \
    "${REGRAPH_ROOT}/acc_template/kernel_big_gs_merger/kernel_big_gs_merger.cpp"
  printf 'v++ --target %q --compile %s %s --config %q -I%q -o %q %q\n' \
    "${TARGET}" "${SW_EMU_GTHREAD_DEFINE}" "${REGRAPH_TARGET_DEFINE}" "${CFG_DIR}/pma_completion_barrier_compile.cfg" \
    "${HLS_INCLUDE_ETC}" \
    "${BUILD_DIR}/pma_completion_barrier.${TARGET}.xo" \
    "${GRI_ROOT}/kernels/pma_completion_barrier/pma_completion_barrier.cpp"
  printf 'v++ --target %q --compile %s %s --config %q -I%q -o %q %q\n' \
    "${TARGET}" "${SW_EMU_GTHREAD_DEFINE}" "${REGRAPH_TARGET_DEFINE}" "${CFG_DIR}/pma_to_regraph_adapter_compile.cfg" \
    "${HLS_INCLUDE_ETC}" \
    "${BUILD_DIR}/pma_to_regraph_adapter.${TARGET}.xo" \
    "${GRI_ROOT}/kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
  printf 'v++ --target %q --compile %s %s -O3 --config %q -DHAVE_EDGE_PROP=1 -DHAVE_UNSIGNED_PROP=1 -DHAVE_APPLY_OUTDEG=0 -DHAVE_VERTEX_PROP=1 -DPARTITION_SIZE=65536 -DLITTLE_KERNEL_DST_BUFFER_SIZE=65536 -DBIG_KERNEL_DST_BUFFER_SIZE=524288 -DSRC_BUFFER_SIZE=4096 -DLOG2_SRC_BUFFER_SIZE=12 -DVERTEX_REORDER_ENABLE=1 -DENABLE_COMPRESSED_EDGE_INPUT=0 -DBIG_KERNEL_NUM=1 -DLITTLE_KERNEL_NUM=1 -I%q -I%q -I%q -I%q -I%q -I%q -I%q -o %q %q\n' \
    "${TARGET}" "${SW_EMU_GTHREAD_DEFINE}" "${REGRAPH_TARGET_DEFINE}" "${CFG_DIR}/little_gs_stream_compile.cfg" \
    "${HLS_INCLUDE_ETC}" \
    "${REGRAPH_ROOT}/acc_udfs/sssp" "${REGRAPH_ROOT}" "${REGRAPH_ROOT}/acc_template" \
    "${REGRAPH_ROOT}/acc_template/common" "${REGRAPH_ROOT}/acc_udfs" \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs" \
    "${BUILD_DIR}/lksg_stream.${TARGET}.xo" \
    "${GRI_ROOT}/kernels/regraph_stream_little_gs/little_gs_stream.cpp"
} > "${COMPILE_COMMANDS}"
chmod +x "${COMPILE_COMMANDS}"

{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  printf 'export TMPDIR=%q\n' "${TMP_DIR}"
  printf 'export TMP=%q\n' "${TMP_DIR}"
  printf 'export TEMP=%q\n' "${TMP_DIR}"
  printf 'export CPLUS_INCLUDE_PATH=%q${CPLUS_INCLUDE_PATH:+:${CPLUS_INCLUDE_PATH}}\n' "${GCC_COMPAT_INCLUDE}"
  printf 'export LIBRARY_PATH=%q${LIBRARY_PATH:+:${LIBRARY_PATH}}\n' "${GCC_LIBRARY_PATH}"
  printf 'export COMPILER_PATH=%q${COMPILER_PATH:+:${COMPILER_PATH}}\n' "${GCC_COMPILER_PATH}"
  printf 'v++ --target %q --link --kernel_frequency %q --config %q -D_GTHREAD_USE_COND_INIT_FUNC' \
    "${TARGET}" "${KERNEL_FREQ}" "${LINK_CFG}"
  for inc in \
    "${REGRAPH_ROOT}/acc_udfs/sssp" \
    "${REGRAPH_ROOT}" \
    "${REGRAPH_ROOT}/acc_template" \
    "${REGRAPH_ROOT}/acc_template/common" \
    "${REGRAPH_ROOT}/acc_udfs" \
    "${REGRAPH_ROOT}/acc_template/kernel_apply" \
    "${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper" \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs_merger" \
    "${REGRAPH_ROOT}/acc_template/kernel_big_gs" \
    "${REGRAPH_ROOT}/acc_template/kernel_big_gs_merger"; do
    if [[ -d "${inc}" ]]; then
      printf ' -I%q' "${inc}"
    fi
  done
  printf ' -o %q' "${OUT_XCLBIN}"
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
  echo "HLS_INCLUDE=${HLS_INCLUDE}"
  echo "HLS_INCLUDE_ETC=${HLS_INCLUDE_ETC}"
  echo "SW_EMU_GTHREAD_DEFINE=${SW_EMU_GTHREAD_DEFINE}"
  printf 'GRASU_BASE_FLAGS='
  printf '%q ' "${GRASU_BASE_FLAGS[@]}"
  printf '\n'
  echo "REGRAPH_TARGET_DEFINE=${REGRAPH_TARGET_DEFINE}"
  printf 'REGRAPH_COMMON_FLAGS='
  printf '%q ' "${REGRAPH_COMMON_FLAGS[@]}"
  printf '\n'
  echo "BUILD_ROOT=${BUILD_ROOT}"
  echo "TMP_DIR=${TMP_DIR}"
  echo "GCC_COMPAT_INCLUDE=${GCC_COMPAT_INCLUDE}"
  echo "GCC_LIBRARY_PATH=${GCC_LIBRARY_PATH}"
  echo "GCC_COMPILER_PATH=${GCC_COMPILER_PATH}"
  echo "GRASU_BUILD_ROOT=${GRASU_BUILD_ROOT}"
  echo "REGRAPH_XCLBIN_DIR=${REGRAPH_XCLBIN_DIR}"
  echo "REGRAPH_LINK_ROOT=${REGRAPH_LINK_ROOT}"
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
