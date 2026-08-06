#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="sw_emu"
ALGORITHM="full_pagerank"
PLATFORM="xilinx_u55c_gen3x16_xdma_3_202210_1"
PLATFORM_XPFM="/opt/xilinx/platforms/${PLATFORM}/${PLATFORM}.xpfm"
KERNEL_FREQ=150
COMPUTE_PIPELINES=1
COMPUTE_PIPELINES_SET=0
PIPELINE_MODE="weighted-axis"
PLATFORM_MASTER_BUDGET=33
MAX_CACHE_SEGMENT="${GRASU_MAX_CACHE_SEGMENT:-131072}"
HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
HLS_INCLUDE_ETC="${HLS_INCLUDE_ETC:-${HLS_INCLUDE}/etc}"
BUILD_ROOT=""

usage() {
  cat <<USAGE
Usage: $0 [options]

Generate, but do not execute, a complete conversion-free GraSU/ReGraph
PageRank Vitis compile/link packet.

Options:
  --target sw_emu|hw_emu|hw
  --algorithm full_pagerank|residual_pagerank
  --platform NAME
  --platform-xpfm PATH
  --kernel-frequency MHz
  --compute-pipelines K
  --pipeline-mode weighted-axis|sharded-k4
  --platform-master-budget N
  --max-cache-segment N
  --hls-include PATH
  --hls-include-etc PATH
  --build-root PATH
  -h, --help
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
    --algorithm) ALGORITHM="$2"; shift 2 ;;
    --platform)
      PLATFORM="$2"
      PLATFORM_XPFM="/opt/xilinx/platforms/${PLATFORM}/${PLATFORM}.xpfm"
      shift 2
      ;;
    --platform-xpfm) PLATFORM_XPFM="$(abs_path "$2")"; shift 2 ;;
    --kernel-frequency) KERNEL_FREQ="$2"; shift 2 ;;
    --compute-pipelines) COMPUTE_PIPELINES="$2"; COMPUTE_PIPELINES_SET=1; shift 2 ;;
    --pipeline-mode) PIPELINE_MODE="$2"; shift 2 ;;
    --platform-master-budget) PLATFORM_MASTER_BUDGET="$2"; shift 2 ;;
    --max-cache-segment) MAX_CACHE_SEGMENT="$2"; shift 2 ;;
    --hls-include) HLS_INCLUDE="$(abs_path "$2")"; shift 2 ;;
    --hls-include-etc) HLS_INCLUDE_ETC="$(abs_path "$2")"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac
case "${ALGORITHM}" in
  full_pagerank) MODE=1 ;;
  residual_pagerank) MODE=2 ;;
  *) echo "Invalid --algorithm: ${ALGORITHM}" >&2; exit 2 ;;
esac
case "${PIPELINE_MODE}" in
  weighted-axis|sharded-k4) ;;
  *) echo "Invalid --pipeline-mode: ${PIPELINE_MODE}" >&2; exit 2 ;;
esac
if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
  if [[ "${COMPUTE_PIPELINES_SET}" == 1 && "${COMPUTE_PIPELINES}" != 4 ]]; then
    echo "sharded-k4 requires exactly four PMA/source/gather frontends" >&2
    exit 2
  fi
  COMPUTE_PIPELINES=4
fi
if [[ ! "${KERNEL_FREQ}" =~ ^[1-9][0-9]*$ ]]; then
  echo "--kernel-frequency must be positive" >&2
  exit 2
fi
if [[ ! "${COMPUTE_PIPELINES}" =~ ^[1-9][0-9]*$ ]]; then
  echo "--compute-pipelines must be positive" >&2
  exit 2
fi
if [[ ! "${PLATFORM_MASTER_BUDGET}" =~ ^[1-9][0-9]*$ ]]; then
  echo "--platform-master-budget must be positive" >&2
  exit 2
fi
if [[ -z "${BUILD_ROOT}" ]]; then
  BUILD_ROOT="${GRI_ROOT}/.tmp_build/${ALGORITHM}_${TARGET}_$(date +%Y%m%d_%H%M%S)"
fi
if [[ ! -d "${HLS_INCLUDE}" || ! -d "${HLS_INCLUDE_ETC}" ]]; then
  echo "Missing Vitis HLS include tree" >&2
  exit 1
fi

