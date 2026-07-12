# Combined GraSU + ReGraph Real HW Validation

Date: 2026-07-12

## Scope

This note records the first complete real-hardware validation of the combined
GraSU + ReGraph weighted-SSSP xclbin. It covers:

- the final `hw` artifact and observed clock behavior;
- resource/CU/HBM/SLR evidence against standalone GraSU and ReGraph builds;
- a real U55C functional smoke test;
- the first review-scenario performance sweep against the existing Spine
  baseline.

## Build Artifact

Combined xclbin:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin
sha256 d4296714739acea95a8f6a2f66e113849f089fe8e026fd72e7ee40c9e56f05b0
size   72 MiB
```

The build command requested 250 MHz:

```bash
cd /home/chuxiao/grasu-regraph-integration
.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/link_command.sh
```

The generated command contains:

```text
v++ --target hw --link --kernel_frequency 250 ...
```

This is a requested experiment frequency, not a functional correctness
requirement. Vitis completed with `exit_status=0`, but it auto-scaled the
kernel clock because timing did not meet the requested 250 MHz:

```text
WARNING: [AUTO-FREQ-SCALING-04]
original frequency equal to 250 MHz
automatically changed to 243.8 MHz
```

Use `243.8 MHz` as the actual clock when interpreting performance numbers from
this xclbin.

## Resource Evidence

Evidence command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/collect_combined_hw_evidence.sh \
  --target hw \
  --combined-build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335 \
  --combined-xclbin /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin \
  --out-root /home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_195442_combined_hw_user_check
```

Evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_195442_combined_hw_user_check
```

Inputs:

```text
GraSU host:
  /home/chuxiao/grasu-regraph-integration/repos/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c
GraSU xclbin:
  /home/chuxiao/grasu-regraph-integration/repos/GraSU/.tmp_build/u55c_hbm_hw/build/GraSU_u55c_hbm.hw.xclbin
ReGraph host:
  /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp
ReGraph xclbin:
  /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
Combined xclbin:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin
```

Review-gate summaries:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_195442_combined_hw_user_check/compare_grasu_hw_vs_combined/summary.md
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_195442_combined_hw_user_check/compare_regraph_hw_vs_combined/summary.md
```

Same-component invariants that passed:

```text
GraSU vs combined:
  hls_top_area same-component changes: 0
  kernel CU count same-kernel changes: 0
  connectivity binding same-endpoint changes: 0

ReGraph vs combined:
  hls_top_area same-component changes: 0
  kernel CU count same-kernel changes: 0
  connectivity binding same-endpoint changes: 0
```

Expected additions:

```text
When comparing standalone GraSU to combined, ReGraph kernels are added:
  bigKernelScatterGather, kernelApply, kernelBigGSMerger, kernelHBMWrapper,
  kernelLittleGSMerger, littleKernelScatterGather

When comparing standalone ReGraph to combined, GraSU kernels are added:
  bin_search, dispatch, process_cache, process_ddr
```

Observed implementation-level deltas:

```text
GraSU vs combined:
  accelerator_util same-component changes: 17

ReGraph vs combined:
  accelerator_util same-component changes: 12
```

Interpretation:

```text
The kernel inventory, CU count, HLS top-area records, and HBM/SLR connectivity
bindings are stable for same components. The post-implementation accelerator
utilization report still shows small LUT/REG deltas for several same-named
components. Treat those as physical implementation differences from linking the
two accelerators together, not as evidence that the HLS modules or CU counts
changed. Keep the delta TSVs with the final experiment package.
```

## Functional Smoke

The real-hw smoke uses the same combined xclbin for both hosts:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +u
source /opt/xilinx/xrt/setup.sh
set -u

XCLBIN=/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin
GRASU_HOST=/home/chuxiao/grasu-regraph-integration/repos/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c
REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp
GRAPH=/home/chuxiao/grasu-regraph-integration/workloads/sssp_benchmark_smoke/tiny_chain_v16/tiny_chain_v16.graph
RESULT=/home/chuxiao/grasu-regraph-integration/workloads/sssp_benchmark_smoke/tiny_chain_v16/tiny_chain_v16.result
CONVERTED=/home/chuxiao/grasu-regraph-integration/results/hw_function_check_20260712_195536_combined/tiny_chain_v16.from_grasu.sssp.edges

(cd repos/GraSU && "$GRASU_HOST" "$XCLBIN" "$GRAPH" "$RESULT")
./scripts/grasu_result_to_regraph.py --input "$RESULT" --output "$CONVERTED" --base 16 --weight 1
(cd repos/ReGraph && REGRAPH_SOURCE=0 "$REGRAPH_HOST" "$XCLBIN" "$CONVERTED" 1 2)
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/hw_function_check_20260712_195536_combined
```

Key result:

```text
exit_code=0
GraSU:
  check result passed
  kernel finish
  kernel time: 1.650496 ms

