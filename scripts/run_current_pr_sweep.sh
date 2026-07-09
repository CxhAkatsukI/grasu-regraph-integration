#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_ROOT="${OUT_ROOT:-${GRI_ROOT}/results/current_pr_sweep_$(date +%Y%m%d_%H%M%S)}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"
REGRAPH_NUM_DENSE="${REGRAPH_NUM_DENSE:-1}"

CASES=(
  "tiny_spread_v16_u8 spread 16 8"
  "tiny_hot_v16_u8 hot 16 8"
  "tiny_delete_v16_u8 delete-even 16 8"
  "small_spread_v4096_u1024 spread 4096 1024"
  "small_hot_v4096_u1024 hot 4096 1024"
  "medium_spread_v16384_u4096 spread 16384 4096"
  "medium_hot_v16384_u4096 hot 16384 4096"
  "large_spread_v65536_u16384 spread 65536 16384"
  "large_hot_v65536_u16384 hot 65536 16384"
)

usage() {
  cat <<USAGE
Usage: $0 [--out-root PATH] [--timeout SECONDS]

Runs a fixed current-system sweep:
  GraSU update/check -> result conversion -> ReGraph PR hw

Environment overrides:
  OUT_ROOT
  TIMEOUT_SECONDS
  REGRAPH_NUM_DENSE
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-root) OUT_ROOT="$2"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

mkdir -p "${OUT_ROOT}"
SUMMARY="${OUT_ROOT}/summary.tsv"

printf "case\tstatus\twall_seconds\tvertices\tstatic_edges\tupdate_edges\tfinal_edges\tconverted_edges\tgrasu_ms\tgrasu_mups\tregraph_vertices\tregraph_edges\tregraph_e2e_ms\tregraph_mteps\tprocessed_edges\tgraph_edges\tresult_dir\n" > "${SUMMARY}"

for spec in "${CASES[@]}"; do
  read -r case_name shape vertices updates <<< "${spec}"
  case_dir="${OUT_ROOT}/${case_name}"
  mkdir -p "${case_dir}"

  echo "=== ${case_name} shape=${shape} vertices=${vertices} updates=${updates} ==="
  start_ns="$(date +%s%N)"
  set +e
  timeout "${TIMEOUT_SECONDS}s" \
    "${SCRIPT_DIR}/run_grasu_regraph_pr.sh" \
      --case "${case_name}" \
      --shape "${shape}" \
      --vertices "${vertices}" \
      --updates "${updates}" \
      --result-dir "${case_dir}" \
      --regraph-num-dense "${REGRAPH_NUM_DENSE}" \
    > "${case_dir}/runner.log" 2>&1
  rc=$?
  set -e
  end_ns="$(date +%s%N)"
  elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))
  printf "wall_seconds\t%d.%03d\n" \
    "$(( elapsed_ms / 1000 ))" "$(( elapsed_ms % 1000 ))" \
    > "${case_dir}/wall_time.tsv"
  printf "exit_code\t%d\n" "${rc}" >> "${case_dir}/wall_time.tsv"

  "${SCRIPT_DIR}/summarize_chain_result.py" --no-header "${case_dir}" >> "${SUMMARY}"
  tail -n 1 "${SUMMARY}"
  if [[ "${rc}" -ne 0 ]]; then
    echo "Case failed: ${case_name}; see ${case_dir}/runner.log" >&2
    exit "${rc}"
  fi
done

echo "DONE summary=${SUMMARY}"