BUILD_DIR="${BUILD_ROOT}/build"
CFG_DIR="${BUILD_ROOT}/config"
LOG_DIR="${BUILD_ROOT}/logs"
REPORT_DIR="${BUILD_ROOT}/reports"
TMP_DIR="${BUILD_ROOT}/tmp"
GCC_COMPAT_INCLUDE="${BUILD_ROOT}/gcc_compat"
mkdir -p "${BUILD_DIR}" "${CFG_DIR}" "${LOG_DIR}" "${REPORT_DIR}" \
  "${TMP_DIR}" "${BUILD_ROOT}/ip_cache" "${GCC_COMPAT_INCLUDE}/bits"

{
  echo "#ifndef _GTHREAD_USE_COND_INIT_FUNC"
  echo "#define _GTHREAD_USE_COND_INIT_FUNC 1"
  echo "#endif"
  echo "#include_next <bits/gthr-default.h>"
} > "${GCC_COMPAT_INCLUDE}/bits/gthr-default.h"

GRASU_KERNEL_DIR="${GRASU_ROOT}/GraSU/GraSU_kernels/src"
REGRAPH_COMMON="${REGRAPH_ROOT}/acc_template/common"
REGRAPH_HBM="${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper"
REGRAPH_MERGER="${REGRAPH_ROOT}/acc_template/kernel_little_gs_merger"

required_sources=(
  "${GRASU_KERNEL_DIR}/kernel_bin_search.cpp"
  "${GRASU_KERNEL_DIR}/kernel_process_cache.cpp"
  "${GRASU_KERNEL_DIR}/kernel_process_ddr.cpp"
  "${GRI_ROOT}/kernels/grasu_dispatch_degree/grasu_dispatch_degree.cpp"
  "${GRI_ROOT}/kernels/grasu_degree_update/grasu_degree_update.cpp"
  "${GRI_ROOT}/kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
  "${GRI_ROOT}/kernels/regraph_stream_little_gs/little_gs_stream.cpp"
  "${REGRAPH_ROOT}/acc_template/kernel_little_gs_merger/kernel_little_gs_merger.cpp"
  "${GRI_ROOT}/kernels/regraph_pagerank_apply/regraph_pagerank_apply.cpp"
  "${GRI_ROOT}/kernels/regraph_pagerank_source_prepare/regraph_pagerank_source_prepare.cpp"
  "${REGRAPH_ROOT}/acc_template/kernel_hbm_wrapper/kernel_hbm_wrapper.cpp"
)
if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
  required_sources+=(
    "${GRI_ROOT}/kernels/regraph_frontend_mux/regraph_frontend_mux.cpp"
    "${GRI_ROOT}/kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp"
  )
fi
for source in "${required_sources[@]}"; do
  if [[ ! -f "${source}" ]]; then
    echo "Missing source: ${source}" >&2
    exit 1
  fi
done

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

kernels=(
  bin_search dispatch_degree process_cache process_ddr grasu_degree_update
  pma_to_regraph_adapter lksg_stream kernelLittleGSMerger
  regraph_pagerank_apply regraph_pagerank_source_prepare kernelHBMWrapper
)
if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
  kernels+=(regraph_frontend_mux)
fi
for kernel in "${kernels[@]}"; do
  write_compile_cfg "${kernel}" "${CFG_DIR}/${kernel}_compile.cfg"
done

