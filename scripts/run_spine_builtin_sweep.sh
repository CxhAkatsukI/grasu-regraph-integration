#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

PRESET="smoke"
OUT_ROOT="${OUT_ROOT:-${GRI_ROOT}/results/spine_builtin_sweep_$(date +%Y%m%d_%H%M%S)}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
DRY_RUN=0
SPINE_HOST="${SPINE_HOST:-/home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke}"
SPINE_XCLBIN="${SPINE_XCLBIN:-/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin}"
SPINE_PARTITIONED_SPLIT_VALUE="${SPINE_PARTITIONED_SPLIT_VALUE:-1}"

usage() {
  cat <<USAGE
Usage: $0 [options]

Run Spine's built-in partitioned CSR e2e scenarios and summarize maint/conv
timings. These are scenario-level baselines; they are not identical-input
matches for the GraSU+ReGraph generated workloads.

Options:
  --preset smoke|review       Scenario preset. Default: ${PRESET}
  --out-root PATH             Result directory. Default: ${OUT_ROOT}
  --timeout SECONDS           Per-case timeout passed to host and timeout(1).
                              Default: ${TIMEOUT_SECONDS}
  --spine-host PATH           Spine host executable. Default: ${SPINE_HOST}
  --spine-xclbin PATH         Spine xclbin. Default: ${SPINE_XCLBIN}
  --dry-run                   Print commands without executing hardware runs.
  -h, --help                  Show this help.

Example:

  $0 --preset review --out-root results/spine_builtin_review_hw
USAGE
}

abs_under_root() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${GRI_ROOT}" "$1" ;;
  esac
}

case_specs() {
  case "$1" in
    smoke)
      cat <<'CASES'
hot_cold|--hot-cold
star_1024|--star 1024
fanout_1024_s64|--fanout 1024 64
CASES
      ;;
    review)
      cat <<'CASES'
hot_cold|--hot-cold
star_4096|--star 4096
star_65536|--star 65536
fanout_4096_s64|--fanout 4096 64
fanout_65536_s256|--fanout 65536 256
repeat_star_4096_b4|--repeat-star 4096 4
repeat_fanout_4096_b4_s64|--repeat-fanout 4096 4 64
duplicate_heavy_4096|--duplicate-heavy 4096
carry_l1|--carry-l1
carry_l3|--carry-l3
CASES
      ;;
    *)
      echo "Invalid preset: $1" >&2
      return 2
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset) PRESET="$2"; shift 2 ;;
    --out-root) OUT_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --spine-host) SPINE_HOST="$(abs_under_root "$2")"; shift 2 ;;
    --spine-xclbin) SPINE_XCLBIN="$(abs_under_root "$2")"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${PRESET}" in
  smoke|review) ;;
  *) echo "Invalid --preset: ${PRESET}" >&2; exit 2 ;;
esac

OUT_ROOT="$(abs_under_root "${OUT_ROOT}")"
mkdir -p "${OUT_ROOT}"
SUMMARY="${OUT_ROOT}/summary.tsv"

if [[ "${DRY_RUN}" == "0" ]]; then
  for required in "${SPINE_HOST}" "${SPINE_XCLBIN}"; do
    if [[ ! -e "${required}" ]]; then
      echo "Missing required path: ${required}" >&2
      exit 1
    fi
  done
fi

{
  echo "preset=${PRESET}"
  echo "spine_host=${SPINE_HOST}"
  echo "spine_xclbin=${SPINE_XCLBIN}"
  echo "timeout_seconds=${TIMEOUT_SECONDS}"
  echo "dry_run=${DRY_RUN}"
  echo "spine_partitioned_split=${SPINE_PARTITIONED_SPLIT_VALUE}"
} > "${OUT_ROOT}/manifest.env"

printf "case\tstatus\tscenario_tag\twall_seconds\tvertices\tinput_edges\tbatch_edges\tsource_count\thot_edges\tcold_edges\ttraversed_edges\tmaint_ms\tconv_ms\tkernel_e2e_ms\tkernel_mteps\terrors\targs\tresult_dir\n" > "${SUMMARY}"

while IFS='|' read -r case_name case_args; do
  [[ -z "${case_name}" ]] && continue
  case_dir="${OUT_ROOT}/${case_name}"
  mkdir -p "${case_dir}"
  {
    echo "case=${case_name}"
    echo "args=${case_args}"
    echo "spine_host=${SPINE_HOST}"
    echo "spine_xclbin=${SPINE_XCLBIN}"
    echo "timeout_seconds=${TIMEOUT_SECONDS}"
    echo "dry_run=${DRY_RUN}"
  } > "${case_dir}/case.env"

  echo "=== ${case_name} args=${case_args} ==="
  start_ns="$(date +%s%N)"
  set +e
  if [[ "${DRY_RUN}" == "0" ]]; then
    # shellcheck disable=SC2086
    timeout "${TIMEOUT_SECONDS}s" env SPINE_PARTITIONED_SPLIT="${SPINE_PARTITIONED_SPLIT_VALUE}" \
      "${SPINE_HOST}" "${SPINE_XCLBIN}" ${case_args} --timeout "${TIMEOUT_SECONDS}" \
      > "${case_dir}/spine.log" 2>&1
    rc=$?
  else
    {
      echo "+ env SPINE_PARTITIONED_SPLIT=${SPINE_PARTITIONED_SPLIT_VALUE} ${SPINE_HOST} ${SPINE_XCLBIN} ${case_args} --timeout ${TIMEOUT_SECONDS}"
    } > "${case_dir}/spine.log"
    rc=0
  fi
  set -e
  end_ns="$(date +%s%N)"
  elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))
  printf "wall_seconds\t%d.%03d\n" "$(( elapsed_ms / 1000 ))" "$(( elapsed_ms % 1000 ))" > "${case_dir}/wall_time.tsv"
  printf "exit_code\t%d\n" "${rc}" >> "${case_dir}/wall_time.tsv"

  "${SCRIPT_DIR}/summarize_spine_builtin_result.py" --no-header "${case_dir}" >> "${SUMMARY}"
  tail -n 1 "${SUMMARY}"

  if [[ "${rc}" -ne 0 ]]; then
    echo "Case failed: ${case_name}; see ${case_dir}/spine.log" >&2
    exit "${rc}"
  fi
done < <(case_specs "${PRESET}")

echo "DONE summary=${SUMMARY}"
