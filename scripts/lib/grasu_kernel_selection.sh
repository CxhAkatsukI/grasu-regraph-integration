#!/usr/bin/env bash

# Sets source paths and cache flags without changing the selected pipeline ABI.
select_grasu_kernels() {
  local implementation="$1" target="$2" pipeline_mode="$3" capacity="$4"
  local kernel_root="${GRASU_ROOT}/GraSU/GraSU_kernels/src"
  GRASU_SEARCH_SOURCE="${kernel_root}/kernel_bin_search.cpp"
  GRASU_CACHE_SOURCE="${kernel_root}/kernel_process_cache.cpp"
  GRASU_CACHE_IMPLEMENTATION_FLAGS=(-DGRASU_PURE_PIPELINE_DIRECT_CACHE)
  GRASU_IMPLEMENTATION_HEADERS=()
  case "${implementation}" in
    legacy-direct-cache) return 0 ;;
    complete-search-cache|complete-search-cache-bounded) ;;
    *) echo "Invalid --grasu-implementation: ${implementation}" >&2; return 2 ;;
  esac
  if [[ "${target}" == sw_emu ]]; then
    echo "complete-search-cache requires hw or hw_emu; stock sw_emu lacks the finite host harness" >&2
    return 2
  fi
  if [[ "${pipeline_mode}" != sharded-k4 || "${capacity}" != 131072 ]]; then
    echo "complete-search-cache requires sharded-k4 and the full 131072-word cache" >&2
    return 2
  fi
  local root="${GRI_ROOT}/kernels/grasu_complete"
  GRASU_SEARCH_SOURCE="${root}/search_binding/top.cpp"
  GRASU_CACHE_SOURCE="${root}/process_cache.cpp"
  GRASU_CACHE_IMPLEMENTATION_FLAGS=(-DCACHE_BANK_REGISTERED)
  if [[ "${implementation}" == complete-search-cache-bounded ]]; then
    GRASU_CACHE_IMPLEMENTATION_FLAGS+=(-DGRASU_CACHE_VALID_EXTENT)
  fi
  local header
  for header in search_binding/top.hpp search_pipeline/types.hpp \
      search_pipeline/search_worker.hpp search_pipeline/workers.hpp \
      search_pipeline/transport.hpp search_pipeline/network.hpp \
      cache_bank.hpp cache_lane.hpp cache_pipeline.hpp; do
    GRASU_IMPLEMENTATION_HEADERS+=("${root}/${header}")
  done
  for header in "${GRASU_SEARCH_SOURCE}" "${GRASU_CACHE_SOURCE}" \
      "${kernel_root}/kernel_config.h" "${GRASU_IMPLEMENTATION_HEADERS[@]}"; do
    if [[ ! -f "${header}" ]]; then
      echo "Missing complete-search-cache input: ${header}" >&2
      return 1
    fi
  done
}