LINK_CFG="${CFG_DIR}/${ALGORITHM}_${TARGET}.cfg"
OUT_XCLBIN="${BUILD_DIR}/grasu_regraph_${ALGORITHM}.${TARGET}.xclbin"
{
  echo "platform=${PLATFORM_XPFM}"
  echo "save-temps=1"
  echo "messageDb=${BUILD_DIR}/grasu_regraph_${ALGORITHM}.mdb"
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
  echo "nk=bin_search:4:bin_search_1.bin_search_2.bin_search_3.bin_search_4"
  lane_ranges=("0:5" "6:11" "12:17" "18:22")
  for index in 1 2 3 4; do
    if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
      echo "sp=bin_search_${index}.edges:HBM[${lane_ranges[$((index - 1))]}]"
      echo "sp=bin_search_${index}.binary_0:HBM[0:22]"
      echo "sp=bin_search_${index}.row_offset_0:HBM[0:22]"
    else
      channel=$((index - 1))
      echo "sp=bin_search_${index}.edges:HBM[${channel}]"
      echo "sp=bin_search_${index}.binary_0:HBM[${channel}]"
    fi
  done
  echo "slr=bin_search_1:SLR0"
  echo "slr=bin_search_2:SLR1"
  echo "slr=bin_search_3:SLR2"
  echo "slr=bin_search_4:SLR2"
  echo "nk=dispatch_degree:1:dispatch_degree_1"
  echo "slr=dispatch_degree_1:SLR1"
  echo "nk=process_cache:2:process_cache_1.process_cache_2"
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    echo "sp=process_cache_1.pma_cache:HBM[0:5]"
    echo "sp=process_cache_2.pma_cache:HBM[12:17]"
  else
    echo "sp=process_cache_1.pma_cache:HBM[0]"
    echo "sp=process_cache_2.pma_cache:HBM[2]"
  fi
  echo "slr=process_cache_1:SLR0"
  echo "slr=process_cache_2:SLR2"
  echo "nk=process_ddr:2:process_ddr_1.process_ddr_2"
  for port in pma_in0_ddr pma_in1_ddr pma_out0_ddr pma_out1_ddr; do
    if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
      echo "sp=process_ddr_1.${port}:HBM[6:11]"
      echo "sp=process_ddr_2.${port}:HBM[18:22]"
    else
      echo "sp=process_ddr_1.${port}:HBM[1]"
      echo "sp=process_ddr_2.${port}:HBM[3]"
    fi
  done
  echo "slr=process_ddr_1:SLR1"
  echo "slr=process_ddr_2:SLR2"
  echo "nk=grasu_degree_update:1:grasu_degree_update_1"
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    echo "sp=grasu_degree_update_1.out_degree:HBM[27]"
    echo "sp=grasu_degree_update_1.status:HBM[27]"
  else
    echo "sp=grasu_degree_update_1.out_degree:HBM[6]"
    echo "sp=grasu_degree_update_1.status:HBM[6]"
  fi
  echo "slr=grasu_degree_update_1:SLR1"
  for index in 1 2 3 4; do
    echo "stream_connect=bin_search_${index}.segment_head_stream_out:dispatch_degree_1.segment_head_stream_${index}:16"
  done
  echo "stream_connect=dispatch_degree_1.dispatch_to_process_cache_1:process_cache_1.update_stream:16"
  echo "stream_connect=dispatch_degree_1.dispatch_to_process_cache_2:process_cache_2.update_stream:16"
  echo "stream_connect=dispatch_degree_1.dispatch_to_process_ddr_1:process_ddr_1.update_stream:16"
  echo "stream_connect=dispatch_degree_1.dispatch_to_process_ddr_2:process_ddr_2.update_stream:16"
  echo "stream_connect=dispatch_degree_1.degree_delta:grasu_degree_update_1.degree_delta:64"
  echo
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    echo "# Four destination-sharded PageRank frontends and one shared downstream"
    echo "nk=pma_to_regraph_adapter:4:pma_to_regraph_adapter_1.pma_to_regraph_adapter_2.pma_to_regraph_adapter_3.pma_to_regraph_adapter_4"
    echo "nk=lksg_stream:4:lksg_stream_1.lksg_stream_2.lksg_stream_3.lksg_stream_4"
    echo "nk=regraph_frontend_mux:1:regraph_frontend_mux_1"
    echo "nk=kernelLittleGSMerger:1:kernelLittleGSMerger_1"
    echo "nk=regraph_pagerank_apply:1:regraph_pagerank_apply_1"
    echo "nk=kernelHBMWrapper:1:kernelHBMWrapper_1"
    echo "nk=regraph_pagerank_source_prepare:1:pr_source_1"
    for index in 1 2 3 4; do
      echo "sp=pma_to_regraph_adapter_${index}.pma0:HBM[0:22]"
      echo "slr=pma_to_regraph_adapter_${index}:SLR$(((index - 1) % 3))"
      echo "slr=lksg_stream_${index}:SLR$(((index - 1) % 3))"
      echo "stream_connect=pma_to_regraph_adapter_${index}.edge_burst_out:lksg_stream_${index}.edge_burst_in:32"
      echo "stream_connect=lksg_stream_${index}.l_ppb_request_stm:kernelHBMWrapper_1.l_ppb_request_stm_${index}:16"
      echo "stream_connect=kernelHBMWrapper_1.l_ppb_response_stm_${index}:lksg_stream_${index}.l_ppb_response_stm:16"
      echo "stream_connect=lksg_stream_${index}.l_tmp_prop_stm:regraph_frontend_mux_1.input$((index - 1)):32"
    done
    echo "slr=regraph_frontend_mux_1:SLR1"
    echo "slr=kernelLittleGSMerger_1:SLR1"
    echo "slr=regraph_pagerank_apply_1:SLR1"
    echo "slr=kernelHBMWrapper_1:SLR0"
    echo "stream_connect=regraph_frontend_mux_1.output:kernelLittleGSMerger_1.l_tmp_prop_stm_1:32"
    echo "stream_connect=kernelLittleGSMerger_1.l_write_burst_stm:regraph_pagerank_apply_1.merged_prop:16"
    echo "stream_connect=regraph_pagerank_apply_1.source_prop_write:kernelHBMWrapper_1.prop_write_burst_stm:16"
    echo "sp=kernelHBMWrapper_1.src_prop_1:HBM[23]"
    echo "sp=kernelHBMWrapper_1.src_prop_2:HBM[24]"
    echo "sp=kernelHBMWrapper_1.src_prop_3:HBM[23]"
    echo "sp=kernelHBMWrapper_1.src_prop_4:HBM[24]"
    echo "sp=kernelHBMWrapper_1.new_prop_1:HBM[23]"
    echo "sp=kernelHBMWrapper_1.new_prop_2:HBM[24]"
    echo "sp=pr_source_1.rank_state:HBM[25]"
    if [[ "${MODE}" == 2 ]]; then
      echo "sp=pr_source_1.residual_state:HBM[26]"
    fi
    echo "sp=pr_source_1.out_degree:HBM[27]"
    echo "sp=pr_source_1.source_prop_1:HBM[23]"
    echo "sp=pr_source_1.source_prop_2:HBM[24]"
    echo "sp=pr_source_1.round_stats:HBM[27]"
    echo "slr=pr_source_1:SLR1"
    echo "sp=regraph_pagerank_apply_1.rank_state:HBM[25]"
    if [[ "${MODE}" == 2 ]]; then
      echo "sp=regraph_pagerank_apply_1.residual_state:HBM[26]"
    fi
    echo "sp=regraph_pagerank_apply_1.out_degree:HBM[27]"
    echo "sp=regraph_pagerank_apply_1.round_stats:HBM[27]"
  else
  worker_names=""
  for index in $(seq 1 "${COMPUTE_PIPELINES}"); do
    worker_names="${worker_names}${worker_names:+.}pma_to_regraph_adapter_${index}"
  done
  echo "nk=pma_to_regraph_adapter:${COMPUTE_PIPELINES}:${worker_names}"
  worker_names=""
  for index in $(seq 1 "${COMPUTE_PIPELINES}"); do
    worker_names="${worker_names}${worker_names:+.}lksg_stream_${index}"
  done
  echo "nk=lksg_stream:${COMPUTE_PIPELINES}:${worker_names}"
  worker_names=""
  for index in $(seq 1 "${COMPUTE_PIPELINES}"); do
    worker_names="${worker_names}${worker_names:+.}kernelLittleGSMerger_${index}"
  done
  echo "nk=kernelLittleGSMerger:${COMPUTE_PIPELINES}:${worker_names}"
  worker_names=""
  for index in $(seq 1 "${COMPUTE_PIPELINES}"); do
    worker_names="${worker_names}${worker_names:+.}regraph_pagerank_apply_${index}"
  done
  echo "nk=regraph_pagerank_apply:${COMPUTE_PIPELINES}:${worker_names}"
  echo "nk=regraph_pagerank_source_prepare:1:pr_source_1"
  echo "sp=pr_source_1.rank_state:HBM[4]"
  if [[ "${MODE}" == 2 ]]; then
    echo "sp=pr_source_1.residual_state:HBM[5]"
  fi
  echo "sp=pr_source_1.out_degree:HBM[6]"
  echo "sp=pr_source_1.source_prop_1:HBM[1]"
  echo "sp=pr_source_1.source_prop_2:HBM[3]"
  echo "sp=pr_source_1.round_stats:HBM[6]"
  echo "slr=pr_source_1:SLR1"
  worker_names=""
  for index in $(seq 1 "${COMPUTE_PIPELINES}"); do
    worker_names="${worker_names}${worker_names:+.}kernelHBMWrapper_${index}"
  done
  echo "nk=kernelHBMWrapper:${COMPUTE_PIPELINES}:${worker_names}"
  for index in $(seq 1 "${COMPUTE_PIPELINES}"); do
    for pma_index in 0 1 2 3; do
      echo "sp=pma_to_regraph_adapter_${index}.pma${pma_index}:HBM[${pma_index}]"
    done
    echo "sp=pma_to_regraph_adapter_${index}.row_offset:HBM[0]"
    echo "slr=pma_to_regraph_adapter_${index}:SLR$((index % 3))"
    echo "slr=lksg_stream_${index}:SLR$(((index - 1) % 3))"
    echo "slr=kernelLittleGSMerger_${index}:SLR$((index % 3))"
    echo "sp=regraph_pagerank_apply_${index}.rank_state:HBM[4]"
    if [[ "${MODE}" == 2 ]]; then
      echo "sp=regraph_pagerank_apply_${index}.residual_state:HBM[5]"
    fi
    echo "sp=regraph_pagerank_apply_${index}.out_degree:HBM[6]"
    echo "sp=regraph_pagerank_apply_${index}.round_stats:HBM[6]"
    echo "slr=regraph_pagerank_apply_${index}:SLR$((index % 3))"
    echo "sp=kernelHBMWrapper_${index}.src_prop_1:HBM[1]"
    echo "sp=kernelHBMWrapper_${index}.src_prop_2:HBM[3]"
    echo "sp=kernelHBMWrapper_${index}.new_prop_1:HBM[1]"
    echo "sp=kernelHBMWrapper_${index}.new_prop_2:HBM[3]"
    echo "slr=kernelHBMWrapper_${index}:SLR$(((index - 1) % 3))"
    echo "stream_connect=pma_to_regraph_adapter_${index}.edge_burst_out:lksg_stream_${index}.edge_burst_in:32"
    echo "stream_connect=lksg_stream_${index}.l_ppb_request_stm:kernelHBMWrapper_${index}.l_ppb_request_stm_1:32"
    echo "stream_connect=kernelHBMWrapper_${index}.l_ppb_response_stm_1:lksg_stream_${index}.l_ppb_response_stm:32"
    echo "stream_connect=lksg_stream_${index}.l_tmp_prop_stm:kernelLittleGSMerger_${index}.l_tmp_prop_stm_1:16"
    echo "stream_connect=kernelLittleGSMerger_${index}.l_write_burst_stm:regraph_pagerank_apply_${index}.merged_prop:16"
    echo "stream_connect=regraph_pagerank_apply_${index}.source_prop_write:kernelHBMWrapper_${index}.prop_write_burst_stm:16"
  done
  fi
} > "${LINK_CFG}"

