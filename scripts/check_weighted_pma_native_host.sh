#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${OUT_DIR:-${GRI_ROOT}/.tmp_build/weighted_pma_native_host_check_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "${OUT_DIR}"

"${SCRIPT_DIR}/build_weighted_pma_native_host.sh" --out-dir "${OUT_DIR}"
HOST="${OUT_DIR}/weighted_pma_native_host"

TINY_OUTPUT="${OUT_DIR}/tiny.out"
"${HOST}" --prepare-only \
  "${GRI_ROOT}/workloads/weighted_pma_native_tiny/weighted_pma_native_tiny.graph" \
  "${OUT_DIR}/tiny.result" 0 8 | tee "${TINY_OUTPUT}"
rg -q 'WEIGHTED_PMA_NATIVE_PREP status=PASS .*logical_updates=5 physical_updates=8 final_edges=5 .*reachable_vertices=5 max_distance=14 .*conversion_cost=absent' \
  "${TINY_OUTPUT}"

if "${HOST}" --prepare-only \
     "${GRI_ROOT}/workloads/weighted_pma_native_tiny/weighted_pma_native_tiny.graph" \
     "${OUT_DIR}/nonconverged.result" 0 1 >"${OUT_DIR}/nonconverged.out" 2>&1; then
  echo "Expected insufficient max_supersteps to fail convergence" >&2
  exit 1
fi
rg -q 'WEIGHTED_PMA_NATIVE_PREP status=FAIL .*oracle_converged=0' \
  "${OUT_DIR}/nonconverged.out"

printf '8 0 0\n' >"${OUT_DIR}/empty.graph"
EMPTY_OUTPUT="${OUT_DIR}/empty.out"
"${HOST}" --prepare-only "${OUT_DIR}/empty.graph" \
  "${OUT_DIR}/empty.result" 0 1 | tee "${EMPTY_OUTPUT}"
rg -q 'WEIGHTED_PMA_NATIVE_PREP status=PASS .*pma_slots=16 .*reachable_vertices=1 max_distance=0' \
  "${EMPTY_OUTPUT}"

printf '8 1 1\n0 1 3\n0 1 4 0\n' >"${OUT_DIR}/bad_delete.graph"
if "${HOST}" --prepare-only "${OUT_DIR}/bad_delete.graph" \
     "${OUT_DIR}/bad_delete.result" >"${OUT_DIR}/bad_delete.out" 2>&1; then
  echo "Expected mismatched weighted delete to fail" >&2
  exit 1
fi
rg -q 'weighted delete target or weight does not match oracle state' \
  "${OUT_DIR}/bad_delete.out"

printf '8 1 0\n0 1 0\n' >"${OUT_DIR}/zero_weight.graph"
if "${HOST}" --prepare-only "${OUT_DIR}/zero_weight.graph" \
     "${OUT_DIR}/zero_weight.result" >"${OUT_DIR}/zero_weight.out" 2>&1; then
  echo "Expected zero edge weight to fail" >&2
  exit 1
fi
rg -q 'weighted static edge exceeds weight12 ABI or is zero' \
  "${OUT_DIR}/zero_weight.out"

printf '8 1 1\n0 1 3\n0 1 3 1\n' >"${OUT_DIR}/duplicate_insert.graph"
if "${HOST}" --prepare-only "${OUT_DIR}/duplicate_insert.graph" \
     "${OUT_DIR}/duplicate_insert.result" >"${OUT_DIR}/duplicate_insert.out" 2>&1; then
  echo "Expected duplicate weighted insert to fail" >&2
  exit 1
fi
rg -q 'weighted insert target already exists with same weight' \
  "${OUT_DIR}/duplicate_insert.out"

if "${HOST}" --prepare-only "${OUT_DIR}/empty.graph" \
     "${OUT_DIR}/bad_arg.result" 4294967296 1 >"${OUT_DIR}/bad_arg.out" 2>&1; then
  echo "Expected overflowing source argument to fail" >&2
  exit 1
fi
rg -q 'invalid source_external: 4294967296' "${OUT_DIR}/bad_arg.out"

cat >"${OUT_DIR}/check_manifest.env" <<MANIFEST
STATUS=PASS
CLAIM_CLASS=host_preprocessing_and_cpu_oracle_only
HARDWARE_EXECUTED=0
PIPELINE_MODE=weighted-axis
CONVERSION_COST=absent
NORMAL_LOGICAL_UPDATES=5
NORMAL_PHYSICAL_UPDATES=8
NORMAL_MAX_DISTANCE=14
EMPTY_PROTOCOL_SLOTS=16
ERROR_PATHS=nonconverged,bad_delete,zero_weight,duplicate_insert,overflowing_cli_arg
MANIFEST

printf 'Weighted PMA native host checks passed:\n  %s\n' "${OUT_DIR}"