Conversion:
  converted_edges=15

ReGraph:
  Device[0]: program successful!
  Supersteps: 2
  Processed edges: 16; Graph edges: 15
  e2e: 0.898685 ms
  mismatch_count=0

Wall time:
  GraSU phase:   11.046 s
  ReGraph phase:  1.129 s
  Total:         12.175 s
```

This proves the integrated real `hw` artifact can run both accelerators on a
real U55C with the same xclbin.

## Review Performance Sweep

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +u
source /opt/xilinx/xrt/setup.sh
set -u

./scripts/run_combined_review_compare.sh \
  --target hw \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335 \
  --timeout 600
```

GraSU + ReGraph summary:

```text
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_20260712_195628/summary.tsv
```

Spine comparison:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_vs_grasu_regraph_review_combined_hw_20260712_195628/comparison.md
/home/chuxiao/grasu-regraph-integration/results/spine_vs_grasu_regraph_review_combined_hw_20260712_195628/comparison.tsv
```

GraSU + ReGraph review cases:

| case | status | vertices | final_edges | supersteps | GraSU ms | ReGraph ms | chain ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| small_chain_v64 | PASS | 64 | 63 | 64 | 1.529942 | 15.9093 | 17.4392 |
| small_star_v4096_u1024 | PASS | 4096 | 5120 | 2 | 2.259353 | 0.970757 | 3.23011 |
| small_spread_v4096_u1024 | PASS | 4096 | 5120 | 16 | 1.651135 | 4.3615 | 6.01264 |
| small_hotdst_v4096_u1024 | PASS | 4096 | 5119 | 32 | 1.833711 | 8.04871 | 9.88242 |
| medium_star_v65536_u8192 | PASS | 65536 | 73728 | 2 | 8.870644 | 1.05347 | 9.92411 |
| medium_spread_v65536_u16384 | PASS | 65536 | 81920 | 32 | 4.517045 | 10.7691 | 15.2861 |

Scenario-level comparison against the existing Spine review baseline:

| label | chain case | Spine case | chain ms | Spine kernel ms | chain / Spine |
| --- | --- | --- | ---: | ---: | ---: |
| small_high_diameter | small_chain_v64 | carry_l1 | 17.4392 | 9.98364 | 1.74678 |
| small_hot_source | small_star_v4096_u1024 | star_4096 | 3.23011 | 234.1 | 0.013798 |
| small_spread_fanout | small_spread_v4096_u1024 | fanout_4096_s64 | 6.01264 | 241.932 | 0.0248526 |
| small_hot_destination | small_hotdst_v4096_u1024 | duplicate_heavy_4096 | 9.88242 | 234.19 | 0.0421983 |
| medium_hot_source | medium_star_v65536_u8192 | star_65536 | 9.92411 | 1865.91 | 0.00531865 |
| medium_spread_fanout | medium_spread_v65536_u16384 | fanout_65536_s256 | 15.2861 | 1912.48 | 0.00799284 |

Important caveat:

```text
This comparison is scenario-level, not strict same-input. The current Spine
builtin baseline allocates much larger vertex spaces in several cases, while
the GraSU+ReGraph review workloads use direct generated graphs with the listed
vertex/edge counts. Use the table as directional evidence only. The next
stronger experiment should either run both systems on identical generated
graphs, or explicitly normalize/justify the different graph front ends.
```

Preliminary interpretation:

```text
GraSU+ReGraph is slower than Spine only on the tiny high-diameter chain-like
pair in this review table. This is consistent with the concern that repeated
SSSP levels/supersteps create overhead on small high-diameter graphs.

GraSU+ReGraph is much faster on the fanout/spread/hot-destination review
pairs, but the comparison is not yet strict same-input. Treat this as an
optimization signal, not a final publishable claim.
```

## Strict Same-Edge Spine Comparison

After the scenario-level comparison, we added a stricter Spine front end that
can load the exact `.from_grasu.sssp.edges` files exported by the
GraSU+ReGraph sweep.

Spine host change:

```text
/home/chuxiao/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke.cpp
```

New host option:

```text
--edge-file PATH
```

Edge file format:

```text
src dst [weight [diff]]
```

The loader defaults `weight=1` and `diff=1`, ignores trailing `#` comments,
validates vertex IDs against `MAX_N`, validates weight/diff width, and rejects
files larger than one `HOST_PARTITIONED_RATIO2_MAX_SORT_N` batch.

