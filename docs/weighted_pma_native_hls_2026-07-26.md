# Weighted PMA-Native HLS `sw_emu` Proof

Date: 2026-07-26

Branch: `codex/weighted-pma-native-hls`

## Goal

This branch starts the compile-ready HLS counterpart of the simulator's
conversion-free normalized GraSU/ReGraph design:

```text
GraSU weighted PMA -> direct AXIS adapter -> ReGraph weighted SSSP scatter
```

The existing hardware-validated native baseline remains unchanged:

```text
GraSU raw-destination PMA -> one-shot compactor -> edge array -> ReGraph
```

The complete weighted-axis pipeline now passes `sw_emu` against an independent
CPU oracle. This is whole-system functional evidence, but it is not native
hardware performance, resource, timing-closure, or board-correctness evidence.
Those claims remain gated on `hw_emu` and real `hw` builds/runs.

## Implemented ABI Boundary

`pma_to_regraph_adapter` now has two compile-time modes:

| Compile definition | PMA input | AXIS destination word |
| --- | --- | --- |
| default / `=0` | raw destination | `dst19 + unit_weight(1)` |
| `GRASU_REGRAPH_WEIGHTED_PMA=1` | `dst19 + weight12` | unchanged packed word |

Bit 31 remains the dummy/empty marker in both modes. Weighted mode strips that
bit from a valid payload and restores it only for a dummy lane. It therefore
preserves ReGraph's existing decoder contract:

```text
destination = word[18:0]
weight      = word[30:19]
dummy       = word[31]
```

The default mode is deliberately byte-compatible with the previous adapter;
the currently accepted compactor xclbin is not rebuilt or relabeled.

## Weighted PMA Host Preprocessing

`include/weighted_pma_graph.hpp` is an integration-owned, dependency-free C++
preprocessor for the existing GraSU PMA ABI. It:

- validates the one-partition `dst19 + weight12` range;
- performs GraSU's update-density vertex reorder using physical PMA operations
  as the work count, with vertex ID as a deterministic tie-break;
- maps vertex IDs before packing destination and weight;
- reserves every packed `(destination, weight)` variant that a batch may
  insert, then emits 16-word PMA segments, packed row bounds, and full 64-bit
  binary-search heads; and
- emits physical updates in the exact full-word ordering expected by the
  unmodified `bin_search`, `process_cache`, and `process_ddr` kernels.

Those kernels compare the complete packed PMA word. A logical weight change
therefore cannot be represented as one existing update: the preprocessor lowers
it to `delete(old dst+weight)` followed by `insert(new dst+weight)`. This is
functionally correct and preserves the existing HLS implementation, but it
counts as two physical updates in performance and energy results. A future
destination-keyed replacement kernel is an optimization point, not part of the
native baseline.

GraSU's four `bin_search` CUs consume update indices `i mod 4`, while `dispatch`
reads those streams in the same round-robin order. When a lowered delete/insert
pair targets the same segment, both operations therefore reach the same process
stream in order. If the two packed weight variants fall in different segments,
they may execute independently; that is safe because they update distinct PMA
slots and the completion barrier holds compute until all four process CUs have
finished.

The builder reserves one all-dummy 16-slot segment for a completely empty graph.
This is not a graph edge or hidden conversion: ReGraph's stream GS kernel uses
blocking reads and needs at least one 8-edge burst to complete its protocol.

## Executable Test Evidence

`tests/pma_to_regraph_adapter_tb.cpp` invokes the synthesizable top function
with one real 16-slot PMA segment. It checks both 8-lane AXIS bursts, two
different non-unit weights, source IDs, empty lanes, and the final `last` bit.
The check script compiles and runs the same test twice, once per ABI mode.
`tests/weighted_pma_graph_test.cpp` separately emulates the existing HLS
full-word binary-search/update behavior and compares the resulting graph with an
independent external-ID weighted-edge oracle. It covers delete, insert, weight
decrease, weight increase, malformed delete rejection, vertex reorder, and a
row spanning the 16/17-entry segment boundary. It also checks empty-graph stream
termination and that weight changes count as two operations for cache-density
reordering. Duplicate insertion of an already-present `(src, dst, weight)` is
rejected rather than silently charged as zero work or duplicated in PMA.

