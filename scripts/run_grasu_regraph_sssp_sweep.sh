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
ALLOW_PASS_ON_NONZERO_EXIT=0
REGRAPH_SKIP_VERIFY=0
DEVICE_GRAPH_EXPORT=0
GRASU_HOST_EXPLICIT=0
XCL_EMULATION_MODE_VALUE="${XCL_EMULATION_MODE_VALUE:-}"
VITIS_SETTINGS="${VITIS_SETTINGS:-/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh}"
GRASU_EMCONFIG_PATH="${GRASU_EMCONFIG_PATH:-}"
REGRAPH_EMCONFIG_PATH="${REGRAPH_EMCONFIG_PATH:-}"

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
  3. export the actual post-update device graph, or use the labeled expected-result baseline
  4. run ReGraph SSSP with the requested source/supersteps

Options:
  --preset smoke|review|capacity
                              Workload preset. Default: ${PRESET}
  --workload-root PATH        Workload root. Default: workloads/sssp_benchmark_<preset>
  --out-root PATH             Result directory. Default: ${OUT_ROOT}
  --timeout SECONDS           Per-case timeout. Default: ${TIMEOUT_SECONDS}
  --regraph-num-dense N       ReGraph numD argument. Default: ${REGRAPH_NUM_DENSE}
  --result-base 10|16|auto    GraSU result ID base. Default: ${RESULT_BASE}
  --grasu-host PATH           GraSU host executable.
  --grasu-xclbin PATH         GraSU xclbin.
  --regraph-host PATH         ReGraph SSSP host executable.
  --regraph-xclbin PATH       ReGraph or combined xclbin.
  --combined-xclbin PATH      Use the same combined xclbin for GraSU and ReGraph.
  --xcl-emulation-mode MODE   Set XCL_EMULATION_MODE for both hosts, e.g. hw_emu.
  --vitis-settings PATH       Source Vitis settings before hw_emu runs.
                              Default: ${VITIS_SETTINGS}
  --grasu-emconfig-path PATH  EMCONFIG_PATH for GraSU hw_emu. Inferred if omitted.
  --regraph-emconfig-path PATH
                              EMCONFIG_PATH for ReGraph hw_emu. Inferred if omitted.
  --skip-generate             Reuse an existing workload manifest.
  --skip-grasu                Skip GraSU and use the expected result file directly.
  --allow-pass-on-nonzero-exit
                              Continue when a case summary is PASS even if the
                              wrapped host exits non-zero during teardown.
  --regraph-skip-verify       Set REGRAPH_SKIP_VERIFY=1 for ReGraph. The
                              summarizer reports these runs as PERF_ONLY, not
                              PASS, because hardware output is not read back.
  --device-graph-export       Pass an export path to a compatible GraSU host,
                              feed that actual post-update graph to ReGraph,
                              and use the expected result only for byte-level
                              verification. Incompatible with --skip-grasu.
  --dry-run                   Print commands without executing hardware runs.
  -h, --help                  Show this help.

Typical real-hw cold-start ReGraph run after the 250 MHz hw build exists:

  REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \\
  REGRAPH_XCLBIN=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin \\
  $0 --preset review

Typical combined-hw run:

  COMBINED_XCLBIN=/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz/build/grasu_regraph_combined.hw.xclbin \\
  REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \\
  $0 --preset review --combined-xclbin "\${COMBINED_XCLBIN}"
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