The first attempt used the latest split xclbin:

```text
/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin
```

That failed because the current local host expected:

```text
spine_partitioned_e2e_kernel
```

but the split xclbin exposes:

```text
spine_partconv_rdmaint_kernel
spine_partconv_compute_kernel
```

For the first strict same-edge run, we therefore used the matching single-CU
Spine xclbin:

```text
/home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/xclbin/spine_partitioned_e2e.hw.xclbin
sha256 ae591fba01896ba6f6835eab866793e932315ffd28459e5e0b7e5c3c2e7ce20c
```

The local Spine host used for this run:

```text
/home/chuxiao/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke
sha256 05aa95bfa1f6859b256dea0936db049b76c89930012df94eceabc1e647fe9713
```

Smoke command:

```bash
cd /home/chuxiao/spine-dynamic-graph
set +u
source /opt/xilinx/xrt/setup.sh
set -u

./tests/test_integration/host_partitioned_csr_e2e_smoke \
  /home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/xclbin/spine_partitioned_e2e.hw.xclbin \
  --edge-file /home/chuxiao/grasu-regraph-integration/results/hw_function_check_20260712_195536_combined/tiny_chain_v16.from_grasu.sssp.edges \
  --timeout 120
```

Smoke evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_edge_file_smoke_single_kernel_20260712_200738
```

Key smoke result:

```text
PARTITIONED_CSR_E2E_SMOKE PASS
case=edge_file
vertices=16
input_edges=15
persisted=15
traversed_edges=15
maint_ms=0.261607
conv_ms=1.04556
kernel_e2e_ms=1.30717
errors=0
```

Sweep command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_spine_edge_file_sweep.sh \
  --chain-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_20260712_195628 \
  --timeout 300
```

Spine same-edge sweep evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_edge_file_review_hw_20260712_200934/summary.tsv
```

Comparison command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/compare_spine_chain_summaries.py \
  --chain-summary /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_20260712_195628/summary.tsv \
  --spine-summary /home/chuxiao/grasu-regraph-integration/results/spine_edge_file_review_hw_20260712_200934/summary.tsv \
  --out-dir /home/chuxiao/grasu-regraph-integration/results/spine_vs_grasu_regraph_edge_file_hw_20260712_201000
```

Strict same-edge comparison evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_vs_grasu_regraph_edge_file_hw_20260712_201000/comparison.md
/home/chuxiao/grasu-regraph-integration/results/spine_vs_grasu_regraph_edge_file_hw_20260712_201000/comparison.tsv
```

Results:

| case | GraSU+ReGraph ms | Spine same-edge ms | chain / Spine | interpretation |
| --- | ---: | ---: | ---: | --- |
| small_chain_v64 | 17.4392 | 1.77427 | 9.82897 | Spine is faster on tiny high-diameter chain input. |
| small_star_v4096_u1024 | 3.23011 | 43.1007 | 0.0749433 | GraSU+ReGraph is faster on low-diameter hot-source fanout. |
| small_spread_v4096_u1024 | 6.01264 | 43.55 | 0.138063 | GraSU+ReGraph is faster on spread fanout. |
| small_hotdst_v4096_u1024 | 9.88242 | 43.3577 | 0.227928 | GraSU+ReGraph is faster on hot-destination updates. |
| medium_star_v65536_u8192 | 9.92411 | 668.18 | 0.0148525 | GraSU+ReGraph is much faster on medium hot-source fanout. |
| medium_spread_v65536_u16384 | 15.2861 | 678.25 | 0.0225376 | GraSU+ReGraph is much faster on medium spread fanout. |

Interpretation:

```text
The strict same-edge run supports the earlier directional conclusion but makes
the small-chain exception sharper. GraSU+ReGraph pays heavily when SSSP needs
many supersteps on a tiny graph; Spine's local maintenance+convergence path is
faster there. For low-diameter fanout/spread/hot-destination inputs, the
GraSU+ReGraph chain wins by roughly 4x to 67x in these six cases.
```

Remaining caveat after this first same-edge run:

```text
This strict same-edge comparison uses a matching single-CU Spine xclbin, not the
latest split-CU Spine xclbin. It proves the edge-file comparison path and gives
useful optimization evidence, but the final latest-Spine comparison still needs
edge-file support on the split-CU host/source or a matching split-capable host
in the local Spine branch.
```

## Strict Same-Edge Split-CU Spine Comparison

We then reproduced the same `--edge-file` patch on the split-capable Spine host
source in a scratch build directory, without modifying the source checkout under
`/home/feiyang`.

Reproducible helper files:

```text
/home/chuxiao/grasu-regraph-integration/patches/spine_split_host_edge_file.patch
/home/chuxiao/grasu-regraph-integration/scripts/build_spine_split_edge_host.sh
```

Build command:

```bash
cd /home/chuxiao/grasu-regraph-integration
BUILD_ROOT=/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_repro2_20260712_201833 \
  ./scripts/build_spine_split_edge_host.sh --target hw