```bash
cd /home/chuxiao/grasu-regraph-integration

./scripts/check_pma_to_regraph_adapter.sh \
  --out-dir .tmp_build/pma_to_regraph_adapter_weighted_20260726

./scripts/check_weighted_pma_graph.sh \
  --out-dir .tmp_build/weighted_pma_graph_20260726

./scripts/check_regraph_stream_little_gs.sh \
  --out-dir .tmp_build/regraph_stream_little_gs_weighted_candidate_20260726
```

All three commands pass with Vitis HLS 2024.1 headers. Source hashes from the
adapter test are:

```text
d3193f17ed6d444dd66dcacb1ca019540fac5ae2034c575679bb46733a5d1edb  pma_to_regraph_adapter.cpp
d9eba56b839a09c3a75b216a96e39f7c9db84948b1f5a4cd237aacb1d29165f1  pma_to_regraph_adapter_tb.cpp
1f9939c047251b19c1cfb9d67c682d6305793ba1a12c3ffd35f02685ffc2a409  weighted_pma_graph.hpp
42832c966f6019f6f640e5658d9f74df0dc7da9eb4c23e15e930bec1d90745d7  weighted_pma_graph_test.cpp
```

## Whole-System Build Generator

`prepare_pure_hw_pipeline_build.sh` preserves the accepted compactor pipeline
as its default and adds an explicit weighted candidate mode:

```bash
cd /home/chuxiao/grasu-regraph-integration

GRASU_ROOT=/home/chuxiao/GraSU \
REGRAPH_ROOT=/home/chuxiao/ReGraph \
./scripts/prepare_pure_hw_pipeline_build.sh \
  --target sw_emu \
  --pipeline-mode weighted-axis \
  --build-root .tmp_build/weighted_pma_native_sw_emu_20260726
```

The generated config contains the four GraSU update CUs, completion barrier,
weighted PMA adapter, `lksg_stream`, little-GS merger, HBM wrapper, and apply
kernel. It has no compactor, edge-array buffer, or `part_edge_array` HBM port.
The adapter compile command includes `GRASU_REGRAPH_WEIGHTED_PMA=1`.

The generated pre-build manifest deliberately records:

```text
PIPELINE_MODE=weighted-axis
CLAIM_CLASS=candidate_hls_not_yet_built
HANDOFF=weighted_pma_to_axis_stream
CONVERSION_COST=absent
```

That value describes the generated build packet before compilation. The smoke
runner produces a separate immutable run claim after the built xclbin passes
its oracle. `tests/test_prepare_weighted_pma_native_build.py` generates both
modes in an isolated fixture, checks both command scripts with `bash -n`,
verifies the selected kernels/ports/macros, and ensures the default compactor
contract is unchanged. Reproduce it with:

```bash
python3 tests/test_prepare_weighted_pma_native_build.py
```

```text
713ef7505dee4ae83416e54b1051b9bf184c362270355d9d1510acbb6b0d9264  prepare_pure_hw_pipeline_build.sh
27bb1fbde95ee135ef0f89e862753e11d7c5b593ac075997a83244e13d8b6941  test_prepare_weighted_pma_native_build.py
```

## Weighted Host And CPU Oracle Gate

`tools/weighted_pma_native_host.cpp` is the matching OpenCL host. It parses
weighted initial edges and updates, independently replays the final graph in
external vertex IDs, builds the weighted PMA, distributes physical updates over
the four GraSU inputs, lays even/odd cache and DDR segments into the same four
HBM buffers consumed by the adapter, and maps the source and result properties
through the vertex reorder.

For each requested superstep it launches the PMA adapter and ReGraph stream GS,
HBM wrapper, and apply kernels. The first adapter waits for the four-CU GraSU
completion barrier. Hardware mode compares every returned property word with a
synchronous weighted SSSP oracle and writes `external_vertex distance` rows.

The short gate builds the host with an embedded XRT `RUNPATH`, then checks:

- the tracked insert/delete/increase/decrease workload (`5` logical updates,
  `8` physical PMA operations, maximum distance `14`);
