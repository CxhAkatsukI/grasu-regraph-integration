#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

CHAIN_ROOT="${GRI_ROOT}/results/grasu_regraph_sssp_review_combined_hw_20260712_195628"
OUT_ROOT="${OUT_ROOT:-${GRI_ROOT}/results/spine_edge_file_review_hw_$(date +%Y%m%d_%H%M%S)}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"
DRY_RUN=0
CONTINUE_ON_FAIL=0
SOURCE_XRT=1
SPINE_HOST="${SPINE_HOST:-/home/chuxiao/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke}"
SPINE_XCLBIN="${SPINE_XCLBIN:-/home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/xclbin/spine_partitioned_e2e.hw.xclbin}"
SPINE_PARTITIONED_SPLIT_VALUE="${SPINE_PARTITIONED_SPLIT_VALUE:-0}"

usage() {
  cat <<USAGE
Usage: $0 [options]

Run Spine's partitioned CSR host on edge files exported by the
GraSU+ReGraph SSSP sweep. Case names match the chain cases, so the resulting
summary can be joined directly for identical-edge-input timing comparison.

Options:
  --chain-root PATH           GraSU+ReGraph result root containing case dirs.
                              Default: ${CHAIN_ROOT}
  --out-root PATH             Result directory. Default: ${OUT_ROOT}
  --timeout SECONDS           Per-case timeout passed to host and timeout(1).
                              Default: ${TIMEOUT_SECONDS}
  --spine-host PATH           Spine host executable. Default: ${SPINE_HOST}
  --spine-xclbin PATH         Spine xclbin. Default: ${SPINE_XCLBIN}
  --continue-on-fail          Continue running later edge files after a case
                              exits non-zero or times out.
  --no-source-xrt             Do not source /opt/xilinx/xrt/setup.sh.
  --dry-run                   Print commands without executing hardware runs.
  -h, --help                  Show this help.

Example:

  $0 --chain-root results/grasu_regraph_sssp_review_combined_hw_20260712_195628
USAGE
}

abs_under_root() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${GRI_ROOT}" "$1" ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --chain-root) CHAIN_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --out-root) OUT_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --spine-host) SPINE_HOST="$(abs_under_root "$2")"; shift 2 ;;
    --spine-xclbin) SPINE_XCLBIN="$(abs_under_root "$2")"; shift 2 ;;
    --continue-on-fail) CONTINUE_ON_FAIL=1; shift ;;
    --no-source-xrt) SOURCE_XRT=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

CHAIN_ROOT="$(abs_under_root "${CHAIN_ROOT}")"
OUT_ROOT="$(abs_under_root "${OUT_ROOT}")"
mkdir -p "${OUT_ROOT}"
SUMMARY="${OUT_ROOT}/summary.tsv"

if [[ "${DRY_RUN}" == "0" ]]; then
  for required in "${CHAIN_ROOT}" "${SPINE_HOST}" "${SPINE_XCLBIN}"; do
    if [[ ! -e "${required}" ]]; then
      echo "Missing required path: ${required}" >&2
      exit 1
    fi
  done
fi

mapfile -t EDGE_FILES < <(
  find "${CHAIN_ROOT}" -mindepth 2 -maxdepth 2 -type f \
    -name '*.from_grasu.sssp.edges' | sort
)
if [[ "${#EDGE_FILES[@]}" -eq 0 ]]; then
  echo "No exported edge files found under ${CHAIN_ROOT}" >&2
  exit 1
fi

if [[ "${SOURCE_XRT}" == "1" && "${DRY_RUN}" == "0" ]]; then
  set +u +e
  # shellcheck disable=SC1091
  source /opt/xilinx/xrt/setup.sh
  xrt_status=$?
  set -euo pipefail
  if [[ "${xrt_status}" -ne 0 ]]; then
    echo "XRT setup returned ${xrt_status}" >&2
    exit "${xrt_status}"
  fi
fi

{
  echo "chain_root=${CHAIN_ROOT}"
  echo "spine_host=${SPINE_HOST}"
  echo "spine_xclbin=${SPINE_XCLBIN}"
  echo "timeout_seconds=${TIMEOUT_SECONDS}"
  echo "dry_run=${DRY_RUN}"
  echo "source_xrt=${SOURCE_XRT}"
  echo "spine_partitioned_split=${SPINE_PARTITIONED_SPLIT_VALUE}"
  echo "continue_on_fail=${CONTINUE_ON_FAIL}"
  if [[ "${DRY_RUN}" == "0" ]]; then
    sha256sum "${SPINE_HOST}" "${SPINE_XCLBIN}"
  fi
} > "${OUT_ROOT}/manifest.env"

printf "case\tstatus\tscenario_tag\twall_seconds\tvertices\tinput_edges\tbatch_edges\tsource_count\thot_edges\tcold_edges\ttraversed_edges\tmaint_ms\tconv_ms\tkernel_e2e_ms\tkernel_mteps\terrors\targs\tresult_dir\n" > "${SUMMARY}"

for edge_file in "${EDGE_FILES[@]}"; do
  case_dir_name="$(basename "$(dirname "${edge_file}")")"
  case_dir="${OUT_ROOT}/${case_dir_name}"
  mkdir -p "${case_dir}"
  {
    echo "case=${case_dir_name}"
    echo "args=--edge-file ${edge_file}"
    echo "edge_file=${edge_file}"
    echo "spine_host=${SPINE_HOST}"
    echo "spine_xclbin=${SPINE_XCLBIN}"
    echo "timeout_seconds=${TIMEOUT_SECONDS}"
    echo "dry_run=${DRY_RUN}"
    if [[ "${DRY_RUN}" == "0" ]]; then
      sha256sum "${edge_file}"
    fi
  } > "${case_dir}/case.env"

  echo "=== ${case_dir_name} edge_file=${edge_file} ==="
  start_ns="$(date +%s%N)"
  set +e
  if [[ "${DRY_RUN}" == "0" ]]; then
    timeout "${TIMEOUT_SECONDS}s" env \
      SPINE_PARTITIONED_SPLIT="${SPINE_PARTITIONED_SPLIT_VALUE}" \
      "${SPINE_HOST}" "${SPINE_XCLBIN}" \
      --edge-file "${edge_file}" --timeout "${TIMEOUT_SECONDS}" \
      > "${case_dir}/spine.log" 2>&1
    rc=$?
  else
    {
      echo "+ env SPINE_PARTITIONED_SPLIT=${SPINE_PARTITIONED_SPLIT_VALUE} ${SPINE_HOST} ${SPINE_XCLBIN} --edge-file ${edge_file} --timeout ${TIMEOUT_SECONDS}"
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
    if [[ "${CONTINUE_ON_FAIL}" == "1" ]]; then
      echo "Case failed: ${case_dir_name}; continuing because --continue-on-fail is set. See ${case_dir}/spine.log" >&2
      continue
    fi
    echo "Case failed: ${case_dir_name}; see ${case_dir}/spine.log" >&2
    exit "${rc}"
  fi
done

echo "DONE summary=${SUMMARY}"
