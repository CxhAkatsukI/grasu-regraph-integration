#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw_emu"
PLATFORM="xilinx_u55c_gen3x16_xdma_3_202210_1"
SCRATCH=""
EVIDENCE_DIR=""
RUN_TINY=0
SOURCE_VERTEX=0
SUPERSTEPS=4
NUM_DENSE=1
CONTAINER_IMAGE="${CONTAINER_IMAGE:-vivado-runner:22.04-feiyang}"
KERNEL_FREQUENCY_MHZ=""

usage() {
  cat <<USAGE
Usage: $0 [options]

Build ReGraph APP=sssp from a clean scratch copied from the current ReGraph
source tree. This avoids accidentally reusing stale _x/xclbin files.

Options:
  --target sw_emu|hw_emu|hw   Build target. Default: ${TARGET}
  --platform NAME             Vitis platform. Default: ${PLATFORM}
  --scratch PATH              Scratch directory. Default: /home/chuxiao/ReGraph_sssp_<target>_fixed_scratch
  --evidence-dir PATH         Evidence/log directory. Default: <ReGraph>/.tmp_doc/evidence_sssp_<target>_fixed_<timestamp>
  --run-tiny                  Run dataset/tiny-weighted-sssp.txt after build.
  --source-vertex N           REGRAPH_SOURCE for --run-tiny. Default: ${SOURCE_VERTEX}
  --supersteps N              Supersteps for --run-tiny. Default: ${SUPERSTEPS}
  --num-dense N               ReGraph numD argument for --run-tiny. Default: ${NUM_DENSE}
  --kernel-frequency-mhz N    Append --kernel_frequency=N to scratch LDCLFLAGS.
                              Useful for timing-closure experiments; leaves source tree unchanged.
  -h, --help                  Show this help.
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
    --platform) PLATFORM="$2"; shift 2 ;;
    --scratch) SCRATCH="$(abs_path "$2")"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="$(abs_path "$2")"; shift 2 ;;
    --run-tiny) RUN_TINY=1; shift ;;
    --source-vertex) SOURCE_VERTEX="$2"; shift 2 ;;
    --supersteps) SUPERSTEPS="$2"; shift 2 ;;
    --num-dense) NUM_DENSE="$2"; shift 2 ;;
    --kernel-frequency-mhz) KERNEL_FREQUENCY_MHZ="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  sw_emu|hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

REGRAPH_REAL_ROOT="$(readlink -f "${REGRAPH_ROOT}")"
if [[ ! -d "${REGRAPH_REAL_ROOT}" ]]; then
  echo "Missing ReGraph tree: ${REGRAPH_ROOT}" >&2
  exit 1
fi

if [[ -z "${SCRATCH}" ]]; then
  SCRATCH="/home/chuxiao/ReGraph_sssp_${TARGET}_fixed_scratch"
fi
if [[ -z "${EVIDENCE_DIR}" ]]; then
  EVIDENCE_DIR="${REGRAPH_REAL_ROOT}/.tmp_doc/evidence_sssp_${TARGET}_fixed_$(date +%Y%m%d_%H%M%S)"
fi

mkdir -p "${SCRATCH}" "${EVIDENCE_DIR}"

echo "[1/5] Copying fixed ReGraph source into scratch..."
rsync -a --delete \
  --exclude "_x" \
  --exclude "_x_*" \
  --exclude ".run" \
  --exclude ".Xil" \
  --exclude ".ipcache" \
  --exclude ".tmp_build" \
  --exclude "target" \
  --exclude "xclbin_*" \
  --exclude "host_graph_fpga_*" \
  --exclude "*.log" \
  "${REGRAPH_REAL_ROOT}/" "${SCRATCH}/"

echo "[2/5] Checking that the scratch contains the gather init fix..."
rg -n "initDstTmpProp|#ifdef SW_EMU" \
  "${SCRATCH}/acc_template/kernel_little_gs/acc_gather.h" \
  "${SCRATCH}/acc_template/kernel_big_gs/acc_gather.h" \
  | tee "${EVIDENCE_DIR}/source_check.txt"
if awk '
  /^[[:space:]]*#ifdef SW_EMU/ { guard_line = NR }
  /initDstTmpProp:/ && guard_line && NR - guard_line <= 2 { bad = 1 }
  END { exit bad ? 0 : 1 }
' "${SCRATCH}/acc_template/kernel_little_gs/acc_gather.h" \
  "${SCRATCH}/acc_template/kernel_big_gs/acc_gather.h"; then
  echo "The scratch still has an active SW_EMU-only gather init guard." >&2
  exit 1
fi

