#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRI_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

matrix=""
out_dir=""
spine_root=/home/chuxiao/spine-dynamic-graph-paper-owner-fifos
spine_build_root=/data/feiyang/codex_builds/spine_paper_alignment/owner_fifo_hw_v1
gr_device=0
spine_device=1
timeout_seconds=1800
execution_mode=auto
gr_memory_gib=64
spine_memory_gib=64
memory_reserve_gib=16

usage() {
  cat <<USAGE
Usage: $0 --matrix MATRIX.tsv --out-dir DIR [options]

MATRIX.tsv columns:
  case  algorithm  graph  source  gr_host  gr_xclbin

Algorithms: weighted_sssp, connected_components, full_pagerank,
            residual_pagerank.

Options:
  --spine-root DIR        Spine source repository.
  --spine-build-root DIR  Routed Spine owner-FIFO xclbin root.
  --gr-device N           U55C device for G+R (default: 0).
  --spine-device N        U55C device for Spine (default: 1).
  --timeout SECONDS       Per-architecture host timeout (default: 1800).
  --execution-mode MODE   auto, concurrent, or serial (default: auto).
  --gr-memory-gib N       G+R process memory ceiling (default: 64 GiB).
  --spine-memory-gib N    Spine process memory ceiling (default: 64 GiB).
  --memory-reserve-gib N  Memory kept outside experiment processes
                          (default: 16 GiB).
USAGE
}

while (( $# > 0 )); do
  case "$1" in
    --matrix) matrix=$2; shift 2 ;;
    --out-dir) out_dir=$2; shift 2 ;;
    --spine-root) spine_root=$2; shift 2 ;;
    --spine-build-root) spine_build_root=$2; shift 2 ;;
    --gr-device) gr_device=$2; shift 2 ;;
    --spine-device) spine_device=$2; shift 2 ;;
    --timeout) timeout_seconds=$2; shift 2 ;;
    --execution-mode) execution_mode=$2; shift 2 ;;
    --gr-memory-gib) gr_memory_gib=$2; shift 2 ;;
    --spine-memory-gib) spine_memory_gib=$2; shift 2 ;;
    --memory-reserve-gib) memory_reserve_gib=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${matrix}" || -z "${out_dir}" ]]; then
  usage >&2
  exit 2
fi
for numeric in gr_device spine_device timeout_seconds gr_memory_gib \
    spine_memory_gib memory_reserve_gib; do
  if ! [[ "${!numeric}" =~ ^[0-9]+$ ]]; then
    echo "${numeric} must be a non-negative integer" >&2
    exit 2
  fi
done
case "${execution_mode}" in
  auto|concurrent|serial) ;;
  *) echo "execution_mode must be auto, concurrent, or serial" >&2; exit 2 ;;
esac
if (( gr_device == spine_device )); then
  echo "G+R and Spine must use distinct devices for concurrent execution" >&2
  exit 2
fi
if (( gr_memory_gib == 0 || spine_memory_gib == 0 )); then
  echo "architecture memory ceilings must be positive" >&2
  exit 2
fi
if [[ ! -f "${matrix}" || ! -d "${spine_root}" ]]; then
  echo "matrix or Spine repository is missing" >&2
  exit 1
fi

matrix=$(realpath "${matrix}")
out_dir=$(realpath -m "${out_dir}")
spine_root=$(realpath "${spine_root}")
spine_build_root=$(realpath "${spine_build_root}")
mkdir -p "${out_dir}"
cp "${matrix}" "${out_dir}/matrix.tsv"

mem_available_kib() {
  awk '/^MemAvailable:/ {print $2; exit}' /proc/meminfo
}

run_with_memory_cap() {
  local cap_gib=$1
  shift
  (
    ulimit -v $((cap_gib * 1024 * 1024))
    exec "$@"
  )
}

effective_serial_cap_gib() {
  local requested=$1
  local available_gib=$(( $(mem_available_kib) / 1024 / 1024 ))
  local safe_gib=$((available_gib - memory_reserve_gib))
  if (( safe_gib < 4 )); then
    return 1
  fi
  if (( requested < safe_gib )); then
    printf '%s\n' "${requested}"
  else
    printf '%s\n' "${safe_gib}"
  fi
}

printf 'case\talgorithm\texecution_mode\tgr_memory_gib\tspine_memory_gib\tgr_exit\tspine_exit\n' \
  >"${out_dir}/launch_status.tsv"
