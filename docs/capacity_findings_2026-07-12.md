# Capacity and Large-Graph Findings

Date: 2026-07-12

## Scope

This note records the first capacity-oriented runs after the combined
GraSU+ReGraph real `hw` xclbin was validated. The goal was to separate three
questions:

- whether the combined xclbin can execute large ReGraph kernels;
- whether the previous large-graph crashes require a hardware rebuild;
- where Spine vs GraSU+ReGraph starts to show architecture-specific weak cases.

## Fixed Inputs

Combined xclbin:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin
sha256 d4296714739acea95a8f6a2f66e113849f089fe8e026fd72e7ee40c9e56f05b0
```

ReGraph host with `REGRAPH_SKIP_VERIFY` support and the verification-buffer
size fix:

```text
/home/chuxiao/ReGraph/host_graph_fpga_sssp
sha256 fae2422595fed58b0e019663e3875214f5b991a273e4cd57b3bdfc8a79747a68
```

The host-only rebuild command was:

```bash
cd /home/chuxiao/ReGraph
set +e +u
source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
source /opt/xilinx/xrt/setup.sh
set -u
make APP=sssp TARGETS=hw DEVICES=xilinx_u55c_gen3x16_xdma_3_202210_1 exe
```

This rebuilds only the x86 host executable. It does not relink or recompile the
hardware xclbin.

Patch recorded for review:

```text
/home/chuxiao/grasu-regraph-integration/patches/regraph_host_skip_verify_perf_only_20260712.diff
/home/chuxiao/grasu-regraph-integration/patches/regraph_verify_buffer_size_fix_20260712.diff
```

## ReGraph Large Runs With Full Verification

Command pattern:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +u
source /opt/xilinx/xrt/setup.sh
set -u

REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset capacity \
  --combined-xclbin /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin \
  --allow-pass-on-nonzero-exit \
  --timeout 900
```

Evidence roots:

```text
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_sweep_20260712_202537
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_sweep_20260712_202626
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_sweep_20260712_202642
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_sweep_20260712_202719
```

Observed results:

| case | status | vertices | final edges | supersteps | GraSU ms | ReGraph ms | note |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| large_star_v1048576_u65536 | PASS | 1048576 | 1114112 | 2 | 76.326566 | 8.33143 | Correct result, but host later exited 134 with `double free or corruption`. |
| large_spread_v262144_u65536 | FAIL | 262144 | 327680 | 32 | 12.173688 | 41.4327 | Segfault near ReGraph result readback/verification. |
| large_hotdst_v262144_u65536 | FAIL | 262144 | 327679 | 64 | 12.145717 | 88.1561 | Segfault near ReGraph result readback/verification. |
| large_chain_v4096 | PASS | 4096 | 4095 | 4096 | 1.615394 | 1118.17 | Correct but slow because it needs many supersteps. |
| large_spread_v262144_u65536, numD=0 | FAIL | 262144 | 327680 | 32 | 12.146057 | 48.9636 | Still segfaulted, so the crash is not specific to `numD=1`. |

Important code observations:

```text
host/verification/verify.cpp
  Prints "Read accumulated results from device for verification..."
  then migrates result_prop_dev back to host.

host/preprocess/partition_schedule.cpp
  May resize vertex_property, dst_tmp_prop_host, and outdegree_host when the
  accelerator partition layout needs more vertices than NUM_VERTEX_ALIGNED.

host/preprocess/partition_schedule.cpp
  Creates multiple CL_MEM_USE_HOST_PTR buffers from the same backing vectors
  for per-kernel source/destination property arrays.
```

Interpretation:

```text
The combined hardware can run large kernels, but the full-verification path is
fragile on some larger graphs. The failure shape points to host-side memory,
buffer migration, verification sizing, or teardown behavior. It does not by
itself justify rebuilding the hardware.
```

## ReGraph Perf-Only Runs

To separate kernel execution from host readback/verification, the ReGraph host
now accepts:

```text
REGRAPH_SKIP_VERIFY=1
```

The sweep script exposes this as:

```text
--regraph-skip-verify
```