if [[ -n "${KERNEL_FREQUENCY_MHZ}" ]]; then
  if ! [[ "${KERNEL_FREQUENCY_MHZ}" =~ ^[0-9]+$ ]]; then
    echo "Invalid --kernel-frequency-mhz: ${KERNEL_FREQUENCY_MHZ}" >&2
    exit 2
  fi
  cat >> "${SCRATCH}/host/host.mk" <<EOF

# Added by scripts/build_regraph_sssp.sh for a reproducible timing experiment.
LDCLFLAGS += --kernel_frequency=${KERNEL_FREQUENCY_MHZ}
EOF
  {
    echo "target=${TARGET}"
    echo "kernel_frequency_mhz=${KERNEL_FREQUENCY_MHZ}"
    echo "scratch=${SCRATCH}"
  } > "${EVIDENCE_DIR}/build_options.txt"
else
  {
    echo "target=${TARGET}"
    echo "kernel_frequency_mhz=default"
    echo "scratch=${SCRATCH}"
  } > "${EVIDENCE_DIR}/build_options.txt"
fi

echo "[3/5] Building ReGraph APP=sssp TARGETS=${TARGET}..."
podman run --rm --platform linux/amd64 \
  --userns=keep-id --user "$(id -u):$(id -g)" \
  --network host --shm-size=8g \
  -v /run/udev:/run/udev:ro \
  -v /sys:/sys:ro \
  -v /etc/machine-id:/etc/machine-id:ro \
  -v /data/yxx/tools/xilinx:/data/yxx/tools/xilinx:ro \
  -v /opt/xilinx:/opt/xilinx:ro \
  -v "${SCRATCH}":/vitis_work/project \
  -v "${EVIDENCE_DIR}":/evidence \
  -v "${REGRAPH_REAL_ROOT}/target/opencl_vendors":/etc/OpenCL/vendors:ro \
  -v "${REGRAPH_REAL_ROOT}/target/include/asm":/usr/include/asm:ro \
  -e HOME=/vitis_work/project/.tmp_build/container_home \
  -e XILINX_XRT=/opt/xilinx/xrt \
  -e PLATFORM_REPO_PATHS=/opt/xilinx/platforms \
  -e CPATH=/usr/include/x86_64-linux-gnu \
  -e LANG=en_US.UTF-8 \
  -e LC_ALL=en_US.UTF-8 \
  -w /vitis_work/project \
  "${CONTAINER_IMAGE}" bash -lc "
    set -euo pipefail
    source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
    mkdir -p \"\$HOME\"
    make APP=sssp TARGETS=${TARGET} DEVICES=${PLATFORM} autogen 2>&1 | tee /evidence/autogen.log
    make APP=sssp TARGETS=${TARGET} DEVICES=${PLATFORM} all 2>&1 | tee /evidence/build_${TARGET}.log
  "

echo "[4/5] Capturing build evidence..."
find "${SCRATCH}" -maxdepth 3 \
  \( -name "host_graph_fpga_sssp" -o -name "graph_fpga.${TARGET}*.xclbin" -o -name "emconfig.json" -o -name "*.link_summary" -o -name "*.compile_summary" \) \
  -printf "%TY-%Tm-%Td %TH:%TM %s %p\n" | sort > "${EVIDENCE_DIR}/build_outputs.txt"

if [[ -f "${SCRATCH}/xclbin_${TARGET}_sssp/graph_fpga.${TARGET}.${PLATFORM}.xclbin.link_summary" ]]; then
  cp "${SCRATCH}/xclbin_${TARGET}_sssp/graph_fpga.${TARGET}.${PLATFORM}.xclbin.link_summary" \
     "${EVIDENCE_DIR}/graph_fpga.${TARGET}.link_summary"
fi
if [[ -f "${SCRATCH}/_x/logs/link/link.steps.log" ]]; then
  cp "${SCRATCH}/_x/logs/link/link.steps.log" "${EVIDENCE_DIR}/link.steps.log"
fi
if [[ -f "${SCRATCH}/_x/reports/link/system_estimate_graph_fpga.${TARGET}.${PLATFORM}.xtxt" ]]; then
  cp "${SCRATCH}/_x/reports/link/system_estimate_graph_fpga.${TARGET}.${PLATFORM}.xtxt" \
     "${EVIDENCE_DIR}/system_estimate_graph_fpga.${TARGET}.xtxt"