first_existing_emconfig_dir() {
  local candidate
  for candidate in "$@"; do
    if [[ -f "${candidate}/emconfig.json" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

infer_emconfig_path() {
  local role="$1"
  local xclbin="$2"
  local xclbin_dir
  local build_root

  xclbin_dir="$(dirname "${xclbin}")"
  build_root="$(dirname "${xclbin_dir}")"

  if [[ "${role}" == "grasu" ]]; then
    first_existing_emconfig_dir \
      "${build_root}/run_grasu_smoke" \
      "${build_root}/run" \
      "${xclbin_dir}" \
      "${build_root}" || true
  else
    first_existing_emconfig_dir \
      "${build_root}/run_regraph_tiny" \
      "${xclbin_dir}/xilinx_u55c_gen3x16_xdma_3_202210_1" \
      "${build_root}" \
      "${xclbin_dir}" || true
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset) PRESET="$2"; shift 2 ;;
    --workload-root) WORKLOAD_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --out-root) OUT_ROOT="$(abs_under_root "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --regraph-num-dense) REGRAPH_NUM_DENSE="$2"; shift 2 ;;
    --result-base) RESULT_BASE="$2"; shift 2 ;;
    --grasu-host) GRASU_HOST="$(abs_under_root "$2")"; GRASU_HOST_EXPLICIT=1; shift 2 ;;
    --grasu-xclbin) GRASU_XCLBIN="$(abs_under_root "$2")"; shift 2 ;;
    --regraph-host) REGRAPH_HOST="$(abs_under_root "$2")"; shift 2 ;;
    --regraph-xclbin) REGRAPH_XCLBIN="$(abs_under_root "$2")"; shift 2 ;;
    --combined-xclbin) GRASU_XCLBIN="$(abs_under_root "$2")"; REGRAPH_XCLBIN="${GRASU_XCLBIN}"; shift 2 ;;
    --xcl-emulation-mode) XCL_EMULATION_MODE_VALUE="$2"; shift 2 ;;
    --vitis-settings) VITIS_SETTINGS="$(abs_under_root "$2")"; shift 2 ;;
    --grasu-emconfig-path) GRASU_EMCONFIG_PATH="$(abs_under_root "$2")"; shift 2 ;;
    --regraph-emconfig-path) REGRAPH_EMCONFIG_PATH="$(abs_under_root "$2")"; shift 2 ;;
    --skip-generate) SKIP_GENERATE=1; shift ;;
    --skip-grasu) SKIP_GRASU=1; shift ;;
    --allow-pass-on-nonzero-exit) ALLOW_PASS_ON_NONZERO_EXIT=1; shift ;;
    --regraph-skip-verify) REGRAPH_SKIP_VERIFY=1; shift ;;
    --device-graph-export) DEVICE_GRAPH_EXPORT=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${PRESET}" in
  smoke|review|capacity) ;;
  *) echo "Invalid --preset: ${PRESET}" >&2; exit 2 ;;
esac

if [[ "${DEVICE_GRAPH_EXPORT}" == "1" && "${SKIP_GRASU}" == "1" ]]; then
  echo "--device-graph-export cannot be combined with --skip-grasu" >&2
  exit 2
fi

if [[ "${DEVICE_GRAPH_EXPORT}" == "1" && "${SKIP_GRASU}" == "0" && "${GRASU_HOST_EXPLICIT}" == "0" ]]; then
  if [[ -x "${GRASU_HOST}_export" ]]; then
    GRASU_HOST="${GRASU_HOST}_export"
  fi
fi

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

if [[ -n "${XCL_EMULATION_MODE_VALUE}" ]]; then
  if [[ -z "${GRASU_EMCONFIG_PATH}" && "${SKIP_GRASU}" == "0" ]]; then
    GRASU_EMCONFIG_PATH="$(infer_emconfig_path grasu "${GRASU_XCLBIN}")"
  fi
  if [[ -z "${REGRAPH_EMCONFIG_PATH}" ]]; then
    REGRAPH_EMCONFIG_PATH="$(infer_emconfig_path regraph "${REGRAPH_XCLBIN}")"
  fi
  if [[ "${DRY_RUN}" == "0" ]]; then
    if [[ -n "${VITIS_SETTINGS}" && -f "${VITIS_SETTINGS}" ]]; then
      # XRT hw_emu needs XILINX_VITIS and Vivado runtime paths in addition to XRT.
      # shellcheck disable=SC1090
      source "${VITIS_SETTINGS}"
    else
      echo "Missing Vitis settings for hw_emu: ${VITIS_SETTINGS}" >&2
      exit 1
    fi
    if [[ "${SKIP_GRASU}" == "0" && ( -z "${GRASU_EMCONFIG_PATH}" || ! -f "${GRASU_EMCONFIG_PATH}/emconfig.json" ) ]]; then
      echo "Missing GraSU EMCONFIG_PATH for hw_emu; pass --grasu-emconfig-path." >&2
      exit 1
    fi
    if [[ -z "${REGRAPH_EMCONFIG_PATH}" || ! -f "${REGRAPH_EMCONFIG_PATH}/emconfig.json" ]]; then
      echo "Missing ReGraph EMCONFIG_PATH for hw_emu; pass --regraph-emconfig-path." >&2
      exit 1
    fi
  fi
