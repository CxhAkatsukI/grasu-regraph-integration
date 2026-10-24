#!/usr/bin/env bash

# Both opt-in policies change the row-pointer AXI width to 512 bits.
select_pma_adapter() {
  local policy="$1" pipeline_mode="$2"
  PMA_ADAPTER_FLAGS=()
  REGRAPH_PROFILE_FLAGS=()
  PMA_ADAPTER_SOURCE="${GRI_ROOT}/kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp"
  PMA_ADAPTER_ROW_LINE_READ=0
  case "${policy}" in
    legacy) return 0 ;;
    bank-stream|prefetch-compact) ;;
    *) echo "Invalid --adapter-policy: ${policy}" >&2; return 2 ;;
  esac
  if [[ "${pipeline_mode}" != sharded-k4 ]]; then
    echo "${policy} requires --pipeline-mode sharded-k4" >&2
    return 2
  fi
  PMA_ADAPTER_ROW_LINE_READ=1
  if [[ "${policy}" == prefetch-compact ]]; then
    PMA_ADAPTER_SOURCE="${GRI_ROOT}/kernels/pma_prefetch_compact/top.cpp"
    REGRAPH_PROFILE_FLAGS=(-DGRASU_REGRAPH_PREFETCH_COMPACT=1)
    return 0
  fi
  PMA_ADAPTER_FLAGS=(
    -DGRASU_REGRAPH_ROW_PREFETCH=1
    -DGRASU_REGRAPH_STOP_AFTER_LAST=1
    -DGRASU_REGRAPH_SKIP_EMPTY_SEGMENT=1
    -DGRASU_REGRAPH_ROW_LINE_READ=1
    -DGRASU_REGRAPH_CROSS_ROW_PIPELINE=1
    -DGRASU_REGRAPH_DIRECTORY_TILE_ROWS=1024
    -DGRASU_REGRAPH_PACKET_PIPELINE=1
    -DGRASU_REGRAPH_BANK_STREAM=1
    -DGRASU_REGRAPH_BANK_FIFO_LINES=256
  )
}

emit_profile_vitis_settings() {
  if [[ "${ADAPTER_POLICY}" == prefetch-compact ]]; then
    echo 'source "${GRI_VITIS_SETTINGS:-/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh}"'
  else
    printf 'source %q\n' "/data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh"
  fi
}
