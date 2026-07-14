# GraSU Device-Graph Export to ReGraph

Date: 2026-07-14 Asia/Shanghai

## What Changed

The previous GraSU+ReGraph sweep ran GraSU's update/check, then converted the
pre-generated expected result file into ReGraph input. That proves the two
algorithms independently, but it does not prove ReGraph consumed GraSU's
actual post-update graph and it uses future final-graph knowledge.

GraSU commit `72c3dae` adds an optional fourth host argument:

```text
GraSU_host_u55c <xclbin> <graph> <result> [export_weighted_edges]
```

After the host reads all four PMA HBM images back and calls `merge_data`, it
now converts internal IDs to external IDs, sorts/deduplicates the actual device
records, and writes `src dst 1`. It also supports `XCL_DEVICE_INDEX` without
mixing the selected context with device 0's program list.

`scripts/run_grasu_regraph_sssp_sweep.sh --device-graph-export` now:

1. passes the per-case export path to GraSU;
2. converts the expected result to a separate verification-only file;
3. requires byte-for-byte `cmp` between actual export and expected edges;
4. records both hashes;
5. feeds only the actual export to ReGraph.

The old expected-result handoff remains available when the flag is absent.

When `--device-graph-export` is used without an explicit `--grasu-host`, the
runner now prefers a sibling host named `GraSU_host_u55c_export` when it exists.
This avoids accidentally using an older host binary that accepts only the
three-argument non-export interface.

## Host Build

```bash
cd /home/chuxiao/GraSU
source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
source /opt/xilinx/xrt/setup.sh
g++ -std=c++17 -O2 \
  -DGRASU_USE_HBM_BANKS -DGRASU_MAX_CACHE_SEGMENT=131072 \
  -I/opt/xilinx/xrt/include \
  -I/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include \
  -I/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include/etc \
  -IGraSU/GraSU/src GraSU/GraSU/src/host.cpp \
  -L/opt/xilinx/xrt/lib -lxilinxopencl -lpthread \
  -o .tmp_build/u55c_hbm_hw/GraSU_host_u55c_export
```

## Combined Real-Hardware Smoke

```bash
cd /home/chuxiao/grasu-regraph-integration
GRASU_HOST=/home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c_export \
REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset smoke \
  --combined-xclbin \
    /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin \
  --device-graph-export \
  --out-root results/grasu_regraph_device_export_smoke_hw_20260714
```

Both hosts load the same combined xclbin. They still run sequentially and the
graph handoff is D2H, host serialization, then H2D, so this is a verified
`host-conversion-baseline`, not a pure kernel-to-kernel path.

## Results

| Case | Status | Actual exported edges | GraSU ms | ReGraph E2E ms | ReGraph mismatch |
| --- | --- | ---: | ---: | ---: | ---: |
| tiny_chain_v16 | PASS | 15 | 1.503532 | 4.571430 | 0 |
| tiny_star_v16_u12 | PASS | 28 | 1.510852 | 0.953467 | 0 |
| tiny_hotdst_v64_u32 | PASS | 95 | 1.497222 | 4.687460 | 0 |

Actual/expected export hashes match within every case:

```text
tiny_chain_v16:
  711894d41cd1e0e07540996af0b323bfdc5702cf520ddb09de940a4eef226a1c
tiny_star_v16_u12:
  4faccf735da914557d790f1699de1cd11c490a5726e92e115d0a46ae6c2f5d96
tiny_hotdst_v64_u32:
  70e040c2e5f8da3ad51410094f8c1d99e0fadeea36c40bd147373dc0529f28a7
```

Core artifacts:

```text
GraSU export host:
  sha256 95edb2a0b0028cd17ae340c56f3a642c86a7d6d4fd03e19e3ab1ac505c89b9e1
ReGraph SSSP host:
  sha256 9ceb054575e63aa9c6b045875eae2de205e14788a1f211c9116b411df4fed8c8
combined xclbin:
  sha256 d4296714739acea95a8f6a2f66e113849f089fe8e026fd72e7ee40c9e56f05b0
summary.tsv:
  sha256 ce6421747afb78f934cd0fc5d39eefac22e30bc64d41768b1cf9d9b4dd47ce87
```

## Frozen Smoke Baseline With Spread

After the smoke manifest was frozen in the integration repository, the same
host-conversion baseline was rerun on all four tracked smoke cases, including
`tiny_spread_v16_u8`.

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset smoke \
  --workload-root workloads/sssp_benchmark_smoke \
  --out-root results/grasu_regraph_smoke_device_export_combined_hw_stage1 \
  --skip-generate \
  --device-graph-export \
  --grasu-host repos/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c_export \
  --regraph-host /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
  --combined-xclbin .tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin \
  --timeout 600
```

Artifacts:

```text
95edb2a0b0028cd17ae340c56f3a642c86a7d6d4fd03e19e3ab1ac505c89b9e1  repos/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c_export
d4296714739acea95a8f6a2f66e113849f089fe8e026fd72e7ee40c9e56f05b0  .tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin
9ceb054575e63aa9c6b045875eae2de205e14788a1f211c9116b411df4fed8c8  /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp
719a48da5eacc18957903212d788106e923df08f596eb9635a8b7df533315945  results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv
```

Result:

| Case | Status | Actual exported edges | GraSU ms | ReGraph E2E ms | Zero-cost handoff ms | ReGraph mismatch |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| tiny_chain_v16 | PASS | 15 | 1.487159 | 4.640770 | 6.127929 | 0 |
| tiny_star_v16_u12 | PASS | 28 | 1.664904 | 0.861722 | 2.526626 | 0 |
| tiny_spread_v16_u8 | PASS | 24 | 1.505099 | 4.238550 | 5.743649 | 0 |
| tiny_hotdst_v64_u32 | PASS | 95 | 1.648783 | 4.553440 | 6.202223 | 0 |

Actual/expected export hashes match within every case:

```text
tiny_chain_v16:
  711894d41cd1e0e07540996af0b323bfdc5702cf520ddb09de940a4eef226a1c
tiny_star_v16_u12:
  4faccf735da914557d790f1699de1cd11c490a5726e92e115d0a46ae6c2f5d96
tiny_spread_v16_u8:
  21c74c7c65edb2c5ee0c7317190f3a5c6a972d0616407a517ab0bbeba58c0a8f
tiny_hotdst_v64_u32:
  70e040c2e5f8da3ad51410094f8c1d99e0fadeea36c40bd147373dc0529f28a7
```

## Remaining Limits

- GraSU's reported milliseconds cover update kernels, not PMA D2H, merge,
  serialization, and ReGraph H2D. The full baseline must instrument those
  phases before an end-to-end comparison.
- The old smoke workload uses configured ReGraph superstep counts. It is
  correctness evidence for those counts, not yet the frozen shared
  until-convergence BFS matrix.
- The handoff is now actual and auditable, but it is still host conversion.
  A pure path requires a device PMA-to-ReGraph adapter/layout or a ReGraph
  reader that consumes GraSU PMA directly.
