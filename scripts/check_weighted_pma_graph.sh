#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

OUT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--out-dir PATH]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="${GRI_ROOT}/.tmp_build/weighted_pma_graph_$(date +%Y%m%d_%H%M%S)"
elif [[ "${OUT_DIR}" != /* ]]; then
  OUT_DIR="${PWD}/${OUT_DIR}"
fi
mkdir -p "${OUT_DIR}"

SRC="${GRI_ROOT}/tests/weighted_pma_graph_test.cpp"
HEADER="${GRI_ROOT}/include/weighted_pma_graph.hpp"
EXE="${OUT_DIR}/weighted_pma_graph_test"
LOG="${OUT_DIR}/test.log"

if ! g++ -std=c++17 -Wall -Wextra -Werror \
  -I"${GRI_ROOT}/include" "${SRC}" -o "${EXE}" > "${LOG}" 2>&1; then
  cat "${LOG}" >&2
  exit 1
fi
if ! "${EXE}" >> "${LOG}" 2>&1; then
  cat "${LOG}" >&2
  exit 1
fi

{
  echo "timestamp=$(date -Is)"
  echo "HEADER=${HEADER}"
  echo "SRC=${SRC}"
  echo "EXE=${EXE}"
} > "${OUT_DIR}/manifest.env"
{
  sha256sum "${HEADER}"
  sha256sum "${SRC}"
  sha256sum "${EXE}"
  sha256sum "${LOG}"
} > "${OUT_DIR}/SHA256SUMS"

echo "Weighted PMA graph preprocessing test passed:"
echo "  ${OUT_DIR}"
