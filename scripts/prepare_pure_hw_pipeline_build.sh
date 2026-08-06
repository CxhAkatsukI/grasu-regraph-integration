#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="sw_emu"
PIPELINE_MODE="compactor"
ALGORITHM="weighted_sssp"
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

Prepare reproducible Vitis compile/link commands for a GraSU -> ReGraph
pipeline. This script is generate-only; it does not run v++.

Options:
  --target sw_emu|hw_emu|hw      Build target. Default: ${TARGET}
  --pipeline-mode MODE           compactor, weighted-axis, or sharded-k4.
                                 Default: ${PIPELINE_MODE}
  --algorithm NAME               weighted_sssp or connected_components.
  --platform NAME                Platform name. Default: ${PLATFORM}
  --platform-xpfm PATH           Platform xpfm. Default: ${PLATFORM_XPFM}
  --kernel-frequency MHz         Link frequency. Default: ${KERNEL_FREQ}
  --max-cache-segment N          GraSU max cache segment. Default: ${MAX_CACHE_SEGMENT}
  --hls-include PATH             Vitis HLS include directory. Default: ${HLS_INCLUDE}
  --hls-include-etc PATH         Vitis HLS include/etc directory. Default: ${HLS_INCLUDE_ETC}
  --build-root PATH              Output root. Default depends on pipeline mode.
  --grasu-build-root PATH        Existing GraSU build root for bin_search/dispatch XOs.
  --regraph-xclbin-dir PATH      Existing ReGraph SSSP XO directory for non-little-GS XOs.
  -h, --help                     Show this help.

Generated files:
  compile_commands.sh            Compile tokenized GraSU, selected handoff, and
                                 ReGraph little-GS XOs.
  link_command.sh                Link the pure pipeline xclbin.
  config/<pipeline>_<target>.cfg
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
    --pipeline-mode) PIPELINE_MODE="$2"; shift 2 ;;
    --algorithm) ALGORITHM="$2"; shift 2 ;;
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
case "${PIPELINE_MODE}" in
  compactor|weighted-axis|sharded-k4) ;;
  *) echo "Invalid --pipeline-mode: ${PIPELINE_MODE}" >&2; exit 2 ;;
esac
case "${ALGORITHM}" in
  weighted_sssp|connected_components) ;;
  *) echo "Invalid --algorithm: ${ALGORITHM}" >&2; exit 2 ;;
esac
if [[ "${ALGORITHM}" == "connected_components" &&
      "${PIPELINE_MODE}" == "compactor" ]]; then
  echo "connected_components requires --pipeline-mode weighted-axis or sharded-k4" >&2
  exit 2
fi

if [[ -z "${BUILD_ROOT}" ]]; then
  if [[ "${PIPELINE_MODE}" == "compactor" ]]; then
    BUILD_ROOT="${GRI_ROOT}/.tmp_build/pure_pipeline_${TARGET}_$(date +%Y%m%d_%H%M%S)"
  else
    BUILD_ROOT="${GRI_ROOT}/.tmp_build/weighted_pma_native_${TARGET}_$(date +%Y%m%d_%H%M%S)"
  fi
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
GCC_SYSTEM_INCLUDE_PATH="/usr/include/x86_64-linux-gnu:/usr/include"
GCC_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu"
GCC_COMPILER_PATH="/usr/bin"
mkdir -p "${BUILD_DIR}" "${CFG_DIR}" "${LOG_DIR}" "${REPORT_DIR}" "${BUILD_ROOT}/ip_cache" "${TMP_DIR}" "${GCC_COMPAT_INCLUDE}/bits"