TARGET_DEFINE=""
case "${TARGET}" in
  sw_emu) TARGET_DEFINE="-DSW_EMU" ;;
  hw_emu) TARGET_DEFINE="-DHW_EMU" ;;
esac

COMMON_ENV="-D_GTHREAD_USE_COND_INIT_FUNC"
GRASU_FLAGS=(
  "${COMMON_ENV}" "-DGRASU_MAX_CACHE_SEGMENT=${MAX_CACHE_SEGMENT}"
  "-I${GRASU_KERNEL_DIR}" "-I${GRASU_ROOT}/GraSU/GraSU/src"
  "-I${GRI_ROOT}/include" "-I${HLS_INCLUDE_ETC}"
)
if [[ "${TARGET}" == sw_emu ]]; then
  GRASU_FLAGS+=("-DSW_EMU")
else
  GRASU_FLAGS+=("-DGRASU_COMPACT_HBM_PORTS")
fi
REGRAPH_FLAGS=(
  "${COMMON_ENV}" -O3 "-DHAVE_EDGE_PROP=0" "-DHAVE_UNSIGNED_PROP=1"
  "-DHAVE_APPLY_OUTDEG=0" "-DHAVE_VERTEX_PROP=0"
  "-DPARTITION_SIZE=65536" "-DLITTLE_KERNEL_DST_BUFFER_SIZE=65536"
  "-DBIG_KERNEL_DST_BUFFER_SIZE=524288" "-DSRC_BUFFER_SIZE=4096"
  "-DLOG2_SRC_BUFFER_SIZE=12" "-DVERTEX_REORDER_ENABLE=1"
  "-DENABLE_COMPRESSED_EDGE_INPUT=0" "-DBIG_KERNEL_NUM=0"
  "-DLITTLE_KERNEL_NUM=1" "-DREGRAPH_PURE_LITTLE_ONLY"
  "-I${GRI_ROOT}/include/regraph_pagerank" "-I${HLS_INCLUDE_ETC}"
  "-I${REGRAPH_ROOT}" "-I${REGRAPH_ROOT}/acc_template"
  "-I${REGRAPH_COMMON}" "-I${REGRAPH_ROOT}/acc_udfs"
)
if [[ -n "${TARGET_DEFINE}" ]]; then
  REGRAPH_FLAGS+=("${TARGET_DEFINE}")
