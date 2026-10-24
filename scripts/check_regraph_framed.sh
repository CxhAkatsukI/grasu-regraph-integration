#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$root/scripts/env.sh"
if [[ $# != 2 || $1 != --out-dir ]]; then
  echo "usage: $0 --out-dir FRESH_DIRECTORY" >&2
  exit 2
fi
mkdir "$2"
out=$(cd "$2" && pwd)
include=${HLS_INCLUDE:-/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include}
for algorithm in sssp cc pagerank; do
  flags=(-DTEST_PAGERANK=0 -DHAVE_EDGE_PROP=0)
  udf="$root/include/regraph_$algorithm"
  case "$algorithm" in
    sssp) udf="$REGRAPH_ROOT/acc_udfs/sssp"; flags=(-DTEST_PAGERANK=0 -DHAVE_EDGE_PROP=1) ;;
    pagerank) flags=(-DTEST_PAGERANK=1 -DHAVE_EDGE_PROP=0) ;;
  esac
  for connected in 0 1; do
  g++ -std=c++17 -O1 -w -pthread "${flags[@]}" \
    -DTEST_COMPACT_INPUT="$connected" \
    -DGRASU_REGRAPH_PREFETCH_COMPACT=1 -DHAVE_UNSIGNED_PROP=1 \
    -DHAVE_APPLY_OUTDEG=0 -DHAVE_VERTEX_PROP=1 -DPARTITION_SIZE=65536 \
    -DLITTLE_KERNEL_DST_BUFFER_SIZE=65536 -DBIG_KERNEL_DST_BUFFER_SIZE=524288 \
    -DSRC_BUFFER_SIZE=4096 -DLOG2_SRC_BUFFER_SIZE=12 -DVERTEX_REORDER_ENABLE=1 \
    -DENABLE_COMPRESSED_EDGE_INPUT=0 -DBIG_KERNEL_NUM=0 -DLITTLE_KERNEL_NUM=1 \
    -I"$include" -I"$include/etc" -I"$udf" -I"$REGRAPH_ROOT" \
    -I"$REGRAPH_ROOT/acc_template" -I"$REGRAPH_ROOT/acc_template/common" \
    -I"$REGRAPH_ROOT/acc_udfs" -I"$REGRAPH_ROOT/acc_template/kernel_little_gs" \
    "$root/tests/regraph_framed_tb.cpp" -o "$out/$algorithm-connected-$connected" \
    > "$out/$algorithm-connected-$connected.build.log" 2>&1
  timeout 180 "$out/$algorithm-connected-$connected" > "$out/$algorithm-connected-$connected.run.log" 2>&1
  tail -n 2 "$out/$algorithm-connected-$connected.run.log"
  done
  if [[ $algorithm != pagerank ]]; then
    g++ -std=c++17 -O1 -w -pthread "${flags[@]}" \
      -DGRASU_REGRAPH_PREFETCH_COMPACT=1 -DHAVE_UNSIGNED_PROP=1 \
      -DHAVE_APPLY_OUTDEG=0 -DHAVE_VERTEX_PROP=1 -DPARTITION_SIZE=65536 \
      -DLITTLE_KERNEL_DST_BUFFER_SIZE=65536 -DBIG_KERNEL_DST_BUFFER_SIZE=524288 \
      -DBIG_KERNEL_NUM=0 -DLITTLE_KERNEL_NUM=1 \
      -I"$include" -I"$include/etc" -I"$udf" \
      -I"$REGRAPH_ROOT/acc_template/common" -I"$REGRAPH_ROOT/acc_template/kernel_apply" \
      "$root/tests/regraph_prefetch_apply_tb.cpp" -o "$out/$algorithm-apply" \
      > "$out/$algorithm-apply.build.log" 2>&1
    timeout 180 "$out/$algorithm-apply" > "$out/$algorithm-apply.run.log" 2>&1
    tail -n 2 "$out/$algorithm-apply.run.log"
  fi
done
