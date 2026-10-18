#!/usr/bin/env bash

# The bank-stream policy changes the row-pointer AXI width to 512 bits.
select_pma_adapter() {
  local policy="$1" pipeline_mode="$2"
  PMA_ADAPTER_FLAGS=()
  PMA_ADAPTER_ROW_LINE_READ=0
  case "${policy}" in
    legacy) return 0 ;;
    bank-stream) ;;
    *) echo "Invalid --adapter-policy: ${policy}" >&2; return 2 ;;
  esac
  if [[ "${pipeline_mode}" != sharded-k4 ]]; then
    echo "bank-stream requires --pipeline-mode sharded-k4" >&2
    return 2
  fi
  PMA_ADAPTER_ROW_LINE_READ=1
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
