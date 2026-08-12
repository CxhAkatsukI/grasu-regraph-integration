#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

algorithm=""
host=""
xclbin=""
graph=""
out_dir=""
device_index=0
source_vertex=0
max_supersteps=256
timeout_seconds=600
update_only=0

usage() {
  cat <<USAGE
Usage: $0 --algorithm NAME --host PATH --xclbin PATH --graph PATH --out-dir PATH [options]

Run one correctness-gated conversion-free GraSU+ReGraph FPGA experiment.

Options:
  --algorithm NAME       weighted_sssp, connected_components, full_pagerank,
                         or residual_pagerank.
  --device-index N       XRT device index. Default: ${device_index}
  --source N             SSSP source vertex. Default: ${source_vertex}
  --max-supersteps N     SSSP/CC watchdog. Default: ${max_supersteps}
  --timeout SECONDS      Host-process watchdog. Default: ${timeout_seconds}
  --update-only          Validate and time only the routed PMA update datapath.
USAGE
}

while (( $# > 0 )); do
  case "$1" in
    --algorithm) algorithm=$2; shift 2 ;;
    --host) host=$2; shift 2 ;;
    --xclbin) xclbin=$2; shift 2 ;;
    --graph) graph=$2; shift 2 ;;
    --out-dir) out_dir=$2; shift 2 ;;
    --device-index) device_index=$2; shift 2 ;;
    --source) source_vertex=$2; shift 2 ;;
    --max-supersteps) max_supersteps=$2; shift 2 ;;
    --timeout) timeout_seconds=$2; shift 2 ;;
    --update-only) update_only=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for required in algorithm host xclbin graph out_dir; do
  if [[ -z "${!required}" ]]; then
    echo "--${required//_/-} is required" >&2
    exit 2
  fi
done
for numeric in device_index source_vertex max_supersteps timeout_seconds; do
  if ! [[ "${!numeric}" =~ ^[0-9]+$ ]]; then
    echo "${numeric} must be a non-negative integer" >&2
    exit 2
  fi
done
if (( max_supersteps == 0 || timeout_seconds == 0 )); then
  echo "--max-supersteps and --timeout must be positive" >&2
  exit 2
fi
if [[ ! -x "${host}" || ! -f "${xclbin}" || ! -f "${graph}" ]]; then
  echo "host, xclbin, or graph is missing" >&2
  exit 1
fi

case "${algorithm}" in
  weighted_sssp) prefix=WEIGHTED_PMA_NATIVE ;;
  connected_components) prefix=CC_PMA_NATIVE ;;
  full_pagerank) prefix=FULL_PR_PMA_NATIVE ;;
  residual_pagerank) prefix=RESIDUAL_PR_PMA_NATIVE ;;
  *) echo "unsupported algorithm: ${algorithm}" >&2; exit 2 ;;
esac

mkdir -p "${out_dir}"
host=$(realpath "${host}")
xclbin=$(realpath "${xclbin}")
graph=$(realpath "${graph}")
out_dir=$(realpath "${out_dir}")
result_file="${out_dir}/result.txt"
run_log="${out_dir}/run.log"
run_env="${out_dir}/run.env"
summary="${out_dir}/summary.tsv"

set +u
source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh >/dev/null
set -u
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${XILINX_XRT}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
unset XCL_EMULATION_MODE || true

repo_head=$(git -C "${GRI_ROOT}" rev-parse HEAD)
repo_dirty=$([[ -n "$(git -C "${GRI_ROOT}" status --short)" ]] && echo 1 || echo 0)
echo "RUN_START target=hw algorithm=${algorithm} device_index=${device_index} repo_head=${repo_head} repo_dirty=${repo_dirty}"

command=("${host}")
if (( update_only )); then
  command+=(--update-only)
fi
command+=("${xclbin}" "${graph}" "${result_file}")
if [[ "${algorithm}" == weighted_sssp ||
      "${algorithm}" == connected_components ]]; then
  command+=("${source_vertex}" "${max_supersteps}")