tail -n +2 "${matrix}" |
while IFS=$'\t' read -r case algorithm graph source gr_host gr_xclbin rest; do
  [[ -z "${case}" ]] && continue
  case "${algorithm}" in
    weighted_sssp) spine_tag=sssp ;;
    connected_components) spine_tag=cc ;;
    full_pagerank) spine_tag=fullpr ;;
    residual_pagerank) spine_tag=respr ;;
    *) echo "unsupported algorithm in ${case}: ${algorithm}" >&2; exit 2 ;;
  esac
  for path in graph gr_host gr_xclbin; do
    if [[ ! -f "${!path}" ]]; then
      echo "missing ${path} for ${case}: ${!path}" >&2
      exit 1
    fi
  done

  case_root="${out_dir}/${case}"
  gr_out="${case_root}/grasu_regraph"
  spine_out="${case_root}/spine"
  mkdir -p "${case_root}"
  case_mode=${execution_mode}
  if [[ "${case_mode}" == auto ]]; then
    available_gib=$(( $(mem_available_kib) / 1024 / 1024 ))
    concurrent_required_gib=$((
      gr_memory_gib + spine_memory_gib + memory_reserve_gib
    ))
    if (( available_gib >= concurrent_required_gib )); then
      case_mode=concurrent
    else
      case_mode=serial
    fi
  fi

  if [[ "${case_mode}" == concurrent ]]; then
    available_gib=$(( $(mem_available_kib) / 1024 / 1024 ))
    concurrent_required_gib=$((
      gr_memory_gib + spine_memory_gib + memory_reserve_gib
    ))
    if (( available_gib < concurrent_required_gib )); then
      echo "insufficient memory for concurrent ${case}: available=${available_gib}GiB required=${concurrent_required_gib}GiB" >&2
      exit 1
    fi
    gr_case_memory_gib=${gr_memory_gib}
    spine_case_memory_gib=${spine_memory_gib}
  else
    gr_case_memory_gib=$(effective_serial_cap_gib "${gr_memory_gib}") || {
      echo "insufficient memory reserve before G+R ${case}" >&2
      exit 1
    }
    spine_case_memory_gib=0
  fi
  echo "MATCHED_FPGA_CASE_START case=${case} algorithm=${algorithm} mode=${case_mode} gr_memory_gib=${gr_case_memory_gib}"

  set +e
  run_with_memory_cap "${gr_case_memory_gib}" \
    timeout --signal=TERM --kill-after=15s "${timeout_seconds}s" \
    "${GRI_ROOT}/scripts/run_pma_native_hw.sh" \
      --algorithm "${algorithm}" --host "${gr_host}" \
      --xclbin "${gr_xclbin}" --graph "${graph}" --out-dir "${gr_out}" \
      --device-index "${gr_device}" --source "${source}" \
      --timeout "${timeout_seconds}" \
      >"${case_root}/grasu_regraph.launch.log" 2>&1 &
  gr_pid=$!
  if [[ "${case_mode}" == concurrent ]]; then
    run_with_memory_cap "${spine_case_memory_gib}" \
      timeout --signal=TERM --kill-after=15s "${timeout_seconds}s" \
      env XCL_DEVICE_INDEX="${spine_device}" \
      "${spine_root}/tests/test_integration/run_partitioned_dynamic_algorithm_hw.sh" \
        "${spine_build_root}" "${spine_out}" "${spine_tag}" \
        "${graph}" "${source}" \
        >"${case_root}/spine.launch.log" 2>&1 &
    spine_pid=$!
    wait "${gr_pid}"; gr_exit=$?
    wait "${spine_pid}"; spine_exit=$?
  else
    wait "${gr_pid}"; gr_exit=$?
    spine_case_memory_gib=$(effective_serial_cap_gib "${spine_memory_gib}") || {
      echo "insufficient memory reserve before Spine ${case}" >&2
      exit 1
    }
    run_with_memory_cap "${spine_case_memory_gib}" \
      timeout --signal=TERM --kill-after=15s "${timeout_seconds}s" \
      env XCL_DEVICE_INDEX="${spine_device}" \
      "${spine_root}/tests/test_integration/run_partitioned_dynamic_algorithm_hw.sh" \
        "${spine_build_root}" "${spine_out}" "${spine_tag}" \
        "${graph}" "${source}" \
        >"${case_root}/spine.launch.log" 2>&1
    spine_exit=$?
  fi
  set -e

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${case}" "${algorithm}" "${case_mode}" \
    "${gr_case_memory_gib}" "${spine_case_memory_gib}" \
    "${gr_exit}" "${spine_exit}" \
    >>"${out_dir}/launch_status.tsv"
  echo "MATCHED_FPGA_CASE_DONE case=${case} gr_exit=${gr_exit} spine_exit=${spine_exit}"
done

python3 "${SCRIPT_DIR}/summarize_matched_fpga_matrix.py" \
  --matrix "${out_dir}/matrix.tsv" --run-root "${out_dir}" \
  --output "${out_dir}/summary.tsv"

if rg -q $'\tREJECTED\t' "${out_dir}/summary.tsv"; then
  echo "one or more matched rows failed correctness/timing admission" >&2
  exit 1
fi
echo "MATCHED_FPGA_MATRIX_PASS evidence=${out_dir}"