The summarizer marks such cases as:

```text
PERF_ONLY
```

not `PASS`, because no hardware result array is read back and checked.

Smoke command:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +u
source /opt/xilinx/xrt/setup.sh
set -u

OUT_ROOT=/home/chuxiao/grasu-regraph-integration/results/regraph_skip_verify_smoke_hw_20260712_204651
REGRAPH_HOST=/home/chuxiao/ReGraph/host_graph_fpga_sssp \
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset smoke \
  --skip-grasu \
  --combined-xclbin /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin \
  --regraph-skip-verify \
  --timeout 300 \
  --out-root "${OUT_ROOT}"
```

Smoke evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/regraph_skip_verify_smoke_hw_20260712_204651/summary.tsv
```

All three smoke cases completed as `PERF_ONLY`.

Capacity command:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +u
source /opt/xilinx/xrt/setup.sh
set -u

OUT_ROOT=/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_capacity_perf_only_hw_20260712_204718
REGRAPH_HOST=/home/chuxiao/ReGraph/host_graph_fpga_sssp \
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset capacity \
  --combined-xclbin /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin \
  --regraph-skip-verify \
  --allow-pass-on-nonzero-exit \
  --timeout 900 \
  --out-root "${OUT_ROOT}"
```

Capacity perf-only evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_capacity_perf_only_hw_20260712_204718/summary.tsv
```

Results:

| case | status | vertices | final edges | supersteps | GraSU ms | ReGraph ms | ReGraph MTEPS |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| large_star_v1048576_u65536 | PERF_ONLY | 1048576 | 1114112 | 2 | 76.292273 | 8.13583 | 273.878 |
| large_spread_v262144_u65536 | PERF_ONLY | 262144 | 327680 | 32 | 12.170097 | 43.3623 | 241.818 |
| large_hotdst_v262144_u65536 | PERF_ONLY | 262144 | 327679 | 64 | 12.157216 | 84.0982 | 249.369 |
| large_chain_v4096 | PERF_ONLY | 4096 | 4095 | 4096 | 1.488780 | 1016.92 | 16.4941 |

Key log lines:

```text
Device[0]: program successful!
[INFO] ... e2e: <time> ms; Throught: <rate> MTEPS :
[INFO] Skipping hardware result verification because REGRAPH_SKIP_VERIFY is set.
```

Conclusion:

```text
The same large spread and hot-destination inputs that segfault with full
verification complete when result readback/verification is skipped. This is
strong evidence that the current blocker is ReGraph host software, not the
combined hardware bitstream.
```

## Verification Buffer-Size Fix

Root cause found:

```text
partition_schedule.cpp may resize partition_container.vertex_property,
dst_tmp_prop_host, and outdegree_host above NUM_VERTEX_ALIGNED when the
accelerator partition layout needs additional destination space.

verify.cpp still allocated dst_tmp_prop_verfication,
dst_tmp_prop_verfication_e2e, and software_next at NUM_VERTEX_ALIGNED.

At the end of software verification, it copied the larger software_prop vector
into the smaller dst_tmp_prop_verfication vector. This is a host memory
overwrite and explains the previous large_star double-free and spread/hotdst
segfaults near result readback.
```

Fix:

```text
Use verification_vertices =
  max(NUM_VERTEX_ALIGNED, partition_container.vertex_property.size())

Allocate the software verification arrays with verification_vertices.
```

Host-only rebuild:

```bash
cd /home/chuxiao/ReGraph
set +e +u
source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
source /opt/xilinx/xrt/setup.sh
set -u
make APP=sssp TARGETS=hw DEVICES=xilinx_u55c_gen3x16_xdma_3_202210_1 exe
```

Re-run command with full verification:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +u
source /opt/xilinx/xrt/setup.sh
set -u

