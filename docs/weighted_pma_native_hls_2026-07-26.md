# Weighted PMA-Native HLS Candidate

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

No result from this branch is native hardware evidence until a matching xclbin
passes emulation, synthesis, route, and board correctness gates.

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
- performs the same update-density vertex reorder used by the GraSU host;
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
reads those streams in the same round-robin order. The lowered pair therefore
reaches the single process stream selected for its PMA segment in delete-then-
insert order; there is no same-segment concurrent write in this topology.

## Executable Test Evidence

`tests/pma_to_regraph_adapter_tb.cpp` invokes the synthesizable top function
with one real 16-slot PMA segment. It checks both 8-lane AXIS bursts, two
different non-unit weights, source IDs, empty lanes, and the final `last` bit.
The check script compiles and runs the same test twice, once per ABI mode.
`tests/weighted_pma_graph_test.cpp` separately emulates the existing HLS
full-word binary-search/update behavior and compares the resulting graph with an
independent external-ID weighted-edge oracle. It covers delete, insert, weight
decrease, weight increase, malformed delete rejection, vertex reorder, and a
row spanning the 16/17-entry segment boundary.

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
e3423844d0b3cb5007e3f47729faaa87e8db2429c900dfeec69b26c70c9d63d1  weighted_pma_graph.hpp
7726393924b3fe92970cd5ef72544606f818de8d98acb1f2a8e8d219cfe516d9  weighted_pma_graph_test.cpp
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

The generated manifest deliberately records:

```text
PIPELINE_MODE=weighted-axis
CLAIM_CLASS=candidate_hls_not_yet_built
HANDOFF=weighted_pma_to_axis_stream
CONVERSION_COST=absent
```

`tests/test_prepare_weighted_pma_native_build.py` generates both modes in an
isolated fixture, checks both command scripts with `bash -n`, verifies the
selected kernels/ports/macros, and ensures the default compactor contract is
unchanged. Reproduce it with:

```bash
python3 tests/test_prepare_weighted_pma_native_build.py
```

```text
9c476569ad91adf7b43a2c2d464433a1aa911192d2ab4506536ef95473b08bc1  prepare_pure_hw_pipeline_build.sh
3d37d04175d403eb4c52ac0e5042266e04d77b652a1959bb12410d08f3cc624a  test_prepare_weighted_pma_native_build.py
```

## Remaining Before Full Xclbin Compile

1. The weighted dataset parser and `WeightedPmaGraph` output must be wired into
   the OpenCL host buffers and GraSU's four-HBM replicated/interleaved layout.
2. The host must launch the adapter on every SSSP round, preserve the update
   completion barrier, and validate weighted distances against an independent
   CPU oracle.
3. `sw_emu` is the first whole-system gate. Only after it passes should the
   long `hw_emu` and `hw` commands be launched.

The complete weighted kernel graph now has generated compile/link commands, but
the matching host is not complete. Building this xclbin can check synthesis and
link connectivity; it cannot yet establish end-to-end weighted correctness.
