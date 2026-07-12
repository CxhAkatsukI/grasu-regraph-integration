#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw_emu"
PLATFORM="xilinx_u55c_gen3x16_xdma_3_202210_1"
PLATFORM_XPFM="/opt/xilinx/platforms/${PLATFORM}/${PLATFORM}.xpfm"
KERNEL_FREQ=200
REGRAPH_HBM_OFFSET=0
BUILD_ROOT=""
GRASU_BUILD_ROOT=""
REGRAPH_XCLBIN_DIR=""
LINK=0
CONTAINER_IMAGE="${CONTAINER_IMAGE:-vivado-runner:22.04-feiyang}"

usage() {
  cat <<USAGE
Usage: $0 [options]

Generate, and optionally execute, one Vitis link step that places GraSU and
ReGraph SSSP kernels into a single xclbin.

Default behavior is generate-only. Add --link to run v++ inside the Vitis
container.

Options:
  --target hw_emu|hw          Link target. Default: ${TARGET}
  --platform NAME             Vitis platform name. Default: ${PLATFORM}
  --platform-xpfm PATH        Platform xpfm path. Default: ${PLATFORM_XPFM}
  --kernel-frequency MHz      Combined xclbin kernel frequency. Default: ${KERNEL_FREQ}
  --regraph-hbm-offset N      Move ReGraph HBM[0..3] to HBM[N..N+3]. Default: ${REGRAPH_HBM_OFFSET}
                              Use 0 with the current unmodified ReGraph host.
  --build-root PATH           Output build root. Default: .tmp_build/combined_<target>_<timestamp>
  --grasu-build-root PATH     GraSU U55C build root. Default from target.
  --regraph-xclbin-dir PATH   ReGraph SSSP xclbin/xo directory. Default from target.
  --link                      Execute the generated v++ link command.
  -h, --help                  Show this help.

Expected default inputs:
  hw_emu GraSU:  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hwemu/build
  hw_emu ReGraph:/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/xclbin_hw_emu_sssp
  hw GraSU:      /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build
  hw ReGraph:    /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp
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
    --platform-xpfm) PLATFORM_XPFM="$(abs_path "$2")"; shift 2 ;;
    --kernel-frequency) KERNEL_FREQ="$2"; shift 2 ;;
    --regraph-hbm-offset) REGRAPH_HBM_OFFSET="$2"; shift 2 ;;
    --build-root) BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --grasu-build-root) GRASU_BUILD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --regraph-xclbin-dir) REGRAPH_XCLBIN_DIR="$(abs_path "$2")"; shift 2 ;;
    --link) LINK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${TARGET}" in
  hw_emu|hw) ;;
  *) echo "Invalid --target: ${TARGET}" >&2; exit 2 ;;
esac

case "${REGRAPH_HBM_OFFSET}" in
  ''|*[!0-9]*) echo "--regraph-hbm-offset must be a non-negative integer" >&2; exit 2 ;;
esac

if (( REGRAPH_HBM_OFFSET + 3 > 31 )); then
  echo "--regraph-hbm-offset ${REGRAPH_HBM_OFFSET} would exceed U55C HBM[31]" >&2
  exit 2
fi

if [[ -z "${BUILD_ROOT}" ]]; then
  BUILD_ROOT="${GRI_ROOT}/.tmp_build/combined_${TARGET}_$(date +%Y%m%d_%H%M%S)"
fi

if [[ -z "${GRASU_BUILD_ROOT}" ]]; then
  if [[ "${TARGET}" == "hw_emu" ]]; then
    GRASU_BUILD_ROOT="${GRASU_ROOT}/.tmp_build/u55c_hbm_hwemu/build"
  else
    GRASU_BUILD_ROOT="${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/build"
  fi
fi

if [[ -z "${REGRAPH_XCLBIN_DIR}" ]]; then
  if [[ "${TARGET}" == "hw_emu" ]]; then
    REGRAPH_XCLBIN_DIR="/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/xclbin_hw_emu_sssp"
  else
    REGRAPH_XCLBIN_DIR="/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp"
  fi
fi

mkdir -p "${BUILD_ROOT}/build" "${BUILD_ROOT}/config" "${BUILD_ROOT}/reports/link" "${BUILD_ROOT}/logs/link" "${BUILD_ROOT}/ip_cache"

if [[ ! -f "${PLATFORM_XPFM}" ]]; then
  echo "Missing platform xpfm: ${PLATFORM_XPFM}" >&2
  exit 1
fi

GRASU_CONFIG_ROOT="$(dirname "${GRASU_BUILD_ROOT}")/config"
GRASU_LINK_CFG="${GRASU_CONFIG_ROOT}/GraSU-link.cfg"
GRASU_STREAM_CFG="${GRASU_CONFIG_ROOT}/stream_connect.ini"
REGRAPH_CONNECTIVITY_CFG="$(dirname "${REGRAPH_XCLBIN_DIR}")/acc_template/connectivity.cfg"

if [[ ! -f "${GRASU_LINK_CFG}" || ! -f "${GRASU_STREAM_CFG}" ]]; then
  echo "Missing GraSU generated link config under ${GRASU_CONFIG_ROOT}" >&2
  exit 1