fi
mkdir -p "${EVIDENCE_DIR}/kernel_system_estimates"
find "${SCRATCH}/_x/reports" -maxdepth 2 -type f -name "system_estimate_*.xtxt" ! -path "*/link/*" \
  -exec cp {} "${EVIDENCE_DIR}/kernel_system_estimates/" \;
{
  echo "# initDstTmpProp HLS evidence"
  echo
  for kernel in littleKernelScatterGather bigKernelScatterGather; do
    echo "## ${kernel}"
    hls_log="${SCRATCH}/_x/${kernel}.${TARGET}.${PLATFORM}/${kernel}/vitis_hls.log"
    if [[ -f "${hls_log}" ]]; then
      rg -n "initDstTmpProp|Loop Constraint Status|Estimated Fmax" "${hls_log}" || true
    else
      echo "missing ${hls_log}"
    fi
    echo
  done
} > "${EVIDENCE_DIR}/initDstTmpProp_hls_evidence.txt"
(
  cd "${SCRATCH}"
  sha256sum \
    host_graph_fpga_sssp \
    "xclbin_${TARGET}_sssp/graph_fpga.${TARGET}.${PLATFORM}.xclbin" \
    "xclbin_${TARGET}_sssp/${PLATFORM}/emconfig.json" 2>/dev/null || true
) > "${EVIDENCE_DIR}/SHA256SUMS"

if [[ "${RUN_TINY}" == "1" ]]; then
  if [[ "${TARGET}" == "hw" ]]; then
    EMU_ENV=()
  else
    EMU_ENV=(-e XCL_EMULATION_MODE="${TARGET}" -e EMCONFIG_PATH="/vitis_work/project/xclbin_${TARGET}_sssp/${PLATFORM}")
  fi

  echo "[5/5] Running tiny weighted SSSP..."
  podman run --rm --platform linux/amd64 \
    --userns=keep-id --user "$(id -u):$(id -g)" \
    --network host --shm-size=8g \
    -v /run/udev:/run/udev:ro \
    -v /sys:/sys:ro \
    -v /etc/machine-id:/etc/machine-id:ro \
    -v /data/yxx/tools/xilinx:/data/yxx/tools/xilinx:ro \
    -v /opt/xilinx:/opt/xilinx:ro \
    -v "${SCRATCH}":/vitis_work/project \
    -v "${EVIDENCE_DIR}":/evidence \
    -v "${REGRAPH_REAL_ROOT}/target/opencl_vendors":/etc/OpenCL/vendors:ro \
    "${EMU_ENV[@]}" \
    -e HOME=/vitis_work/project/.tmp_build/container_home \
    -e XILINX_XRT=/opt/xilinx/xrt \
    -e PLATFORM_REPO_PATHS=/opt/xilinx/platforms \
    -e REGRAPH_SOURCE="${SOURCE_VERTEX}" \
    -e LD_LIBRARY_PATH=/opt/xilinx/xrt/lib \
    -w /vitis_work/project \
    "${CONTAINER_IMAGE}" bash -lc "
      set -euo pipefail
      source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
      ./host_graph_fpga_sssp \
        xclbin_${TARGET}_sssp/graph_fpga.${TARGET}.${PLATFORM}.xclbin \
        dataset/tiny-weighted-sssp.txt \
        ${NUM_DENSE} ${SUPERSTEPS} 2>&1 | tee /evidence/run_tiny_weighted_sssp_${TARGET}.log
    "
  if [[ -f "${SCRATCH}/.run/7/${TARGET}/device0/binary_0/behav_waveform/xsim/simulate.log" ]]; then
    cp "${SCRATCH}/.run/7/${TARGET}/device0/binary_0/behav_waveform/xsim/simulate.log" \
       "${EVIDENCE_DIR}/xsim_simulate.log"
  fi
  run_log="${EVIDENCE_DIR}/run_tiny_weighted_sssp_${TARGET}.log"
  if rg -q "mismatch|This iteration has" "${run_log}"; then
    mismatch_count="$(rg -c "mismatch|This iteration has" "${run_log}")"
  else
    mismatch_count=0
  fi
  {
    echo "# ${TARGET} tiny weighted SSSP validation"
    echo "mismatch_count=${mismatch_count}"
    rg -n "Device\\[0\\]: program successful|Supersteps|Starting superstep|Processed edges|All the simulator processes exited successfully|mismatch|This iteration has" \
      "${run_log}" || true
  } > "${EVIDENCE_DIR}/run_validation_summary.txt"
  cp "${EVIDENCE_DIR}/run_validation_summary.txt" "${EVIDENCE_DIR}/run_key_lines.txt"
else
  echo "[5/5] Skipped tiny run. Add --run-tiny to execute it."
fi

echo "DONE scratch=${SCRATCH}"
echo "DONE evidence=${EVIDENCE_DIR}"