```

Generated split-edge host:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_repro2_20260712_201833/host_partitioned_csr_e2e_smoke_edge
sha256 7e12888aabc8f7716a8e37031145db63df27c66394c84ff189b1185099154b15
```

Split xclbin:

```text
/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin
sha256 69145517738cc1ffff95e91c24393260c346ac683db9eef2989bbc1bdb7a3469
```

Smoke evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_split_edge_file_smoke_repro_20260712_201900
```

Key smoke result:

```text
PARTITIONED_CSR_E2E_SMOKE PASS
case=edge_file
vertices=16
input_edges=15
persisted=15
traversed_edges=15
maint_ms=0.283418
conv_ms=1.41676
kernel_e2e_ms=1.70018
errors=0
```

Six-case split-CU sweep command:

```bash
cd /home/chuxiao/grasu-regraph-integration
SPINE_HOST=/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_20260712_201407/host_partitioned_csr_e2e_smoke_edge \
SPINE_XCLBIN=/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
SPINE_PARTITIONED_SPLIT_VALUE=1 \
OUT_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_split_edge_file_review_hw_20260712_201541 \
./scripts/run_spine_edge_file_sweep.sh \
  --chain-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_20260712_195628 \
  --timeout 300
```

Split-CU same-edge summary:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_split_edge_file_review_hw_20260712_201541/summary.tsv
```

Split-CU comparison output:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_split_vs_grasu_regraph_edge_file_hw_20260712_201607/comparison.md
/home/chuxiao/grasu-regraph-integration/results/spine_split_vs_grasu_regraph_edge_file_hw_20260712_201607/comparison.tsv
```

Results:

| case | GraSU+ReGraph ms | Spine split same-edge ms | chain / Spine split | interpretation |
| --- | ---: | ---: | ---: | --- |
| small_chain_v64 | 17.4392 | 2.17218 | 8.02845 | Spine split is faster on tiny high-diameter chain input. |
| small_star_v4096_u1024 | 3.23011 | 64.8235 | 0.0498293 | GraSU+ReGraph is faster on low-diameter hot-source fanout. |
| small_spread_v4096_u1024 | 6.01264 | 65.358 | 0.0919954 | GraSU+ReGraph is faster on spread fanout. |
| small_hotdst_v4096_u1024 | 9.88242 | 65.1231 | 0.15175 | GraSU+ReGraph is faster on hot-destination updates. |
| medium_star_v65536_u8192 | 9.92411 | 997.137 | 0.00995261 | GraSU+ReGraph is much faster on medium hot-source fanout. |
| medium_spread_v65536_u16384 | 15.2861 | 1023 | 0.0149425 | GraSU+ReGraph is much faster on medium spread fanout. |

Interpretation:

```text
Using the latest available split-CU Spine xclbin does not change the qualitative
conclusion: Spine wins only on the tiny high-diameter chain; GraSU+ReGraph wins
on low-diameter fanout/spread/hot-destination workloads, especially as graph
size grows.

In this edge-file path, the split-CU Spine run is slower than the matching
single-CU Spine run. That is consistent with the split host reporting zero fast
path/gather use and forcing full-path tile processing in this build. It should
be treated as an implementation/architecture signal to inspect, not as a proof
that split is universally worse.
```

## Current Status

Completed:

```text
1. ReGraph weighted SSSP implemented and validated in hw_emu and standalone hw.
2. GraSU + ReGraph linked into one combined hw_emu and real hw xclbin.
3. Combined hw_emu functional check passed.
4. Combined real hw resource evidence collected.
5. Combined real hw functional smoke passed.
6. First combined real hw review sweep and Spine scenario comparison completed.
7. First strict same-edge Spine comparison path completed with a matching
   single-CU Spine xclbin.
8. Strict same-edge comparison also completed for the latest available
   split-CU Spine xclbin using a reproducible scratch host patch/build helper.
```

Remaining:

```text
1. Upstream the split-CU edge-file host change into the chosen Spine branch if
   we want it as a permanent source change rather than a scratch patch helper.
2. Extend capacity/large-graph testing once the comparison front end is aligned.
3. Decide whether to optimize timing/SLR/HBM placement for a stable requested
   clock, or simply report the current xclbin at its achieved 243.8 MHz clock.
```