fi
if [[ ! -f "${REGRAPH_CONNECTIVITY_CFG}" ]]; then
  echo "Missing ReGraph connectivity config: ${REGRAPH_CONNECTIVITY_CFG}" >&2
  if [[ "${TARGET}" == "hw" && "${REGRAPH_XCLBIN_DIR}" == "/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp" ]]; then
    cat >&2 <<'MSG'

For final hw integration, build cold-start ReGraph SSSP real hardware first:

  cd /home/chuxiao/grasu-regraph-integration
  ./scripts/build_regraph_sssp.sh \
    --target hw \
    --scratch /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch \
    --kernel-frequency-mhz 250

You can pass --regraph-xclbin-dir explicitly for a non-default scratch, but do
not use old-source ReGraph hw artifacts for final correctness claims.
MSG
  fi
  exit 1
fi

declare -a GRASU_XOS=(
  "${GRASU_BUILD_ROOT}/bin_search.${TARGET}.xo"
  "${GRASU_BUILD_ROOT}/dispatch.${TARGET}.xo"
  "${GRASU_BUILD_ROOT}/process_cache.${TARGET}.xo"
  "${GRASU_BUILD_ROOT}/process_ddr.${TARGET}.xo"
)
declare -a REGRAPH_XOS=(
  "${REGRAPH_XCLBIN_DIR}/kernelApply.${TARGET}.${PLATFORM}.xo"
  "${REGRAPH_XCLBIN_DIR}/kernelHBMWrapper.${TARGET}.${PLATFORM}.xo"
  "${REGRAPH_XCLBIN_DIR}/littleKernelScatterGather.${TARGET}.${PLATFORM}.xo"
  "${REGRAPH_XCLBIN_DIR}/kernelLittleGSMerger.${TARGET}.${PLATFORM}.xo"
  "${REGRAPH_XCLBIN_DIR}/bigKernelScatterGather.${TARGET}.${PLATFORM}.xo"
  "${REGRAPH_XCLBIN_DIR}/kernelBigGSMerger.${TARGET}.${PLATFORM}.xo"
)

missing=0
for xo in "${GRASU_XOS[@]}" "${REGRAPH_XOS[@]}"; do
  if [[ ! -f "${xo}" ]]; then
    echo "Missing xo: ${xo}" >&2
    missing=1
  fi
done
if [[ "${missing}" == "1" ]]; then
  if [[ "${TARGET}" == "hw" ]]; then
    cat >&2 <<'MSG'

For final hw integration, build cold-start ReGraph SSSP real hardware first:

  cd /home/chuxiao/grasu-regraph-integration
  ./scripts/build_regraph_sssp.sh \
    --target hw \
    --scratch /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch \
    --kernel-frequency-mhz 250

You can pass --regraph-xclbin-dir explicitly for a non-default scratch, but do
not use old-source ReGraph hw artifacts for final correctness claims.
MSG
  fi
  exit 1
fi

CFG="${BUILD_ROOT}/config/grasu_regraph_combined_${TARGET}.cfg"
OUT_XCLBIN="${BUILD_ROOT}/build/grasu_regraph_combined.${TARGET}.xclbin"
CMD_FILE="${BUILD_ROOT}/link_command.sh"
MANIFEST="${BUILD_ROOT}/manifest.env"
INPUTS="${BUILD_ROOT}/inputs.tsv"

copy_connectivity_body() {
  local file="$1"
  awk '
    BEGIN { in_conn = 0 }
    /^\[connectivity\]/ { in_conn = 1; next }
    in_conn == 1 { print }
  ' "${file}"
}

write_regraph_connectivity_with_hbm_shift() {
  local file="$1"
  local offset="$2"
  awk -v off="${offset}" '
    BEGIN { in_conn = 0 }
    /^\[connectivity\]/ { in_conn = 1; next }
    in_conn == 0 { next }
    {
      line = $0
      for (i = 3; i >= 0; --i) {
        repl = "HBM[" (i + off) "]"
        gsub("HBM\\[" i "\\]", repl, line)
      }
      print line
    }
  ' "${file}"
}

{
  echo "platform=${PLATFORM_XPFM}"
  echo "save-temps=1"
  echo "messageDb=${BUILD_ROOT}/build/grasu_regraph_combined.mdb"
  echo "temp_dir=${BUILD_ROOT}/build/link"
  echo "report_dir=${BUILD_ROOT}/reports/link"
  echo "log_dir=${BUILD_ROOT}/logs/link"
  echo "remote_ip_cache=${BUILD_ROOT}/ip_cache"
  echo
  echo "[advanced]"
  echo "misc=solution_name=link"
  echo "param=compiler.enablePerformanceTrace=1"
  echo
  echo "[vivado]"
  echo "prop=run.__KERNEL__.{STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS}={-directive sdx_optimization_effort_high}"
  echo "prop=run.impl_1.{STEPS.PLACE_DESIGN.ARGS.MORE OPTIONS}={-retiming}"
  echo "prop=run.impl_1.STEPS.PHYS_OPT_DESIGN.IS_ENABLED=true"
  echo "prop=run.impl_1.STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED=true"
  echo
  echo "[connectivity]"
  echo "# GraSU standalone U55C connectivity"
  copy_connectivity_body "${GRASU_LINK_CFG}"
  echo
  echo "# GraSU internal streams"
  copy_connectivity_body "${GRASU_STREAM_CFG}"
  echo
  echo "# ReGraph weighted SSSP connectivity; HBM[0..3] shifted by ${REGRAPH_HBM_OFFSET}"
  write_regraph_connectivity_with_hbm_shift "${REGRAPH_CONNECTIVITY_CFG}" "${REGRAPH_HBM_OFFSET}"
} > "${CFG}"