fi
REGRAPH_K4_FLAGS=()
for flag in "${REGRAPH_FLAGS[@]}"; do
  if [[ "${flag}" != "-DLITTLE_KERNEL_NUM=1" ]]; then
    REGRAPH_K4_FLAGS+=("${flag}")
  fi
done
REGRAPH_K4_FLAGS+=("-DLITTLE_KERNEL_NUM=4")

emit_compile() {
  local kernel="$1"
  local source="$2"
  shift 2
  printf 'v++ --target %q --compile --kernel_frequency %q' "${TARGET}" "${KERNEL_FREQ}"
  for flag in "$@"; do printf ' %q' "${flag}"; done
  printf ' --config %q -o %q %q\n' \
    "${CFG_DIR}/${kernel}_compile.cfg" "${BUILD_DIR}/${kernel}.${TARGET}.xo" "${source}"
}

COMPILE_COMMANDS="${BUILD_ROOT}/compile_commands.sh"
{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  printf 'export TMPDIR=%q TMP=%q TEMP=%q\n' "${TMP_DIR}" "${TMP_DIR}" "${TMP_DIR}"
  printf 'export CPATH=%q${CPATH:+:${CPATH}}\n' "/usr/include/x86_64-linux-gnu:/usr/include"
  printf 'export C_INCLUDE_PATH=%q${C_INCLUDE_PATH:+:${C_INCLUDE_PATH}}\n' "/usr/include/x86_64-linux-gnu:/usr/include"
  printf 'export CPLUS_INCLUDE_PATH=%q${CPLUS_INCLUDE_PATH:+:${CPLUS_INCLUDE_PATH}}\n' "${GCC_COMPAT_INCLUDE}"
  printf 'export LIBRARY_PATH=%q${LIBRARY_PATH:+:${LIBRARY_PATH}}\n' "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu"
  printf 'export COMPILER_PATH=%q${COMPILER_PATH:+:${COMPILER_PATH}}\n' "/usr/bin"
  emit_compile bin_search "${GRASU_KERNEL_DIR}/kernel_bin_search.cpp" "${GRASU_FLAGS[@]}"
  emit_compile dispatch_degree "${GRI_ROOT}/kernels/grasu_dispatch_degree/grasu_dispatch_degree.cpp" "${GRASU_FLAGS[@]}"
  emit_compile process_cache "${GRASU_KERNEL_DIR}/kernel_process_cache.cpp" "${GRASU_FLAGS[@]}" -DGRASU_PURE_PIPELINE_DIRECT_CACHE
  emit_compile process_ddr "${GRASU_KERNEL_DIR}/kernel_process_ddr.cpp" "${GRASU_FLAGS[@]}" -DGRASU_SHARE_HBM_PORTS
  emit_compile grasu_degree_update "${GRI_ROOT}/kernels/grasu_degree_update/grasu_degree_update.cpp" "${GRASU_FLAGS[@]}"
  adapter_flags=(-DGRASU_REGRAPH_DESTINATION_ONLY=1 -DGRASU_REGRAPH_SHARE_ROW_OFFSET_PORT=1)
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    adapter_flags+=(
      -DGRASU_REGRAPH_SHARDED_PMA=1
      -DGRASU_REGRAPH_SHARE_ALL_MEMORY_PORTS=1
    )
  fi
  emit_compile pma_to_regraph_adapter "${GRI_ROOT}/kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp" "${REGRAPH_FLAGS[@]}" "${adapter_flags[@]}"
  emit_compile lksg_stream "${GRI_ROOT}/kernels/regraph_stream_little_gs/little_gs_stream.cpp" "${REGRAPH_FLAGS[@]}" "-I${REGRAPH_ROOT}/acc_template/kernel_little_gs"
  emit_compile kernelLittleGSMerger "${REGRAPH_MERGER}/kernel_little_gs_merger.cpp" "${REGRAPH_FLAGS[@]}" "-I${REGRAPH_MERGER}"
  emit_compile regraph_pagerank_apply "${GRI_ROOT}/kernels/regraph_pagerank_apply/regraph_pagerank_apply.cpp" "${COMMON_ENV}" "-DGRASU_REGRAPH_PAGERANK_MODE=${MODE}" "-I${GRI_ROOT}/include" "-I${HLS_INCLUDE_ETC}" ${TARGET_DEFINE:+"${TARGET_DEFINE}"}
  emit_compile regraph_pagerank_source_prepare "${GRI_ROOT}/kernels/regraph_pagerank_source_prepare/regraph_pagerank_source_prepare.cpp" "${COMMON_ENV}" "-DGRASU_REGRAPH_PAGERANK_MODE=${MODE}" "-I${GRI_ROOT}/include" "-I${HLS_INCLUDE_ETC}" ${TARGET_DEFINE:+"${TARGET_DEFINE}"}
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    emit_compile regraph_frontend_mux "${GRI_ROOT}/kernels/regraph_frontend_mux/regraph_frontend_mux.cpp" "${COMMON_ENV}" "-I${HLS_INCLUDE_ETC}" ${TARGET_DEFINE:+"${TARGET_DEFINE}"}
    emit_compile kernelHBMWrapper "${GRI_ROOT}/kernels/regraph_k4_shared_hbm_wrapper/kernel_hbm_wrapper.cpp" "${REGRAPH_K4_FLAGS[@]}" "-I${REGRAPH_HBM}"
  else
    emit_compile kernelHBMWrapper "${REGRAPH_HBM}/kernel_hbm_wrapper.cpp" "${REGRAPH_FLAGS[@]}" "-I${REGRAPH_HBM}"
  fi
} > "${COMPILE_COMMANDS}"
chmod +x "${COMPILE_COMMANDS}"

