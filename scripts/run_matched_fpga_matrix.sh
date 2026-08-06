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
memory_poll_seconds=1
active_process_groups=()

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
  --memory-poll-seconds N Runtime MemAvailable polling interval
                          (default: 1 second).
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
    --memory-poll-seconds) memory_poll_seconds=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${matrix}" || -z "${out_dir}" ]]; then
  usage >&2
  exit 2
fi
for numeric in gr_device spine_device timeout_seconds gr_memory_gib \
    spine_memory_gib memory_reserve_gib memory_poll_seconds; do
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
if (( memory_poll_seconds == 0 )); then
  echo "--memory-poll-seconds must be positive" >&2
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
  ulimit -v $((cap_gib * 1024 * 1024))
  exec setsid "$@"
}

terminate_process_group() {
  local pid=$1
  kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
}

kill_process_group() {
  local pid=$1
  kill -KILL -- "-${pid}" 2>/dev/null || kill -KILL "${pid}" 2>/dev/null || true
}

cleanup_active_process_groups() {
  (( ${#active_process_groups[@]} != 0 )) || return 0
  local pid
  for pid in "${active_process_groups[@]}"; do
    terminate_process_group "${pid}"
  done
  sleep 1
  for pid in "${active_process_groups[@]}"; do
    kill_process_group "${pid}"
  done
  active_process_groups=()
}

stop_memory_guard() {
  local guard_pid=$1
  kill -TERM "${guard_pid}" 2>/dev/null || true
  wait "${guard_pid}" 2>/dev/null || true
}

memory_guard() {
  local marker=$1
  local label=$2
  shift 2
  local reserve_kib=$((memory_reserve_gib * 1024 * 1024))
  trap 'exit 0' INT TERM
  while true; do
    local any_alive=0
    local pid
    for pid in "$@"; do
      if kill -0 "${pid}" 2>/dev/null; then
        any_alive=1
        break
      fi
    done
    (( any_alive != 0 )) || return 0

    local available_kib
    available_kib=$(mem_available_kib)
    if (( available_kib < reserve_kib )); then
      printf 'MEMORY_GUARD_TRIPPED label=%s available_kib=%s reserve_kib=%s pids=%s\n' \
        "${label}" "${available_kib}" "${reserve_kib}" "$*" |
        tee -a "${out_dir}/memory_guard.log" >"${marker}"
      for pid in "$@"; do
        terminate_process_group "${pid}"
      done
      sleep 2
      for pid in "$@"; do
        kill_process_group "${pid}"
      done
      return 0
    fi
    sleep "${memory_poll_seconds}"
  done
}

trap 'cleanup_active_process_groups; exit 130' INT TERM
trap cleanup_active_process_groups EXIT

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

printf 'case\talgorithm\texecution_mode\tgr_memory_gib\tspine_memory_gib\tgr_exit\tspine_exit\tmemory_guard\n' \
  >"${out_dir}/launch_status.tsv"
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
  rm -f "${case_root}/grasu_regraph.memory_guard" \
    "${case_root}/spine.memory_guard" "${case_root}/concurrent.memory_guard"
  case_guard_status=PASS
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
  active_process_groups=("${gr_pid}")
  if [[ "${case_mode}" == concurrent ]]; then
    run_with_memory_cap "${spine_case_memory_gib}" \
      timeout --signal=TERM --kill-after=15s "${timeout_seconds}s" \
      env XCL_DEVICE_INDEX="${spine_device}" \
      "${spine_root}/tests/test_integration/run_partitioned_dynamic_algorithm_hw.sh" \
        "${spine_build_root}" "${spine_out}" "${spine_tag}" \
        "${graph}" "${source}" \
        >"${case_root}/spine.launch.log" 2>&1 &
    spine_pid=$!
    active_process_groups=("${gr_pid}" "${spine_pid}")
    memory_guard "${case_root}/concurrent.memory_guard" \
      "${case}:concurrent" "${gr_pid}" "${spine_pid}" &
    guard_pid=$!
    wait "${gr_pid}"; gr_exit=$?
    wait "${spine_pid}"; spine_exit=$?
    stop_memory_guard "${guard_pid}"
    if [[ -f "${case_root}/concurrent.memory_guard" ]]; then
      gr_exit=125
      spine_exit=125
      case_guard_status=TRIPPED_CONCURRENT
    fi
    active_process_groups=()
  else
    memory_guard "${case_root}/grasu_regraph.memory_guard" \
      "${case}:grasu_regraph" "${gr_pid}" &
    guard_pid=$!
    wait "${gr_pid}"; gr_exit=$?
    stop_memory_guard "${guard_pid}"
    active_process_groups=()
    if [[ -f "${case_root}/grasu_regraph.memory_guard" ]]; then
      gr_exit=125
      spine_exit=125
      case_guard_status=TRIPPED_GR
      spine_case_memory_gib=0
    else
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
          >"${case_root}/spine.launch.log" 2>&1 &
      spine_pid=$!
      active_process_groups=("${spine_pid}")
      memory_guard "${case_root}/spine.memory_guard" \
        "${case}:spine" "${spine_pid}" &
      guard_pid=$!
      wait "${spine_pid}"; spine_exit=$?
      stop_memory_guard "${guard_pid}"
      if [[ -f "${case_root}/spine.memory_guard" ]]; then
        spine_exit=125
        case_guard_status=TRIPPED_SPINE
      fi
      active_process_groups=()
    fi
  fi
  set -e

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${case}" "${algorithm}" "${case_mode}" \
    "${gr_case_memory_gib}" "${spine_case_memory_gib}" \
    "${gr_exit}" "${spine_exit}" "${case_guard_status}" \
    >>"${out_dir}/launch_status.tsv"
  echo "MATCHED_FPGA_CASE_DONE case=${case} gr_exit=${gr_exit} spine_exit=${spine_exit}"
done < <(tail -n +2 "${matrix}")

python3 "${SCRIPT_DIR}/summarize_matched_fpga_matrix.py" \
  --matrix "${out_dir}/matrix.tsv" --run-root "${out_dir}" \
  --output "${out_dir}/summary.tsv"

if rg -q $'\tREJECTED\t' "${out_dir}/summary.tsv"; then
  echo "one or more matched rows failed correctness/timing admission" >&2
  exit 1
fi
echo "MATCHED_FPGA_MATRIX_PASS evidence=${out_dir}"