- an empty graph with the required 16 dummy slots;
- rejection of a delete with the wrong current weight; and
- rejection of zero, which is outside the positive `weight12` ABI;
- rejection of duplicate same-weight insertion; and
- rejection of a CLI integer outside the 32-bit kernel ABI.

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_weighted_pma_native_host.sh
```

This short gate's evidence class is intentionally
`host_preprocessing_and_cpu_oracle_only`, with `HARDWARE_EXECUTED=0`. The whole-
system gate below has a distinct claim class. The latest source hashes are:

```text
bba058ed9ca0785f2abf35e8e6436ceaec1467ded52488128a0633ee8b855085  weighted_pma_native_host.cpp
f37837193cba969dd670131735f68dcc72524b33f56a7dfd912bb041e69c213f  build_weighted_pma_native_host.sh
8d6b2e22ea095ecc626fe8141edbabdd2d2e302342a618804ae917447b0a5816  check_weighted_pma_native_host.sh
adb3c32417e73a172ae6cb6eaced7d93618942e53260e9dea2a5c9bd6634a959  weighted_pma_native_tiny.graph
```

## Whole-System `sw_emu` Proof

The full conversion-free pipeline was compiled and linked as 15 CUs: four
`bin_search` CUs, `dispatch`, two `process_cache` CUs, two `process_ddr` CUs,
the completion barrier, weighted PMA adapter, `lksg_stream`, little-GS merger,
HBM wrapper, and apply kernel. There is no compactor or intermediate edge-array
buffer. The tracked weighted workload passed the independent synchronous SSSP
oracle:

```text
WEIGHTED_PMA_NATIVE_RESULT status=PASS mismatches=0 vertices=8 final_edges=5 logical_updates=5 physical_updates=8 processed_edge_slots_per_superstep=64 source_external=0 source_internal=0 supersteps=4 conversion_cost=absent
```

Expected external-ID distances were exactly:

```text
0 0
1 3
2 10
3 14
4 12
5 2147483646
6 2147483646
7 2147483646
```

Evidence is archived at:

```text
evidence/weighted_pma_native_sw_emu_ff13a67/
```

The bundle contains the run log/result, run environment, build/input manifests,
all generated compile/link commands, all ten compile step logs, the link step
log, and relative SHA-256 checksums. The xclbin is intentionally omitted because
of its size, but is bound by hash:

```text
3e819201c8846299a0b5f40ed66be7043fa6f2b1e97bdc7dbba2e2171edaa0ba  grasu_regraph_weighted_pma_native.sw_emu.xclbin
cbe32e71ff832b4378a69b888e25b11aa8b4116a737f87ae8e95d51397b1fe53  weighted_pma_native_host
```

Reproduce the build and run with:

```bash
cd /home/chuxiao/grasu-regraph-integration

GRASU_ROOT=/home/chuxiao/GraSU \
REGRAPH_ROOT=/home/chuxiao/ReGraph \
./scripts/prepare_pure_hw_pipeline_build.sh \
  --target sw_emu \
  --pipeline-mode weighted-axis \
  --build-root .tmp_build/weighted_pma_native_sw_emu_repro

./.tmp_build/weighted_pma_native_sw_emu_repro/compile_commands.sh
./.tmp_build/weighted_pma_native_sw_emu_repro/link_command.sh
./scripts/build_weighted_pma_native_host.sh \
  --out-dir .tmp_build/weighted_pma_native_sw_emu_repro/host

./scripts/run_weighted_pma_native_smoke.sh \
  --target sw_emu \
  --host .tmp_build/weighted_pma_native_sw_emu_repro/host/weighted_pma_native_host \
  --xclbin .tmp_build/weighted_pma_native_sw_emu_repro/build/grasu_regraph_weighted_pma_native.sw_emu.xclbin \
  --out-dir results/weighted_pma_native_sw_emu_repro
```

The first compile attempt exposed one integration-owned generator omission:
`lksg_stream` did not receive ReGraph's `kernel_little_gs` include directory.
The generator now supplies it and the complete rebuild passes. The run still
reports eight inherited GraSU `ap_uint` bitsize warnings. They did not produce a
functional mismatch here, but remain a synthesis audit item.

The reported `sw_emu` milliseconds must not be used for performance comparison.
The valid claim is only: the complete conversion-free weighted PMA-to-ReGraph
pipeline executes and returns the correct result in software emulation.

## Remaining Whole-System Gates

1. Build and run the same source/ABI under `hw_emu`, requiring zero oracle
   mismatches.
2. Build a routed `hw` xclbin, archive Vivado timing/resource reports, and run
   the same correctness gate on U55C.
3. Only the real-`hw` run may contribute weighted-axis latency/throughput data;
   even then, a broader workload matrix is required before comparison claims.
