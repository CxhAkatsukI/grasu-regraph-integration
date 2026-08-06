#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRI_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SIM_ROOT="${SIM_ROOT:-/home/chuxiao/spine-cycle-sim-architecture-alignment}"
OUT_DIR="${1:-/data/tmp/chuxiao/matched_fpga_bridge_workloads_20260806}"

mkdir -p "${OUT_DIR}"

convert() {
  local name=$1
  local initial=$2
  local update=$3
  python3 "${GRI_ROOT}/scripts/convert_spine_slices_to_pma_graph.py" \
    --initial "${SIM_ROOT}/${initial}" \
    --update "${SIM_ROOT}/${update}" \
    --output "${OUT_DIR}/${name}.graph" \
    --metadata "${OUT_DIR}/${name}.json"
}

convert askubuntu_directed_e540000_insert_u8 \
  tests/data/candidate10_askubuntu_paper_scale/sx_askubuntu_base_e540000.slice \
  tests/data/candidate10_askubuntu_paper_scale/sx_askubuntu_insert_u8.slice

convert askubuntu_reciprocal_e540000_insert_u8 \
  tests/data/askubuntu_reciprocal_large/askubuntu_reciprocal_gate_e540000.slice \
  tests/data/askubuntu_reciprocal_large/askubuntu_reciprocal_gate_e540000_insert_bridge_u8.slice

convert askubuntu_reciprocal_e903774_insert_u8 \
  tests/data/askubuntu_reciprocal_full/askubuntu_reciprocal_full_e903774.slice \
  tests/data/askubuntu_reciprocal_full/askubuntu_reciprocal_full_e903774_insert_bridge_u8.slice

(
  cd "${OUT_DIR}"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum
) >"${OUT_DIR}/SHA256SUMS"

echo "BRIDGE_FPGA_WORKLOADS_PASS out_dir=${OUT_DIR}"
