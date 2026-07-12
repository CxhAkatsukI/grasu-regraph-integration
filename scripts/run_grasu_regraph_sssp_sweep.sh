#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

PRESET="smoke"
WORKLOAD_ROOT=""
OUT_ROOT="${OUT_ROOT:-${GRI_ROOT}/results/grasu_regraph_sssp_sweep_$(date +%Y%m%d_%H%M%S)}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-600}"
REGRAPH_NUM_DENSE="${REGRAPH_NUM_DENSE:-1}"
RESULT_BASE="${RESULT_BASE:-16}"
SKIP_GENERATE=0
SKIP_GRASU=0
DRY_RUN=0
XCL_EMULATION_MODE_VALUE="${XCL_EMULATION_MODE_VALUE:-}"

GRASU_HOST="${GRASU_HOST:-${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/GraSU_host_u55c}"
GRASU_XCLBIN="${GRASU_XCLBIN:-${GRASU_ROOT}/.tmp_build/u55c_hbm_hw/build/GraSU_u55c_hbm.hw.xclbin}"
REGRAPH_HOST="${REGRAPH_HOST:-/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/host_graph_fpga_sssp}"
REGRAPH_XCLBIN="${REGRAPH_XCLBIN:-/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/xclbin_hw_emu_sssp/graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin}"

usage() {
  cat <<USAGE
Usage: $0 [options]

Run a reproducible GraSU -> ReGraph weighted-SSSP sweep:
  1. generate or reuse GraSU graph/result workloads
  2. run GraSU update/check
  3. convert the final result edge set to ReGraph's weighted SSSP input
  4. run ReGraph SSSP with the requested source/supersteps

Options:
  --preset smoke|review       Workload preset. Default: ${PRESET}
  --workload-root PATH        Workload root. Default: workloads/sssp_benchmark_<preset>
  --out-root PATH             Result directory. Default: ${OUT_ROOT}
  --timeout SECONDS           Per-case timeout. Default: ${TIMEOUT_SECONDS}
  --regraph-num-dense N       ReGraph numD argument. Default: ${REGRAPH_NUM_DENSE}
  --result-base 10|16|auto    GraSU result ID base. Default: ${RESULT_BASE}
  --grasu-host PATH           GraSU host executable.
  --grasu-xclbin PATH         GraSU xclbin.
  --regraph-host PATH         ReGraph SSSP host executable.
  --regraph-xclbin PATH       ReGraph or combined xclbin.
  --xcl-emulation-mode MODE   Set XCL_EMULATION_MODE for ReGraph, e.g. hw_emu.
  --skip-generate             Reuse an existing workload manifest.
  --skip-grasu                Skip GraSU and use the expected result file directly.
  --dry-run                   Print commands without executing hardware runs.
  -h, --help                  Show this help.

Typical real-hw cold-start ReGraph run after the 250 MHz hw build exists:

  REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \\
  REGRAPH_XCLBIN=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin \\
  $0 --preset review

Typical combined-hw run:

  REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \\
  REGRAPH_XCLBIN=/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz/build/grasu_regraph_combined.hw.xclbin \\
  $0 --preset review
USAGE
}

abs_under_root() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "${GRI_ROOT}" "$1" ;;
  esac
}

run_local_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  "$@"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset) PRESET="$2"; shift 2 ;;
    --workload-root) WORKLOAD_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --out-root) OUT_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --regraph-num-dense) REGRAPH_NUM_DENSE="$2"; shift 2 ;;
    --result-base) RESULT_BASE="$2"; shift 2 ;;
    --grasu-host) GRASU_HOST="$(abs_under_root "$2")"; shift 2 ;;
    --grasu-xclbin) GRASU_XCLBIN="$(abs_under_root "$2")"; shift 2 ;;
    --regraph-host) REGRAPH_HOST="$(abs_under_root "$2")"; shift 2 ;;
    --regraph-xclbin) REGRAPH_XCLBIN="$(abs_under_root "$2")"; shift 2 ;;
    --xcl-emulation-mode) XCL_EMULATION_MODE_VALUE="$2"; shift 2 ;;
    --skip-generate) SKIP_GENERATE=1; shift ;;
    --skip-grasu) SKIP_GRASU=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${PRESET}" in
  smoke|review) ;;
  *) echo "Invalid --preset: ${PRESET}" >&2; exit 2 ;;
esac

if [[ -z "${WORKLOAD_ROOT}" ]]; then
  WORKLOAD_ROOT="${GRI_ROOT}/workloads/sssp_benchmark_${PRESET}"
fi
WORKLOAD_ROOT="$(abs_under_root "${WORKLOAD_ROOT}")"
OUT_ROOT="$(abs_under_root "${OUT_ROOT}")"
MANIFEST="${WORKLOAD_ROOT}/manifest.tsv"
SUMMARY="${OUT_ROOT}/summary.tsv"

mkdir -p "${OUT_ROOT}"

if [[ "${SKIP_GENERATE}" == "0" ]]; then
  "${SCRIPT_DIR}/generate_sssp_benchmark_workloads.py" \
    --preset "${PRESET}" \
    --out-root "${WORKLOAD_ROOT}" | tee "${OUT_ROOT}/generate_workloads.log"
fi

if [[ ! -f "${MANIFEST}" ]]; then
  echo "Missing workload manifest: ${MANIFEST}" >&2
  exit 1
fi

if [[ "${DRY_RUN}" == "0" ]]; then
  required_paths=("${REGRAPH_HOST}" "${REGRAPH_XCLBIN}")
  if [[ "${SKIP_GRASU}" == "0" ]]; then
    required_paths+=("${GRASU_HOST}" "${GRASU_XCLBIN}")
  fi
  for required in "${required_paths[@]}"; do
    if [[ ! -e "${required}" ]]; then
      echo "Missing required path: ${required}" >&2
      exit 1
    fi
  done
