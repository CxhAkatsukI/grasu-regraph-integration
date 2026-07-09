#!/usr/bin/env bash
set -euo pipefail

export GRI_ROOT="${GRI_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export GRASU_ROOT="${GRASU_ROOT:-${GRI_ROOT}/repos/GraSU}"
export REGRAPH_ROOT="${REGRAPH_ROOT:-${GRI_ROOT}/repos/ReGraph}"
export SPINE_ROOT="${SPINE_ROOT:-/home/chuxiao/spine-dynamic-graph}"

export XILINX_XRT="${XILINX_XRT:-/opt/xilinx/xrt}"
if [[ -d "${XILINX_XRT}/lib" ]]; then
  export LD_LIBRARY_PATH="${XILINX_XRT}/lib:${LD_LIBRARY_PATH:-}"
fi