xos=()
for kernel in "${kernels[@]}"; do
  xos+=("${BUILD_DIR}/${kernel}.${TARGET}.xo")
done
LINK_COMMAND="${BUILD_ROOT}/link_command.sh"
{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  printf 'export TMPDIR=%q TMP=%q TEMP=%q\n' "${TMP_DIR}" "${TMP_DIR}" "${TMP_DIR}"
  printf 'export CPATH=%q${CPATH:+:${CPATH}}\n' "/usr/include/x86_64-linux-gnu:/usr/include"
  printf 'export C_INCLUDE_PATH=%q${C_INCLUDE_PATH:+:${C_INCLUDE_PATH}}\n' "/usr/include/x86_64-linux-gnu:/usr/include"
  printf 'export CPLUS_INCLUDE_PATH=%q${CPLUS_INCLUDE_PATH:+:${CPLUS_INCLUDE_PATH}}\n' "${GCC_COMPAT_INCLUDE}"
  printf 'export LIBRARY_PATH=%q${LIBRARY_PATH:+:${LIBRARY_PATH}}\n' "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu"
  printf 'export COMPILER_PATH=%q${COMPILER_PATH:+:${COMPILER_PATH}}\n' "/usr/bin"
  printf 'v++ --target %q --link --kernel_frequency %q --config %q -D_GTHREAD_USE_COND_INIT_FUNC -o %q' \
    "${TARGET}" "${KERNEL_FREQ}" "${LINK_CFG}" "${OUT_XCLBIN}"
  for xo in "${xos[@]}"; do printf ' %q' "${xo}"; done
  printf '\n'
} > "${LINK_COMMAND}"
chmod +x "${LINK_COMMAND}"