OUT_ROOT=/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_capacity_verifyfix_hw_20260712_205303
REGRAPH_HOST=/home/chuxiao/ReGraph/host_graph_fpga_sssp \
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset capacity \
  --combined-xclbin /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin \
  --allow-pass-on-nonzero-exit \
  --timeout 900 \
  --out-root "${OUT_ROOT}"
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_capacity_verifyfix_hw_20260712_205303/summary.tsv
```

Full-verification results after the fix:

| case | status | vertices | final edges | supersteps | GraSU ms | ReGraph ms | processed edges | mismatch count |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| large_star_v1048576_u65536 | PASS | 1048576 | 1114112 | 2 | 76.240819 | 8.17581 | 1115336 | 0 |
| large_spread_v262144_u65536 | PASS | 262144 | 327680 | 32 | 12.205769 | 41.1394 | 327912 | 0 |
| large_hotdst_v262144_u65536 | PASS | 262144 | 327679 | 64 | 12.144246 | 85.551 | 327752 | 0 |
| large_chain_v4096 | PASS | 4096 | 4095 | 4096 | 1.667694 | 1091.32 | 4096 | 0 |

Conclusion:

```text
The large-spread and large-hotdst failures were fixed by a host-only
verification buffer sizing change. No hardware rebuild was required.
```

## Spine Capacity Probe

The Spine `--edge-file` host was extended to split input files into batches of
at most `HOST_PARTITIONED_RATIO2_MAX_SORT_N` edges. This allows large edge
files from the GraSU+ReGraph capacity preset to be tested without changing the
hardware.

Local single-CU Spine host:

```text
/home/chuxiao/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke
sha256 83d7654b289d4057e47843c3385c057bdd42863694ab8d78e125201ccd219fcb
```

Split-CU scratch host with chunked `--edge-file`:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge
sha256 df0aa0dca3eddb09aa58805fe7bb1c65e4c1a7484ab8ae6ca230c11bbff90bdd
```

Run command:

```bash
cd /home/chuxiao/grasu-regraph-integration
SPINE_HOST=/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge \
SPINE_XCLBIN=/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
SPINE_PARTITIONED_SPLIT_VALUE=1 \
OUT_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_split_edge_file_capacity_hw_20260712_202812 \
./scripts/run_spine_edge_file_sweep.sh \
  --chain-root /home/chuxiao/grasu-regraph-integration/results/capacity_edges_for_spine_split_copy_20260712_202812 \
  --timeout 1800
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_split_edge_file_capacity_hw_20260712_202812/summary.tsv
```

Observed results:

| case | status | wall seconds | input edges observed | maint ms | conv ms | note |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| large_chain_v4096 | PASS | 11.035 | 4095 | 8.16793 | 54.3404 | End-to-end kernel path completed. |
| large_hotdst_v262144_u65536 | FAIL | 647.702 | 131072 | 250.563 | | Stopped after batch 2 maintenance kept reporting RUNNING past 630 s. |

Hot-destination log evidence:

```text
PARTITIONED_CSR_E2E_BATCH ... batch=1 input_edges=131072 ... maint_ms=250.563
[part-e2e] maintenance status=RUNNING elapsed_s=630
exit_code 143
```

Interpretation:

```text
Spine did not crash here. The large hot-destination input entered a very slow
maintenance path after the first full batch. This is a separate architecture or
scheduling optimization target from the ReGraph host verification crash.
```

## Current Conclusions

```text
1. The former ReGraph large-spread / large-hotdst crash was a host verification
   memory overwrite, fixed by sizing verification arrays from the actual
   partition_container property buffer.
2. No combined GraSU+ReGraph hardware rebuild was needed for this failure.
3. Keep reporting skip-verify large results as PERF_ONLY only. They are useful
   for timing and capacity, not correctness.
4. GraSU+ReGraph large low-diameter cases show strong ReGraph kernel throughput
   with full verification passing, while the high-diameter chain remains slow
   because it requires thousands of supersteps.
5. Spine's large hot-destination path is a separate slow-maintenance issue:
   the board stays responsive, but maintenance does not finish in a practical
   time for the tested batch.
```

## Next Work

```text
1. Fold the ReGraph verification buffer-size patch into the source branch used
   for future builds, not only the local hard-linked working copy.
2. Add a smaller binary search around Spine hot-destination fan-in and batch
   size to find where the maintenance slow path begins.
```