fi

set +e
timeout --signal=TERM --kill-after=15s "${timeout_seconds}s" \
  env XCL_DEVICE_INDEX="${device_index}" "${command[@]}" \
  2>&1 | tee "${run_log}"
host_exit=${PIPESTATUS[0]}
set -e

# Sharded-K4 hosts retain an explicit SHARDED marker so their evidence cannot
# be confused with the legacy full-PMA-scan baseline.
if (( update_only )); then
  result_line=$(rg '^GRASU_SHARDED_UPDATE_ONLY_RESULT ' "${run_log}" | tail -1 || true)
else
  result_line=$(rg "^${prefix}(_SHARDED)?_RESULT " "${run_log}" | tail -1 || true)
fi
timing_line=$(rg "^${prefix}(_SHARDED)?_TIMING " "${run_log}" | tail -1 || true)
status=FAIL
if (( host_exit == 0 )) &&
   [[ "${result_line}" == *"status=PASS"* ]] &&
   [[ "${result_line}" == *"conversion_cost=absent"* ]]; then
  if (( update_only )); then
    if [[ "${result_line}" == *"pma_mismatches=0"* ]]; then
      case "${algorithm}" in
        full_pagerank|residual_pagerank)
          [[ "${result_line}" == *"degree_mismatches=0"* ]] && status=PASS
          ;;
        *) status=PASS ;;
      esac
    fi
  else
    case "${algorithm}" in
    weighted_sssp|connected_components)
      [[ "${result_line}" == *"mismatches=0"* ]] && status=PASS
      ;;
    full_pagerank|residual_pagerank)
      if [[ "${result_line}" == *"rank_mismatches=0"* &&
            "${result_line}" == *"degree_mismatches=0"* ]]; then
        status=PASS
      fi
      ;;
    esac
  fi
fi

{
  printf 'STATUS=%s\n' "${status}"
  printf 'TARGET=hw\n'
  printf 'ALGORITHM=%s\n' "${algorithm}"
  printf 'DEVICE_INDEX=%s\n' "${device_index}"
  printf 'CONVERSION_COST=absent\n'
  printf 'MEASUREMENT_WINDOW=%s\n' "$([[ ${update_only} == 1 ]] && echo update_only || echo algorithm_e2e)"
  printf 'HOST_EXIT=%s\n' "${host_exit}"
  printf 'REPO_HEAD=%s\n' "${repo_head}"
  printf 'REPO_DIRTY=%s\n' "${repo_dirty}"
  printf 'HOST=%s\nHOST_SHA256=%s\n' "${host}" "$(sha256sum "${host}" | awk '{print $1}')"
  printf 'XCLBIN=%s\nXCLBIN_SHA256=%s\n' "${xclbin}" "$(sha256sum "${xclbin}" | awk '{print $1}')"
  printf 'GRAPH=%s\nGRAPH_SHA256=%s\n' "${graph}" "$(sha256sum "${graph}" | awk '{print $1}')"
  printf 'RUN_LOG_SHA256=%s\n' "$(sha256sum "${run_log}" | awk '{print $1}')"
  printf 'RESULT_LINE=%s\n' "${result_line}"
  printf 'TIMING_LINE=%s\n' "${timing_line}"
} >"${run_env}"

printf 'algorithm\tstatus\thost_exit\tdevice_index\tresult_line\ttiming_line\n' >"${summary}"
printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
  "${algorithm}" "${status}" "${host_exit}" "${device_index}" \
  "${result_line}" "${timing_line}" >>"${summary}"
(
  cd "${out_dir}"
  find . -type f ! -name evidence.sha256 -print0 | sort -z | xargs -0 sha256sum
) >"${out_dir}/evidence.sha256"

echo "PMA_NATIVE_HW_RUN status=${status} algorithm=${algorithm} evidence=${out_dir}"
[[ "${status}" == PASS ]]