RUN_BUILD="${BUILD_ROOT}/run_build.sh"
{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf '%q\n' "${COMPILE_COMMANDS}"
  if [[ "${TARGET}" == "hw" && "${PIPELINE_MODE}" != "sharded-k4" ]]; then
    printf 'python3 %q --xo %q --expected-masters 2\n' \
      "${GRI_ROOT}/scripts/check_xo_master_budget.py" \
      "${BUILD_DIR}/bin_search.${TARGET}.xo"
    printf 'python3 %q --build-dir %q --compute-pipelines %q --platform-master-budget %q --out %q\n' \
      "${GRI_ROOT}/scripts/check_pipeline_master_budget.py" \
      "${BUILD_DIR}" "${COMPUTE_PIPELINES}" "${PLATFORM_MASTER_BUDGET}" \
      "${BUILD_ROOT}/pipeline_master_budget.json"
  elif [[ "${TARGET}" != "hw" ]]; then
    echo "echo 'SKIP AXI master-budget audit: sw_emu XO omits synthesized bundle metadata'"
  else
    echo "echo 'SKIP legacy replicated-worker master audit: sharded-k4 uses lane-aware connectivity checked by system_link'"
  fi
  printf '%q\n' "${LINK_COMMAND}"
} > "${RUN_BUILD}"
chmod +x "${RUN_BUILD}"

