#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

PRESET="boundary"
WORKLOAD_ROOT=""
HOST="${GRI_ROOT}/.tmp_build/pure_pipeline_host_stage0/pure_pipeline_host"
OUT_DIR=""
TIMEOUT_SECONDS=120
SKIP_GENERATE=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Run pure-pipeline host preparation checks without loading an xclbin. This
validates graph ingest, V<=65536 bounds, GraSU PMA packing, and the CPU oracle
for a workload manifest. It is intended for large boundary cases that are too
slow for sw_emu but must still have reproducible capacity evidence.

Options:
  --preset smoke|review|boundary|pure_stage0|capacity
                              Workload preset. Default: ${PRESET}
  --workload-root PATH        Workload root. Default: workloads/sssp_benchmark_<preset>
  --host PATH                 pure_pipeline_host binary. Default: ${HOST}
  --out-dir PATH              Output directory. Default: results/pure_pipeline_prepare_<preset>_<timestamp>
  --timeout SECONDS           Per-case timeout. Default: ${TIMEOUT_SECONDS}
  --skip-generate             Reuse an existing workload manifest.
  -h, --help                  Show this help.
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
    --preset) PRESET="$2"; shift 2 ;;
    --workload-root) WORKLOAD_ROOT="$(abs_path "$2")"; shift 2 ;;
    --host) HOST="$(abs_path "$2")"; shift 2 ;;
    --out-dir) OUT_DIR="$(abs_path "$2")"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    --skip-generate) SKIP_GENERATE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "${PRESET}" in
  smoke|review|boundary|pure_stage0|capacity) ;;
  *) echo "Invalid --preset: ${PRESET}" >&2; exit 2 ;;
esac

cd "${GRI_ROOT}"

if [[ -z "${WORKLOAD_ROOT}" ]]; then
  WORKLOAD_ROOT="${GRI_ROOT}/workloads/sssp_benchmark_${PRESET}"
fi
if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/results/pure_pipeline_prepare_${PRESET}_$(date +%Y%m%d_%H%M%S)"
fi

MANIFEST="${WORKLOAD_ROOT}/manifest.tsv"
mkdir -p "${OUT_DIR}"

if [[ "${SKIP_GENERATE}" == "0" ]]; then
  "${SCRIPT_DIR}/generate_sssp_benchmark_workloads.py" \
    --preset "${PRESET}" \
    --out-root "${WORKLOAD_ROOT}" | tee "${OUT_DIR}/generate_workloads.log"
fi

if [[ ! -x "${HOST}" ]]; then
  echo "Missing executable host runner: ${HOST}" >&2
  exit 1
fi
if [[ ! -f "${MANIFEST}" ]]; then
  echo "Missing manifest: ${MANIFEST}" >&2
  exit 1
fi

SUMMARY="${OUT_DIR}/summary.tsv"
ENV_FILE="${OUT_DIR}/run.env"

{
  printf 'preset=%s\n' "${PRESET}"
  printf 'host=%s\n' "${HOST}"
  printf 'manifest=%s\n' "${MANIFEST}"
  printf 'out_dir=%s\n' "${OUT_DIR}"
  printf 'timeout_seconds=%s\n' "${TIMEOUT_SECONDS}"
  printf 'host_sha256='
  sha256sum "${HOST}" | awk '{print $1}'
  printf 'manifest_sha256='
  sha256sum "${MANIFEST}" | awk '{print $1}'
  printf 'git_head='
  git -C "${GRI_ROOT}" rev-parse HEAD
} > "${ENV_FILE}"

printf 'case\tfamily\tvertices\tupdates\tfinal_edges\tsource\tsupersteps\texit_code\tstatus\tlog\tinput_line\tprep_line\n' > "${SUMMARY}"

failures=0
while IFS=$'\t' read -r case family vertices static_edges updates final_edges source supersteps weight graph result regraph_edges expected metadata; do
  if [[ "${case}" == "case" ]]; then
    continue
  fi

  log="${OUT_DIR}/${case}.log"
  echo "preparing ${case} (${family}) vertices=${vertices} source=${source} supersteps=${supersteps}"
  set +e
  timeout "${TIMEOUT_SECONDS}s" "${HOST}" --prepare-only "${graph}" "${result}" "${source}" "${supersteps}" \
    2>&1 | tee "${log}"
  rc=${PIPESTATUS[0]}
  set -e

  input_line="$(grep 'PURE_PIPELINE_INPUT' "${log}" | tail -n 1 || true)"
  prep_line="$(grep 'PURE_PIPELINE_PREP' "${log}" | tail -n 1 || true)"
  status="FAIL"
  if [[ ${rc} -eq 0 && "${prep_line}" == *"status=PASS"* ]]; then
    status="PASS"
  else
    failures=$((failures + 1))
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${case}" "${family}" "${vertices}" "${updates}" "${final_edges}" \
    "${source}" "${supersteps}" "${rc}" "${status}" "${log}" \
    "${input_line//$'\t'/ }" "${prep_line//$'\t'/ }" >> "${SUMMARY}"
done < "${MANIFEST}"

echo "summary: ${SUMMARY}"
if [[ ${failures} -ne 0 ]]; then
  echo "pure pipeline prepare-check failures: ${failures}" >&2
  exit 1
fi

echo "pure pipeline prepare-check passed"
