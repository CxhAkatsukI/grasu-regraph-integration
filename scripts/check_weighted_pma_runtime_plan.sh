#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR="${GRI_ROOT}/.tmp_build/weighted_pma_runtime_plan_$(date +%Y%m%d_%H%M%S)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--out-dir PATH]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
mkdir -p "${OUT_DIR}"

SRC="${GRI_ROOT}/tests/weighted_pma_runtime_plan_test.cpp"
EXE="${OUT_DIR}/weighted_pma_runtime_plan_test"
LOG="${OUT_DIR}/test.log"

if ! g++ -std=c++17 -Wall -Wextra -Werror \
  -I"${GRI_ROOT}/include" "${SRC}" -o "${EXE}" >"${LOG}" 2>&1; then
  cat "${LOG}" >&2
  exit 1
fi
if ! "${EXE}" >>"${LOG}" 2>&1; then
  cat "${LOG}" >&2
  exit 1
fi

{
  echo "timestamp=$(date -Is)"
  echo "SRC=${SRC}"
  echo "EXE=${EXE}"
} >"${OUT_DIR}/manifest.env"
sha256sum \
  "${GRI_ROOT}/include/weighted_pma_graph.hpp" \
  "${GRI_ROOT}/include/weighted_pma_runtime_plan.hpp" \
  "${SRC}" "${EXE}" "${LOG}" >"${OUT_DIR}/SHA256SUMS"

echo "Weighted PMA runtime plan test passed:"
echo "  ${OUT_DIR}"