{
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

if [[ "${ALGORITHM}" == "connected_components" ]]; then
  REGRAPH_EDGE_PROP=0
  REGRAPH_UDF_INCLUDE="${GRI_ROOT}/include/regraph_cc"
  ADAPTER_MODE_DEFINE="-DGRASU_REGRAPH_DESTINATION_ONLY=1"
else
  REGRAPH_EDGE_PROP=1
  REGRAPH_UDF_INCLUDE="${REGRAPH_ROOT}/acc_udfs/sssp"
  ADAPTER_MODE_DEFINE="-DGRASU_REGRAPH_WEIGHTED_PMA=1"
fi
SHARDED_PMA_DEFINE=""
if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
  SHARDED_PMA_DEFINE="-DGRASU_REGRAPH_SHARDED_PMA=1"
fi

declare -a REGRAPH_COMMON_FLAGS=(
  "${SW_EMU_GTHREAD_DEFINE}"
  "-O3"
  "-DHAVE_EDGE_PROP=${REGRAPH_EDGE_PROP}"
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
  "-DBIG_KERNEL_NUM=0"
  "-DLITTLE_KERNEL_NUM=1"
  "-DREGRAPH_PURE_LITTLE_ONLY"
  "-I${HLS_INCLUDE_ETC}"
  "-I${REGRAPH_UDF_INCLUDE}"
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

copy_connectivity_body_without_memory() {
  local file="$1"
  awk '
    BEGIN { in_conn = 0 }
    /^\[connectivity\]/ { in_conn = 1; next }
    in_conn == 1 && $0 !~ /^sp=/ { print }
  ' "${file}"
}

write_regraph_little_only_connectivity() {
  local file="$1"
  awk '
    BEGIN { in_conn = 0 }
    /^\[connectivity\]/ { in_conn = 1; next }
    in_conn == 0 { next }
    /bigKernelScatterGather/ { next }
    /kernelBigGSMerger/ { next }
    /b_cacheline/ { next }
    /b_tmp_prop/ { next }
    /b_write_burst/ { next }
    /b_merged_prop/ { next }
    { print }
  ' "${file}"
}

write_regraph_stream_little_only_connectivity() {
  local file="$1"
  awk '
    BEGIN { in_conn = 0 }
    /^\[connectivity\]/ { in_conn = 1; next }
    in_conn == 0 { next }
    /bigKernelScatterGather/ { next }
    /kernelBigGSMerger/ { next }
    /b_cacheline/ { next }
    /b_tmp_prop/ { next }
    /b_write_burst/ { next }
    /b_merged_prop/ { next }
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
write_compile_cfg pma_completion_barrier "${CFG_DIR}/pma_completion_barrier_compile.cfg"
if [[ "${PIPELINE_MODE}" == "compactor" ]]; then
  write_compile_cfg pma_to_regraph_edge_array "${CFG_DIR}/pma_to_regraph_edge_array_compile.cfg"
  write_compile_cfg littleKernelScatterGather "${CFG_DIR}/littleKernelScatterGather_compile.cfg"
else
  write_compile_cfg pma_to_regraph_adapter "${CFG_DIR}/pma_to_regraph_adapter_compile.cfg"
  write_compile_cfg lksg_stream "${CFG_DIR}/little_gs_stream_compile.cfg"
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    write_compile_cfg regraph_frontend_mux "${CFG_DIR}/regraph_frontend_mux_compile.cfg"
  fi
fi

emit_regraph_compile_command() {
  local kernel_dir="$1"
  local cfg="$2"
  local out="$3"
  local src="$4"
  shift 4
  printf 'v++ --target %q --compile --kernel_frequency %q' \
    "${TARGET}" "${KERNEL_FREQ}"
  for flag in "${REGRAPH_COMMON_FLAGS[@]}"; do
    printf ' %q' "${flag}"
  done
  for include_dir in "$@"; do
    printf ' -I%q' "${include_dir}"
  done
  printf ' --config %q -I%q -o %q %q\n' \
    "${cfg}" "${kernel_dir}" "${out}" "${src}"
}

emit_regraph_k4_wrapper_compile_command() {
  local cfg="$1"
  local out="$2"
  local src="$3"
  printf 'v++ --target %q --compile --kernel_frequency %q' \
    "${TARGET}" "${KERNEL_FREQ}"
  for flag in "${REGRAPH_COMMON_FLAGS[@]}"; do
    if [[ "${flag}" != "-DLITTLE_KERNEL_NUM=1" ]]; then
      printf ' %q' "${flag}"
    fi
  done
  printf ' %q --config %q -I%q -I%q -o %q %q\n' \
    "-DLITTLE_KERNEL_NUM=4" "${cfg}" \
    "${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper" \
    "${HLS_INCLUDE_ETC}" "${out}" "${src}"
}

emit_grasu_compile_command() {
  local cfg="$1"
  local out="$2"
  local src="$3"
  shift 3
  printf 'v++ --target %q --compile --kernel_frequency %q' \
    "${TARGET}" "${KERNEL_FREQ}"
  for flag in "${GRASU_BASE_FLAGS[@]}" "$@"; do
    printf ' %q' "${flag}"
  done
  printf ' --config %q -o %q %q\n' "${cfg}" "${out}" "${src}"
}

git_head_or_unavailable() {
  local repo="$1"
  git -C "${repo}" rev-parse HEAD 2>/dev/null || printf 'not_available\n'
}

git_tracked_dirty_or_unavailable() {
  local repo="$1"
  if ! git -C "${repo}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'not_available\n'
  elif ! git -C "${repo}" diff --quiet ||
       ! git -C "${repo}" diff --cached --quiet; then
    printf '1\n'
  else
    printf '0\n'
  fi
}

git_untracked_count_or_unavailable() {
  local repo="$1"
  if ! git -C "${repo}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'not_available\n'
  else
    git -C "${repo}" ls-files --others --exclude-standard | wc -l
  fi
}

emit_input_record() {
  local role="$1"
  local path="$2"
  if [[ -f "${path}" ]]; then
    printf '%s\tpresent\t' "${role}"
    sha256sum "${path}" | awk '{printf "%s\t", $1}'
    stat --printf '%s\t%n\n' "${path}"
  else
    printf '%s\tmissing\t-\t-\t%s\n' "${role}" "${path}"
  fi
}

if [[ "${PIPELINE_MODE}" == "compactor" ]]; then
  PIPELINE_STEM="pure_pipeline"
  CLAIM_CLASS="native_hls_aligned_with_conversion"
  HANDOFF="capacity_wide_compactor_to_edge_array"
  CONVERSION_COST="included"
else
  if [[ "${ALGORITHM}" == "connected_components" ]]; then
    PIPELINE_STEM="connected_components_pma_native"
  else
    PIPELINE_STEM="weighted_pma_native"
  fi
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    PIPELINE_STEM="${PIPELINE_STEM}_sharded_k4"
    CLAIM_CLASS="candidate_sharded_k4_hls_not_yet_built"
    HANDOFF="four_sharded_pma_source_gather_frontends_to_one_regraph_downstream"
  else
    CLAIM_CLASS="candidate_hls_not_yet_built"
    HANDOFF="weighted_pma_to_axis_stream"
  fi
  CONVERSION_COST="absent"
fi
LINK_CFG="${CFG_DIR}/${PIPELINE_STEM}_${TARGET}.cfg"
OUT_XCLBIN="${BUILD_DIR}/grasu_regraph_${PIPELINE_STEM}.${TARGET}.xclbin"
COMPILE_COMMANDS="${BUILD_ROOT}/compile_commands.sh"
LINK_COMMAND="${BUILD_ROOT}/link_command.sh"
MANIFEST="${BUILD_ROOT}/manifest.env"
INPUTS="${BUILD_ROOT}/inputs.tsv"

{
  echo "platform=${PLATFORM_XPFM}"
  echo "save-temps=1"
  echo "messageDb=${BUILD_DIR}/grasu_regraph_${PIPELINE_STEM}.mdb"
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
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    copy_connectivity_body_without_memory "${GRASU_LINK_CFG}"
    lane_ranges=("0:5" "6:11" "12:17" "18:22")
    for index in 1 2 3 4; do
      echo "sp=bin_search_${index}.edges:HBM[${lane_ranges[$((index - 1))]}]"
      echo "sp=bin_search_${index}.binary_0:HBM[0:22]"
      echo "sp=bin_search_${index}.row_offset_0:HBM[0:22]"
    done
    echo "sp=process_cache_1.pma_cache:HBM[0:5]"
    echo "sp=process_cache_2.pma_cache:HBM[12:17]"
    for port in pma_in0_ddr pma_in1_ddr pma_out0_ddr pma_out1_ddr; do
      echo "sp=process_ddr_1.${port}:HBM[6:11]"
      echo "sp=process_ddr_2.${port}:HBM[18:22]"
    done
  else
    copy_connectivity_body "${GRASU_LINK_CFG}"
  fi
  echo
  echo "# GraSU internal update streams"
  copy_connectivity_body "${GRASU_STREAM_CFG}"
  echo
  echo "# GraSU PMA completion barrier into selected handoff"
  echo "stream_connect=process_cache_1.completion_token:pma_completion_barrier_1.done0:16"
  echo "stream_connect=process_ddr_1.completion_token:pma_completion_barrier_1.done1:16"
  echo "stream_connect=process_cache_2.completion_token:pma_completion_barrier_1.done2:16"
  echo "stream_connect=process_ddr_2.completion_token:pma_completion_barrier_1.done3:16"
  echo
  echo "# PMA completion barrier"
  echo "nk=pma_completion_barrier:1:pma_completion_barrier_1"
  echo "slr=pma_completion_barrier_1:SLR1"
  if [[ "${PIPELINE_MODE}" == "compactor" ]]; then
    echo
    echo "# One-shot PMA-to-ReGraph edge-array compactor"
    echo "nk=pma_to_regraph_edge_array:1:pma_to_regraph_edge_array_1"
    echo "sp=pma_to_regraph_edge_array_1.pma0:HBM[0]"
    echo "sp=pma_to_regraph_edge_array_1.pma1:HBM[1]"
    echo "sp=pma_to_regraph_edge_array_1.pma2:HBM[2]"
    echo "sp=pma_to_regraph_edge_array_1.pma3:HBM[3]"
    echo "sp=pma_to_regraph_edge_array_1.row_offset:HBM[0]"
    echo "sp=pma_to_regraph_edge_array_1.edge_array:HBM[0]"
    echo "slr=pma_to_regraph_edge_array_1:SLR1"
    echo
    echo "# ReGraph SSSP connectivity with compact edge-array little-only GS"
    write_regraph_little_only_connectivity "${REGRAPH_CONNECTIVITY_CFG}"
    echo "sp=kernelApply_1.active_count:HBM[30]"
  elif [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    echo
    echo "# Four destination-sharded PMA frontends with one shared downstream"
    echo "nk=pma_to_regraph_adapter:4:pma_to_regraph_adapter_1.pma_to_regraph_adapter_2.pma_to_regraph_adapter_3.pma_to_regraph_adapter_4"
    echo "nk=lksg_stream:4:lksg_stream_1.lksg_stream_2.lksg_stream_3.lksg_stream_4"
    for index in 1 2 3 4; do
      echo "sp=pma_to_regraph_adapter_${index}.pma0:HBM[0:22]"
      echo "slr=pma_to_regraph_adapter_${index}:SLR$(((index - 1) % 3))"
      echo "slr=lksg_stream_${index}:SLR$(((index - 1) % 3))"
      echo "stream_connect=pma_to_regraph_adapter_${index}.edge_burst_out:lksg_stream_${index}.edge_burst_in:32"
      echo "stream_connect=lksg_stream_${index}.l_ppb_request_stm:kernelHBMWrapper_1.l_ppb_request_stm_${index}:16"
      echo "stream_connect=kernelHBMWrapper_1.l_ppb_response_stm_${index}:lksg_stream_${index}.l_ppb_response_stm:16"
      echo "stream_connect=lksg_stream_${index}.l_tmp_prop_stm:regraph_frontend_mux_1.input$((index - 1)):32"
    done
    echo "nk=regraph_frontend_mux:1:regraph_frontend_mux_1"
    echo "slr=regraph_frontend_mux_1:SLR1"
    echo "stream_connect=regraph_frontend_mux_1.output:kernelLittleGSMerger_1.l_tmp_prop_stm_1:32"
    echo
    echo "# One shared ReGraph ${ALGORITHM} downstream"
    write_regraph_stream_little_only_connectivity "${REGRAPH_CONNECTIVITY_CFG}" |
      awk '$0 !~ /lksg_stream_1/ && $0 !~ /^sp=kernelHBMWrapper_1\./ && $0 !~ /^sp=kernelApply_1\./ { print }'
    echo "sp=kernelHBMWrapper_1.src_prop_1:HBM[23]"
    echo "sp=kernelHBMWrapper_1.src_prop_2:HBM[24]"
    echo "sp=kernelHBMWrapper_1.src_prop_3:HBM[23]"
    echo "sp=kernelHBMWrapper_1.src_prop_4:HBM[24]"
    echo "sp=kernelHBMWrapper_1.new_prop_1:HBM[23]"
    echo "sp=kernelHBMWrapper_1.new_prop_2:HBM[24]"
    echo "sp=kernelApply_1.vertex_prop:HBM[30]"
    echo "sp=kernelApply_1.active_count:HBM[30]"
  else
    echo "stream_connect=pma_to_regraph_adapter_1.edge_burst_out:lksg_stream_1.edge_burst_in:32"
    echo
    echo "# Weighted PMA-to-ReGraph direct AXIS adapter"
    echo "nk=pma_to_regraph_adapter:1:pma_to_regraph_adapter_1"
    echo "sp=pma_to_regraph_adapter_1.pma0:HBM[0]"
    echo "sp=pma_to_regraph_adapter_1.pma1:HBM[1]"
    echo "sp=pma_to_regraph_adapter_1.pma2:HBM[2]"
    echo "sp=pma_to_regraph_adapter_1.pma3:HBM[3]"
    echo "sp=pma_to_regraph_adapter_1.row_offset:HBM[0]"
    echo "slr=pma_to_regraph_adapter_1:SLR1"
    echo
    echo "# ReGraph ${ALGORITHM} connectivity with stream-input little-only GS"
    write_regraph_stream_little_only_connectivity "${REGRAPH_CONNECTIVITY_CFG}"
    echo "sp=kernelApply_1.active_count:HBM[30]"
  fi
} > "${LINK_CFG}"

declare -a EXISTING_XOS=()

declare -a GENERATED_XOS=(
  "${BUILD_DIR}/bin_search.${TARGET}.xo"
  "${BUILD_DIR}/dispatch.${TARGET}.xo"
  "${BUILD_DIR}/kernelApply.${TARGET}.${PLATFORM}.xo"
  "${BUILD_DIR}/kernelHBMWrapper.${TARGET}.${PLATFORM}.xo"
  "${BUILD_DIR}/kernelLittleGSMerger.${TARGET}.${PLATFORM}.xo"
  "${BUILD_DIR}/process_cache.${TARGET}.xo"
  "${BUILD_DIR}/process_ddr.${TARGET}.xo"
  "${BUILD_DIR}/pma_completion_barrier.${TARGET}.xo"
)
if [[ "${PIPELINE_MODE}" == "compactor" ]]; then
  GENERATED_XOS+=(
    "${BUILD_DIR}/pma_to_regraph_edge_array.${TARGET}.xo"
    "${BUILD_DIR}/littleKernelScatterGather.${TARGET}.xo"
  )
else
  GENERATED_XOS+=(
    "${BUILD_DIR}/pma_to_regraph_adapter.${TARGET}.xo"
    "${BUILD_DIR}/lksg_stream.${TARGET}.xo"
  )
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    GENERATED_XOS+=("${BUILD_DIR}/regraph_frontend_mux.${TARGET}.xo")
  fi
fi

{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  printf 'export TMPDIR=%q\n' "${TMP_DIR}"
  printf 'export TMP=%q\n' "${TMP_DIR}"
  printf 'export TEMP=%q\n' "${TMP_DIR}"
  printf 'export CPATH=%q${CPATH:+:${CPATH}}\n' "${GCC_SYSTEM_INCLUDE_PATH}"
  printf 'export C_INCLUDE_PATH=%q${C_INCLUDE_PATH:+:${C_INCLUDE_PATH}}\n' "${GCC_SYSTEM_INCLUDE_PATH}"
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
    "-DGRASU_ENABLE_COMPLETION_TOKEN" \
    "-DGRASU_PURE_PIPELINE_DIRECT_CACHE"
  emit_grasu_compile_command \
    "${CFG_DIR}/process_ddr_token_compile.cfg" \
    "${BUILD_DIR}/process_ddr.${TARGET}.xo" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_process_ddr.cpp" \
    "-DGRASU_ENABLE_COMPLETION_TOKEN"
  emit_regraph_compile_command \
    "${REGRAPH_ROOT}/acc_template/kernel_apply" \
    "${CFG_DIR}/kernelApply_compile.cfg" \
    "${BUILD_DIR}/kernelApply.${TARGET}.${PLATFORM}.xo" \
    "${GRI_ROOT}/kernels/regraph_sssp_apply_status/kernel_apply.cpp"
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    emit_regraph_k4_wrapper_compile_command \
      "${CFG_DIR}/kernelHBMWrapper_compile.cfg" \
      "${BUILD_DIR}/kernelHBMWrapper.${TARGET}.${PLATFORM}.xo" \
      "${GRI_ROOT}/kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp"
  else
    emit_regraph_compile_command \
      "${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper" \
      "${CFG_DIR}/kernelHBMWrapper_compile.cfg" \
      "${BUILD_DIR}/kernelHBMWrapper.${TARGET}.${PLATFORM}.xo" \
      "${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper/kernel_hbm_wrapper.cpp"
  fi
  emit_regraph_compile_command \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs_merger" \
    "${CFG_DIR}/kernelLittleGSMerger_compile.cfg" \
    "${BUILD_DIR}/kernelLittleGSMerger.${TARGET}.${PLATFORM}.xo" \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs_merger/kernel_little_gs_merger.cpp"
  printf 'v++ --target %q --compile --kernel_frequency %q %s %s --config %q -I%q -o %q %q\n' \
    "${TARGET}" "${KERNEL_FREQ}" "${SW_EMU_GTHREAD_DEFINE}" "${REGRAPH_TARGET_DEFINE}" "${CFG_DIR}/pma_completion_barrier_compile.cfg" \
    "${HLS_INCLUDE_ETC}" \
    "${BUILD_DIR}/pma_completion_barrier.${TARGET}.xo" \
    "${GRI_ROOT}/kernels/pma_completion_barrier/pma_completion_barrier.cpp"
  if [[ "${PIPELINE_MODE}" == "compactor" ]]; then
    printf 'v++ --target %q --compile --kernel_frequency %q %s %s --config %q -I%q -o %q %q\n' \
      "${TARGET}" "${KERNEL_FREQ}" "${SW_EMU_GTHREAD_DEFINE}" "${REGRAPH_TARGET_DEFINE}" "${CFG_DIR}/pma_to_regraph_edge_array_compile.cfg" \
      "${HLS_INCLUDE_ETC}" \
      "${BUILD_DIR}/pma_to_regraph_edge_array.${TARGET}.xo" \
      "${GRI_ROOT}/kernels/pma_to_regraph_edge_array/pma_to_regraph_edge_array.cpp"
    emit_regraph_compile_command \
      "${REGRAPH_ROOT}/acc_template/kernel_little_gs" \
      "${CFG_DIR}/littleKernelScatterGather_compile.cfg" \
      "${BUILD_DIR}/littleKernelScatterGather.${TARGET}.xo" \
      "${REGRAPH_ROOT}/acc_template/kernel_little_gs/kernel_scatter_gather.cpp"
  else
      adapter_memory_define=""
      if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
        adapter_memory_define="-DGRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS=1"
      fi
      printf 'v++ --target %q --compile --kernel_frequency %q %s %s %s %s %s --config %q -I%q -o %q %q\n' \
        "${TARGET}" "${KERNEL_FREQ}" "${SW_EMU_GTHREAD_DEFINE}" "${REGRAPH_TARGET_DEFINE}" "${ADAPTER_MODE_DEFINE}" "${SHARDED_PMA_DEFINE}" "${adapter_memory_define}" "${CFG_DIR}/pma_to_regraph_adapter_compile.cfg" \
      "${HLS_INCLUDE_ETC}" \
      "${BUILD_DIR}/pma_to_regraph_adapter.${TARGET}.xo" \
      "${GRI_ROOT}/kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
    if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
      printf 'v++ --target %q --compile --kernel_frequency %q %s %s --config %q -I%q -o %q %q\n' \
        "${TARGET}" "${KERNEL_FREQ}" "${SW_EMU_GTHREAD_DEFINE}" "${REGRAPH_TARGET_DEFINE}" \
        "${CFG_DIR}/regraph_frontend_mux_compile.cfg" "${HLS_INCLUDE_ETC}" \
        "${BUILD_DIR}/regraph_frontend_mux.${TARGET}.xo" \
        "${GRI_ROOT}/kernels/regraph_frontend_mux/regraph_frontend_mux.cpp"
    fi
    emit_regraph_compile_command \
      "${GRI_ROOT}/kernels/regraph_stream_little_gs" \
      "${CFG_DIR}/little_gs_stream_compile.cfg" \
      "${BUILD_DIR}/lksg_stream.${TARGET}.xo" \
      "${GRI_ROOT}/kernels/regraph_stream_little_gs/little_gs_stream.cpp" \
      "${REGRAPH_ROOT}/acc_template/kernel_little_gs"
  fi
} > "${COMPILE_COMMANDS}"
chmod +x "${COMPILE_COMMANDS}"

{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  printf 'export TMPDIR=%q\n' "${TMP_DIR}"
  printf 'export TMP=%q\n' "${TMP_DIR}"
  printf 'export TEMP=%q\n' "${TMP_DIR}"
  printf 'export CPATH=%q${CPATH:+:${CPATH}}\n' "${GCC_SYSTEM_INCLUDE_PATH}"
  printf 'export C_INCLUDE_PATH=%q${C_INCLUDE_PATH:+:${C_INCLUDE_PATH}}\n' "${GCC_SYSTEM_INCLUDE_PATH}"
  printf 'export CPLUS_INCLUDE_PATH=%q${CPLUS_INCLUDE_PATH:+:${CPLUS_INCLUDE_PATH}}\n' "${GCC_COMPAT_INCLUDE}"
  printf 'export LIBRARY_PATH=%q${LIBRARY_PATH:+:${LIBRARY_PATH}}\n' "${GCC_LIBRARY_PATH}"
  printf 'export COMPILER_PATH=%q${COMPILER_PATH:+:${COMPILER_PATH}}\n' "${GCC_COMPILER_PATH}"
  printf 'v++ --target %q --link --kernel_frequency %q --config %q -D_GTHREAD_USE_COND_INIT_FUNC' \
    "${TARGET}" "${KERNEL_FREQ}" "${LINK_CFG}"
  for inc in \
    "${REGRAPH_UDF_INCLUDE}" \
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
  echo "GRI_GIT_HEAD=$(git_head_or_unavailable "${GRI_ROOT}")"
  echo "GRI_GIT_TRACKED_DIRTY=$(git_tracked_dirty_or_unavailable "${GRI_ROOT}")"
  echo "GRI_GIT_UNTRACKED_COUNT=$(git_untracked_count_or_unavailable "${GRI_ROOT}")"
  echo "GRASU_GIT_HEAD=$(git_head_or_unavailable "${GRASU_ROOT}")"
  echo "GRASU_GIT_TRACKED_DIRTY=$(git_tracked_dirty_or_unavailable "${GRASU_ROOT}")"
  echo "GRASU_GIT_UNTRACKED_COUNT=$(git_untracked_count_or_unavailable "${GRASU_ROOT}")"
  echo "REGRAPH_GIT_HEAD=$(git_head_or_unavailable "${REGRAPH_ROOT}")"
  echo "REGRAPH_GIT_TRACKED_DIRTY=$(git_tracked_dirty_or_unavailable "${REGRAPH_ROOT}")"
  echo "REGRAPH_GIT_UNTRACKED_COUNT=$(git_untracked_count_or_unavailable "${REGRAPH_ROOT}")"
  echo "TARGET=${TARGET}"
  echo "ALGORITHM=${ALGORITHM}"
  echo "PIPELINE_MODE=${PIPELINE_MODE}"
  echo "PIPELINE_STEM=${PIPELINE_STEM}"
  echo "CLAIM_CLASS=${CLAIM_CLASS}"
  echo "HANDOFF=${HANDOFF}"
  echo "CONVERSION_COST=${CONVERSION_COST}"
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
  echo "REGRAPH_UDF_INCLUDE=${REGRAPH_UDF_INCLUDE}"
  echo "REGRAPH_EDGE_PROP=${REGRAPH_EDGE_PROP}"
  echo "ADAPTER_MODE_DEFINE=${ADAPTER_MODE_DEFINE}"
  echo "SHARDED_PMA_DEFINE=${SHARDED_PMA_DEFINE}"
  echo "PMA_FRONTEND_CUS=$([[ "${PIPELINE_MODE}" == "sharded-k4" ]] && echo 4 || echo 1)"
  echo "SHARED_REGRAPH_DOWNSTREAM=1"
  printf 'REGRAPH_COMMON_FLAGS='
  printf '%q ' "${REGRAPH_COMMON_FLAGS[@]}"
  printf '\n'
  echo "BUILD_ROOT=${BUILD_ROOT}"
  echo "TMP_DIR=${TMP_DIR}"
  echo "GCC_COMPAT_INCLUDE=${GCC_COMPAT_INCLUDE}"
  echo "GCC_SYSTEM_INCLUDE_PATH=${GCC_SYSTEM_INCLUDE_PATH}"
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
  emit_input_record generator_source "${GRI_ROOT}/scripts/prepare_pure_hw_pipeline_build.sh"
  emit_input_record config_input "${GRASU_LINK_CFG}"
  emit_input_record config_input "${GRASU_STREAM_CFG}"
  emit_input_record config_input "${REGRAPH_CONNECTIVITY_CFG}"
  for source in \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_bin_search.cpp" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_dispatch.cpp" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_process_cache.cpp" \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src/kernel_process_ddr.cpp" \
    "${GRI_ROOT}/kernels/regraph_sssp_apply_status/kernel_apply.cpp" \
    "${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper/kernel_hbm_wrapper.cpp" \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs_merger/kernel_little_gs_merger.cpp" \
    "${GRI_ROOT}/kernels/pma_completion_barrier/pma_completion_barrier.cpp"; do
    emit_input_record kernel_source "${source}"
  done
  if [[ "${PIPELINE_MODE}" == "compactor" ]]; then
    emit_input_record kernel_source \
      "${GRI_ROOT}/kernels/pma_to_regraph_edge_array/pma_to_regraph_edge_array.cpp"
    emit_input_record kernel_source \
      "${REGRAPH_ROOT}/acc_template/kernel_little_gs/kernel_scatter_gather.cpp"
  else
    emit_input_record kernel_source \
      "${GRI_ROOT}/kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
    emit_input_record kernel_source \
      "${GRI_ROOT}/kernels/regraph_stream_little_gs/little_gs_stream.cpp"
    if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
      emit_input_record kernel_source \
        "${GRI_ROOT}/kernels/regraph_frontend_mux/regraph_frontend_mux.cpp"
      emit_input_record kernel_source \
        "${GRI_ROOT}/kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp"
    fi
  fi
  for header_dir in \
    "${GRASU_ROOT}/GraSU/GraSU_kernels/src" \
    "${REGRAPH_ROOT}/acc_template/common" \
    "${REGRAPH_ROOT}/acc_template/kernel_apply" \
    "${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper" \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs" \
    "${REGRAPH_ROOT}/acc_template/kernel_little_gs_merger" \
    "${REGRAPH_UDF_INCLUDE}"; do
    if [[ -d "${header_dir}" ]]; then
      while IFS= read -r -d '' header; do
        emit_input_record kernel_header "${header}"
      done < <(find "${header_dir}" -maxdepth 1 -type f \
        \( -name '*.h' -o -name '*.hpp' \) -print0 | sort -z)
    fi
  done
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

echo "Prepared ${PIPELINE_MODE} pipeline build commands:"
echo "  ${BUILD_ROOT}"
echo
echo "Compile new/modified XOs:"
echo "  ${COMPILE_COMMANDS}"
echo
echo "Then link xclbin:"
echo "  ${LINK_COMMAND}"