fi

printf "case\tstatus\twall_seconds\tvertices\tstatic_edges\tupdate_edges\tfinal_edges\tsource\tsupersteps\tconverted_edges\tgrasu_ms\tgrasu_mups\tregraph_e2e_ms\tregraph_mteps\tprocessed_edges\tgraph_edges\tmismatch_count\tresult_dir\n" > "${SUMMARY}"

while IFS=$'\t' read -r case_name family vertices static_edges update_edges final_edges source supersteps default_weight graph result regraph_sssp_edges expected metadata; do
  [[ -z "${case_name}" ]] && continue
  case_dir="${OUT_ROOT}/${case_name}"
  mkdir -p "${case_dir}"
  converted_edges="${case_dir}/${case_name}.from_grasu.sssp.edges"
  expected_converted_edges="${case_dir}/${case_name}.expected.sssp.edges"

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
    echo "expected_converted_regraph_sssp_edges=${expected_converted_edges}"
    echo "expected=${expected}"
    echo "metadata=${metadata}"
    echo "grasu_host=${GRASU_HOST}"
    echo "grasu_xclbin=${GRASU_XCLBIN}"
    echo "regraph_host=${REGRAPH_HOST}"
    echo "regraph_xclbin=${REGRAPH_XCLBIN}"
    echo "regraph_num_dense=${REGRAPH_NUM_DENSE}"
    echo "xcl_emulation_mode=${XCL_EMULATION_MODE_VALUE}"
    echo "grasu_emconfig_path=${GRASU_EMCONFIG_PATH}"
    echo "regraph_emconfig_path=${REGRAPH_EMCONFIG_PATH}"
    echo "skip_grasu=${SKIP_GRASU}"
    echo "allow_pass_on_nonzero_exit=${ALLOW_PASS_ON_NONZERO_EXIT}"
    echo "regraph_skip_verify=${REGRAPH_SKIP_VERIFY}"
    echo "device_graph_export=${DEVICE_GRAPH_EXPORT}"
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
        grasu_env=()
        if [[ -n "${XCL_EMULATION_MODE_VALUE}" ]]; then
          grasu_env+=(XCL_EMULATION_MODE="${XCL_EMULATION_MODE_VALUE}" EMCONFIG_PATH="${GRASU_EMCONFIG_PATH}")
        fi
        grasu_args=("${GRASU_XCLBIN}" "${graph}" "${result}")
        if [[ "${DEVICE_GRAPH_EXPORT}" == "1" ]]; then
          grasu_args+=("${converted_edges}")
        fi
        (cd "${GRASU_ROOT}" && timeout "${TIMEOUT_SECONDS}s" env "${grasu_env[@]}" "${GRASU_HOST}" "${grasu_args[@]}") > "${case_dir}/grasu.log" 2>&1
      else
        if [[ "${DEVICE_GRAPH_EXPORT}" == "1" ]]; then
          echo "+ (cd ${GRASU_ROOT} && ${GRASU_HOST} ${GRASU_XCLBIN} ${graph} ${result} ${converted_edges})"
        else
          echo "+ (cd ${GRASU_ROOT} && ${GRASU_HOST} ${GRASU_XCLBIN} ${graph} ${result})"
        fi
      fi
    else
      echo "[1/3] Skipping GraSU update/check."
      : > "${case_dir}/grasu.log"
    fi

    echo "[2/3] Verifying/selecting ReGraph weighted SSSP input..."
    conversion_output="${converted_edges}"
    if [[ "${DEVICE_GRAPH_EXPORT}" == "1" ]]; then
      conversion_output="${expected_converted_edges}"
    fi
    run_local_cmd "${SCRIPT_DIR}/grasu_result_to_regraph.py" \
      --input "${result}" \
      --output "${conversion_output}" \
      --base "${RESULT_BASE}" \
      --weight "${default_weight}" | tee "${case_dir}/convert.log"
    if [[ "${DEVICE_GRAPH_EXPORT}" == "1" && "${DRY_RUN}" == "0" ]]; then
      cmp "${converted_edges}" "${expected_converted_edges}"
      sha256sum "${converted_edges}" "${expected_converted_edges}" \
        > "${case_dir}/device_graph_export.sha256"
      echo "device graph export matches expected final edge set"
    fi

    echo "[3/3] Running ReGraph SSSP..."
    if [[ "${DRY_RUN}" == "0" ]]; then
      regraph_env=(REGRAPH_SOURCE="${source}")
      if [[ "${REGRAPH_SKIP_VERIFY}" == "1" ]]; then
        regraph_env+=(REGRAPH_SKIP_VERIFY=1)
      fi
      if [[ -n "${XCL_EMULATION_MODE_VALUE}" ]]; then
        regraph_env+=(XCL_EMULATION_MODE="${XCL_EMULATION_MODE_VALUE}" EMCONFIG_PATH="${REGRAPH_EMCONFIG_PATH}")
      fi
      (cd "${REGRAPH_ROOT}" && timeout "${TIMEOUT_SECONDS}s" env "${regraph_env[@]}" "${REGRAPH_HOST}" "${REGRAPH_XCLBIN}" "${converted_edges}" "${REGRAPH_NUM_DENSE}" "${supersteps}") > "${case_dir}/regraph.log" 2>&1
    else
      echo "+ (cd ${REGRAPH_ROOT} && REGRAPH_SOURCE=${source} REGRAPH_SKIP_VERIFY=${REGRAPH_SKIP_VERIFY} ${REGRAPH_HOST} ${REGRAPH_XCLBIN} ${converted_edges} ${REGRAPH_NUM_DENSE} ${supersteps})"
      : > "${case_dir}/regraph.log"
    fi
  ) > "${case_dir}/runner.log" 2>&1
  rc=$?
  set -e
  end_ns="$(date +%s%N)"
  elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))
  printf "wall_seconds\t%d.%03d\n" "$(( elapsed_ms / 1000 ))" "$(( elapsed_ms % 1000 ))" > "${case_dir}/wall_time.tsv"
  printf "exit_code\t%d\n" "${rc}" >> "${case_dir}/wall_time.tsv"

  summary_line="$("${SCRIPT_DIR}/summarize_sssp_chain_result.py" --no-header "${case_dir}")"
  printf '%s\n' "${summary_line}" >> "${SUMMARY}"
  printf '%s\n' "${summary_line}"
  case_status="$(printf '%s\n' "${summary_line}" | cut -f2)"

  if [[ "${rc}" -ne 0 ]]; then
    if [[ "${ALLOW_PASS_ON_NONZERO_EXIT}" == "1" && "${case_status}" == "PASS" ]]; then
      echo "Case exited ${rc} after producing a PASS summary; continuing because --allow-pass-on-nonzero-exit is set." >&2
      continue
    fi
    echo "Case failed: ${case_name}; see ${case_dir}/runner.log" >&2
    exit "${rc}"
  fi
done < <(tail -n +2 "${MANIFEST}")

echo "DONE summary=${SUMMARY}"