fi

printf "case\tstatus\twall_seconds\tvertices\tstatic_edges\tupdate_edges\tfinal_edges\tsource\tsupersteps\tconverted_edges\tgrasu_ms\tgrasu_mups\tregraph_e2e_ms\tregraph_mteps\tprocessed_edges\tgraph_edges\tmismatch_count\tresult_dir\n" > "${SUMMARY}"

while IFS=$'\t' read -r case_name family vertices static_edges update_edges final_edges source supersteps default_weight graph result regraph_sssp_edges expected metadata; do
  [[ -z "${case_name}" ]] && continue
  case_dir="${OUT_ROOT}/${case_name}"
  mkdir -p "${case_dir}"
  converted_edges="${case_dir}/${case_name}.from_grasu.sssp.edges"

  {
    echo "case=${case_name}"
    echo "family=${family}"
    echo "vertices=${vertices}"
    echo "static_edges=${static_edges}"
    echo "update_edges=${update_edges}"
    echo "final_edges=${final_edges}"
    echo "source=${source}"
    echo "supersteps=${supersteps}"
    echo "default_weight=${default_weight}"
    echo "graph=${graph}"
    echo "result=${result}"
    echo "generated_regraph_sssp_edges=${regraph_sssp_edges}"
    echo "converted_regraph_sssp_edges=${converted_edges}"
    echo "expected=${expected}"
    echo "metadata=${metadata}"
    echo "grasu_host=${GRASU_HOST}"
    echo "grasu_xclbin=${GRASU_XCLBIN}"
    echo "regraph_host=${REGRAPH_HOST}"
    echo "regraph_xclbin=${REGRAPH_XCLBIN}"
    echo "regraph_num_dense=${REGRAPH_NUM_DENSE}"
    echo "skip_grasu=${SKIP_GRASU}"
    echo "dry_run=${DRY_RUN}"
  } > "${case_dir}/case.env"

  echo "=== ${case_name} family=${family} vertices=${vertices} updates=${update_edges} supersteps=${supersteps} ==="
  start_ns="$(date +%s%N)"
  set +e
  (
    set -euo pipefail
    if [[ "${SKIP_GRASU}" == "0" ]]; then
      echo "[1/3] Running GraSU update/check..."
      if [[ "${DRY_RUN}" == "0" ]]; then
        (cd "${GRASU_ROOT}" && timeout "${TIMEOUT_SECONDS}s" "${GRASU_HOST}" "${GRASU_XCLBIN}" "${graph}" "${result}") > "${case_dir}/grasu.log" 2>&1
      else
        echo "+ (cd ${GRASU_ROOT} && ${GRASU_HOST} ${GRASU_XCLBIN} ${graph} ${result})"
      fi
    else
      echo "[1/3] Skipping GraSU update/check."
      : > "${case_dir}/grasu.log"
    fi

    echo "[2/3] Converting GraSU result to ReGraph weighted SSSP input..."
    run_local_cmd "${SCRIPT_DIR}/grasu_result_to_regraph.py" \
      --input "${result}" \
      --output "${converted_edges}" \
      --base "${RESULT_BASE}" \
      --weight "${default_weight}" | tee "${case_dir}/convert.log"

    echo "[3/3] Running ReGraph SSSP..."
    if [[ "${DRY_RUN}" == "0" ]]; then
      if [[ -n "${XCL_EMULATION_MODE_VALUE}" ]]; then
        (cd "${REGRAPH_ROOT}" && timeout "${TIMEOUT_SECONDS}s" env XCL_EMULATION_MODE="${XCL_EMULATION_MODE_VALUE}" REGRAPH_SOURCE="${source}" "${REGRAPH_HOST}" "${REGRAPH_XCLBIN}" "${converted_edges}" "${REGRAPH_NUM_DENSE}" "${supersteps}") > "${case_dir}/regraph.log" 2>&1
      else
        (cd "${REGRAPH_ROOT}" && timeout "${TIMEOUT_SECONDS}s" env REGRAPH_SOURCE="${source}" "${REGRAPH_HOST}" "${REGRAPH_XCLBIN}" "${converted_edges}" "${REGRAPH_NUM_DENSE}" "${supersteps}") > "${case_dir}/regraph.log" 2>&1
      fi
    else
      echo "+ (cd ${REGRAPH_ROOT} && REGRAPH_SOURCE=${source} ${REGRAPH_HOST} ${REGRAPH_XCLBIN} ${converted_edges} ${REGRAPH_NUM_DENSE} ${supersteps})"
      : > "${case_dir}/regraph.log"
    fi
  ) > "${case_dir}/runner.log" 2>&1
  rc=$?
  set -e
  end_ns="$(date +%s%N)"
  elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))
  printf "wall_seconds\t%d.%03d\n" "$(( elapsed_ms / 1000 ))" "$(( elapsed_ms % 1000 ))" > "${case_dir}/wall_time.tsv"
  printf "exit_code\t%d\n" "${rc}" >> "${case_dir}/wall_time.tsv"

  "${SCRIPT_DIR}/summarize_sssp_chain_result.py" --no-header "${case_dir}" >> "${SUMMARY}"
  tail -n 1 "${SUMMARY}"

  if [[ "${rc}" -ne 0 ]]; then
    echo "Case failed: ${case_name}; see ${case_dir}/runner.log" >&2
    exit "${rc}"
  fi
done < <(tail -n +2 "${MANIFEST}")

echo "DONE summary=${SUMMARY}"