MANIFEST="${BUILD_ROOT}/manifest.env"
if git -C "${GRI_ROOT}" diff --quiet &&
   git -C "${GRI_ROOT}" diff --cached --quiet; then
  GRI_TRACKED_DIRTY=0
else
  GRI_TRACKED_DIRTY=1
fi
{
  echo "CLAIM_CLASS=proposed_conversion_free_hls_not_yet_built"
  echo "ALGORITHM=${ALGORITHM}"
  echo "PAGERANK_MODE=${MODE}"
  echo "TARGET=${TARGET}"
  echo "KERNEL_FREQUENCY_MHZ=${KERNEL_FREQ}"
  echo "COMPUTE_PIPELINES=${COMPUTE_PIPELINES}"
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    echo "PIPELINE_TOPOLOGY=four_sharded_pma_source_gather_frontends_one_shared_downstream"
  else
    echo "PIPELINE_TOPOLOGY=direct_complete_worker_replication"
  fi
  echo "PIPELINE_MODE=${PIPELINE_MODE}"
  echo "PLATFORM_MASTER_BUDGET=${PLATFORM_MASTER_BUDGET}"
  echo "PLATFORM=${PLATFORM}"
  echo "PLATFORM_XPFM=${PLATFORM_XPFM}"
  echo "GRI_GIT_HEAD=$(git -C "${GRI_ROOT}" rev-parse HEAD)"
  echo "GRI_GIT_TRACKED_DIRTY=${GRI_TRACKED_DIRTY}"
  echo "GRASU_GIT_HEAD=$(git -C "${GRASU_ROOT}" rev-parse HEAD)"
  echo "REGRAPH_GIT_HEAD=not_a_git_repository"
  echo "HANDOFF=pma_native_axis_no_edge_array_conversion"
  echo "DEGREE_SIDEBAND=dispatch_ordered_projected_optimization"
  if [[ "${PIPELINE_MODE}" == "sharded-k4" ]]; then
    echo "PMA_HBM_CHANNELS=0:22_lane_aware"
    echo "RANK_HBM_CHANNEL=25"
    echo "RESIDUAL_HBM_CHANNEL=$([[ "${MODE}" == 2 ]] && echo 26 || echo unused)"
    echo "DEGREE_HBM_CHANNEL=27"
    echo "STATS_HBM_CHANNEL=27"
    echo "SOURCE_MIRROR_HBM_CHANNELS=23,24"
    echo "PMA_FRONTEND_CUS=4"
    echo "SHARED_REGRAPH_DOWNSTREAM=1"
  else
    echo "PMA_HBM_CHANNELS=0,1,2,3"
    echo "RANK_HBM_CHANNEL=4"
    echo "RESIDUAL_HBM_CHANNEL=$([[ "${MODE}" == 2 ]] && echo 5 || echo unused)"
    echo "DEGREE_HBM_CHANNEL=6"
    echo "STATS_HBM_CHANNEL=7"
    echo "SOURCE_MIRROR_HBM_CHANNELS=1,3"
  fi
  echo "LINK_CFG=${LINK_CFG}"
  echo "OUT_XCLBIN=${OUT_XCLBIN}"
  echo "COMPILE_COMMANDS=${COMPILE_COMMANDS}"
  echo "LINK_COMMAND=${LINK_COMMAND}"
  echo "RUN_BUILD=${RUN_BUILD}"
} > "${MANIFEST}"

INPUTS="${BUILD_ROOT}/inputs.tsv"
{
  printf 'role\tstatus\tsha256\tbytes\tpath\n'
  for source in "${required_sources[@]}" "${GRI_ROOT}/include/grasu_degree_delta.hpp" \
      "${GRI_ROOT}/include/regraph_pagerank_apply.hpp" \
      "${GRI_ROOT}/include/regraph_pagerank/l2.h"; do
    printf 'source\tpresent\t'
    sha256sum "${source}" | awk '{printf "%s\t", $1}'
    stat --printf '%s\t%n\n' "${source}"
  done
  for xo in "${xos[@]}"; do
    printf 'generated_xo\tpending\t-\t-\t%s\n' "${xo}"
  done
  printf 'xclbin\tpending\t-\t-\t%s\n' "${OUT_XCLBIN}"
} > "${INPUTS}"

echo "Prepared ${ALGORITHM} ${TARGET} build packet: ${BUILD_ROOT}"
echo "Run later: ${RUN_BUILD}"