{
  echo "GRI_ROOT=${GRI_ROOT}"
  echo "GRASU_ROOT=${GRASU_ROOT}"
  echo "REGRAPH_ROOT=${REGRAPH_ROOT}"
  echo "TARGET=${TARGET}"
  echo "PLATFORM=${PLATFORM}"
  echo "PLATFORM_XPFM=${PLATFORM_XPFM}"
  echo "KERNEL_FREQ=${KERNEL_FREQ}"
  echo "REGRAPH_HBM_OFFSET=${REGRAPH_HBM_OFFSET}"
  echo "BUILD_ROOT=${BUILD_ROOT}"
  echo "GRASU_BUILD_ROOT=${GRASU_BUILD_ROOT}"
  echo "REGRAPH_XCLBIN_DIR=${REGRAPH_XCLBIN_DIR}"
  echo "GRASU_LINK_CFG=${GRASU_LINK_CFG}"
  echo "GRASU_STREAM_CFG=${GRASU_STREAM_CFG}"
  echo "REGRAPH_CONNECTIVITY_CFG=${REGRAPH_CONNECTIVITY_CFG}"
  echo "OUT_XCLBIN=${OUT_XCLBIN}"
} > "${MANIFEST}"

{
  printf 'role\tsha256\tsize\tpath\n'
  for xo in "${GRASU_XOS[@]}"; do
    printf 'grasu_xo\t'
    sha256sum "${xo}" | awk '{printf "%s\t", $1}'
    stat --printf '%s\t%n\n' "${xo}"
  done
  for xo in "${REGRAPH_XOS[@]}"; do
    printf 'regraph_xo\t'
    sha256sum "${xo}" | awk '{printf "%s\t", $1}'
    stat --printf '%s\t%n\n' "${xo}"
  done
} > "${INPUTS}"

{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  printf 'v++ --target %q --link --kernel_frequency %q --config %q -o %q' \
    "${TARGET}" "${KERNEL_FREQ}" "${CFG}" "${OUT_XCLBIN}"
  for xo in "${GRASU_XOS[@]}" "${REGRAPH_XOS[@]}"; do
    printf ' %q' "${xo}"
  done
  printf '\n'
} > "${CMD_FILE}"
chmod +x "${CMD_FILE}"

echo "Generated combined link config:"
echo "  ${CFG}"
echo "Generated manifest:"
echo "  ${MANIFEST}"
echo "Generated command:"
echo "  ${CMD_FILE}"
echo "Output xclbin:"
echo "  ${OUT_XCLBIN}"

if [[ "${LINK}" != "1" ]]; then
  echo
  echo "Generate-only mode. To execute:"
  echo "  ${CMD_FILE}"
  echo
  echo "Or rerun this script with --link to execute inside ${CONTAINER_IMAGE}."
  exit 0
fi

echo
echo "Executing combined ${TARGET} link inside ${CONTAINER_IMAGE}..."

podman run --rm --platform linux/amd64 \
  --userns=keep-id --user "$(id -u):$(id -g)" \
  --network host --shm-size=8g \
  -v /run/udev:/run/udev:ro \
  -v /sys:/sys:ro \
  -v /etc/machine-id:/etc/machine-id:ro \
  -v /data/yxx/tools/xilinx:/data/yxx/tools/xilinx:ro \
  -v /opt/xilinx:/opt/xilinx:ro \
  -v /home/chuxiao:/home/chuxiao \
  -e HOME="${BUILD_ROOT}/container_home" \
  -e XILINX_XRT=/opt/xilinx/xrt \
  -e PLATFORM_REPO_PATHS=/opt/xilinx/platforms \
  -e CPATH=/usr/include/x86_64-linux-gnu \
  -e LANG=en_US.UTF-8 \
  -e LC_ALL=en_US.UTF-8 \
  -w "${BUILD_ROOT}" \
  "${CONTAINER_IMAGE}" bash "${CMD_FILE}" 2>&1 | tee "${BUILD_ROOT}/link_${TARGET}.log"

if [[ -f "${OUT_XCLBIN}" ]]; then
  sha256sum "${OUT_XCLBIN}" > "${BUILD_ROOT}/SHA256SUMS"
  echo "DONE combined_xclbin=${OUT_XCLBIN}"
else
  echo "Link command finished but xclbin is missing: ${OUT_XCLBIN}" >&2
  exit 1
fi
