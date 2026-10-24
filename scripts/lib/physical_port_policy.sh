#!/usr/bin/env bash

# Keep the simulator's independent ingress profile available. Physical sharing
# changes arbitration and must be selected and measured explicitly.
select_physical_ports() {
  PHYSICAL_PORT_FLAGS=()
  PHYSICAL_ADAPTER_BUNDLES=3
  case "$1" in
    independent) return 0 ;;
    shared-ingress) ;;
    *) echo "Invalid --physical-port-policy: $1" >&2; return 2 ;;
  esac
  if [[ "$2" != sharded-k4 || "$3" != complete-search-cache ||
        "$4" != prefetch-compact || "$5" == sw_emu ]]; then
    echo "shared-ingress requires sharded-k4, complete-search-cache, prefetch-compact and hw/hw_emu" >&2
    return 2
  fi
  PHYSICAL_PORT_FLAGS=(-DGRI_HMSS_SHARED_INGRESS=1)
  PHYSICAL_ADAPTER_BUNDLES=2
}
