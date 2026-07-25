#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

TARGET="hw"
ALGORITHM="all"
PLATFORM="xilinx_u55c_gen3x16_xdma_3_202210_1"
PLATFORM_XPFM="/opt/xilinx/platforms/${PLATFORM}/${PLATFORM}.xpfm"
KERNEL_FREQUENCY=200
HLS_INCLUDE="${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}"
HLS_INCLUDE_ETC="${HLS_INCLUDE_ETC:-${HLS_INCLUDE}/etc}"
BUILD_ROOT=""

usage() {
  cat <<USAGE
Usage: $0 [options]

Generate v++ compile commands for the isolated 8-lane ReGraph algorithm policy
core. The resulting XO/resource reports are incremental algorithm-datapath
evidence, not complete-system performance evidence.

Options:
  --target sw_emu|hw_emu|hw
  --algorithm weighted-sssp|full-pagerank|thresholded-residual-pagerank|all
  --platform-xpfm PATH
  --kernel-frequency MHz
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
    --platform-xpfm) PLATFORM_XPFM="$(abs_path "$2")"; shift 2 ;;
    --kernel-frequency) KERNEL_FREQUENCY="$2"; shift 2 ;;
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
  weighted-sssp|full-pagerank|thresholded-residual-pagerank|all) ;;
  *) echo "Invalid --algorithm: ${ALGORITHM}" >&2; exit 2 ;;
esac
if ! [[ "${KERNEL_FREQUENCY}" =~ ^[0-9]+$ ]] || [[ "${KERNEL_FREQUENCY}" == 0 ]]; then
  echo "Invalid --kernel-frequency: ${KERNEL_FREQUENCY}" >&2
  exit 2
fi
for required in "${PLATFORM_XPFM}" "${HLS_INCLUDE}" "${HLS_INCLUDE_ETC}"; do
  if [[ ! -e "${required}" ]]; then
    echo "Missing build input: ${required}" >&2
    exit 1
  fi
done

if [[ -z "${BUILD_ROOT}" ]]; then
  BUILD_ROOT="${GRI_ROOT}/.tmp_build/regraph_algorithm_policy_${TARGET}_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "${BUILD_ROOT}/build" "${BUILD_ROOT}/config" \
  "${BUILD_ROOT}/logs" "${BUILD_ROOT}/reports" "${BUILD_ROOT}/tmp"

declare -A POLICY_IDS=(
  [weighted-sssp]=1
  [full-pagerank]=2
  [thresholded-residual-pagerank]=3
)
declare -A STATE_BYTES=(
  [weighted-sssp]=4
  [full-pagerank]=4
  [thresholded-residual-pagerank]=8
)
if [[ "${ALGORITHM}" == all ]]; then
  ALGORITHMS=(weighted-sssp full-pagerank thresholded-residual-pagerank)
else
  ALGORITHMS=("${ALGORITHM}")
fi

SOURCE="${GRI_ROOT}/kernels/regraph_algorithm_policy/regraph_algorithm_policy.cpp"
COMMANDS="${BUILD_ROOT}/compile_commands.sh"
MANIFEST="${BUILD_ROOT}/manifest.env"
INPUTS="${BUILD_ROOT}/inputs.tsv"

{
  echo '#!/usr/bin/env bash'
  echo 'set -euo pipefail'
  printf 'source %q\n' /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
  printf 'export TMPDIR=%q\n' "${BUILD_ROOT}/tmp"
  for algorithm in "${ALGORITHMS[@]}"; do
    stem="${algorithm//-/_}"
    cfg="${BUILD_ROOT}/config/${stem}_${TARGET}.cfg"
    {
      echo "platform=${PLATFORM_XPFM}"
      echo 'save-temps=1'
      echo 'kernel=regraph_algorithm_policy'
      echo "messageDb=${BUILD_ROOT}/build/${stem}.mdb"
      echo "temp_dir=${BUILD_ROOT}/build/${stem}"
      echo "report_dir=${BUILD_ROOT}/reports/${stem}"
      echo "log_dir=${BUILD_ROOT}/logs/${stem}"
      echo
      echo '[advanced]'
      echo "misc=solution_name=${stem}"
    } >"${cfg}"
    output="${BUILD_ROOT}/build/regraph_algorithm_policy_${stem}.${TARGET}.xo"
    printf 'v++ --target %q --compile --kernel_frequency %q -DREGRAPH_ALGORITHM_POLICY=%q -I%q --config %q -o %q %q\n' \
      "${TARGET}" "${KERNEL_FREQUENCY}" "${POLICY_IDS[${algorithm}]}" \
      "${HLS_INCLUDE_ETC}" "${cfg}" "${output}" "${SOURCE}"
  done
} >"${COMMANDS}"
chmod +x "${COMMANDS}"

{
  echo "CLAIM_CLASS=synthesizable_policy_core_not_full_system_native"
  echo "EVIDENCE_SCOPE=incremental_map_reduce_apply_datapath"
  echo "TARGET=${TARGET}"
  echo "ALGORITHM=${ALGORITHM}"
  echo "ALGORITHMS=$(IFS=,; echo "${ALGORITHMS[*]}")"
  echo "POLICY_LANES=8"
  echo "PLATFORM_XPFM=${PLATFORM_XPFM}"
  echo "KERNEL_FREQUENCY=${KERNEL_FREQUENCY}"
  echo "BUILD_ROOT=${BUILD_ROOT}"
  echo "SOURCE=${SOURCE}"
  echo "SOURCE_SHA256=$(sha256sum "${SOURCE}" | awk '{print $1}')"
  echo "GRI_GIT_HEAD=$(git -C "${GRI_ROOT}" rev-parse HEAD)"
  echo "COMPILE_COMMANDS=${COMMANDS}"
  for algorithm in "${ALGORITHMS[@]}"; do
    key="${algorithm^^}"
    key="${key//-/_}"
    echo "${key}_POLICY_ID=${POLICY_IDS[${algorithm}]}"
    echo "${key}_STATE_BYTES_PER_VERTEX=${STATE_BYTES[${algorithm}]}"
  done
} >"${MANIFEST}"

{
  printf 'role\tsha256\tbytes\tpath\n'
  for input in "${SOURCE}" "${COMMANDS}" "${MANIFEST}"; do
    printf 'build_input\t%s\t%s\t%s\n' \
      "$(sha256sum "${input}" | awk '{print $1}')" \
      "$(stat --printf '%s' "${input}")" "${input}"
  done
  for algorithm in "${ALGORITHMS[@]}"; do
    stem="${algorithm//-/_}"
    printf 'generated_xo\tpending\t-\t%s\n' \
      "${BUILD_ROOT}/build/regraph_algorithm_policy_${stem}.${TARGET}.xo"
  done
} >"${INPUTS}"

echo "Prepared algorithm policy HLS build: ${BUILD_ROOT}"
echo "Run: ${COMMANDS}"
