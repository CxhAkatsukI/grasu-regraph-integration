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

## Executable Test Evidence

`tests/pma_to_regraph_adapter_tb.cpp` invokes the synthesizable top function
with one real 16-slot PMA segment. It checks both 8-lane AXIS bursts, two
different non-unit weights, source IDs, empty lanes, and the final `last` bit.
The check script compiles and runs the same test twice, once per ABI mode.

```bash
cd /home/chuxiao/grasu-regraph-integration

./scripts/check_pma_to_regraph_adapter.sh \
  --out-dir .tmp_build/pma_to_regraph_adapter_weighted_20260726

./scripts/check_regraph_stream_little_gs.sh \
  --out-dir .tmp_build/regraph_stream_little_gs_weighted_candidate_20260726
```

Both commands pass with Vitis HLS 2024.1 headers. Source hashes from the
adapter test are:

```text
d3193f17ed6d444dd66dcacb1ca019540fac5ae2034c575679bb46733a5d1edb  pma_to_regraph_adapter.cpp
d9eba56b839a09c3a75b216a96e39f7c9db84948b1f5a4cd237aacb1d29165f1  pma_to_regraph_adapter_tb.cpp
```

## Remaining Before Full Xclbin Compile

1. The GraSU host must ingest weight and map vertex IDs before packing the
   32-bit PMA word.
2. GraSU binary search and PMA update must compare by destination, not by the
   complete packed word, so a weight change replaces an edge rather than
   inserting a second destination.
3. The build generator must restore the proven adapter-to-`lksg_stream` AXIS
   topology and compile the adapter with the weighted definition.
4. The host must launch the adapter on every SSSP round, preserve the update
   completion barrier, and validate weighted distances against an independent
   CPU oracle.
5. `sw_emu` is the first whole-system gate. Only after it passes should the
   long `hw_emu` and `hw` commands be launched.

The adapter alone is ready for XO synthesis, but the whole weighted system is
not yet ready for a long build. Issuing a full build now would only prove the
front-end ABI and would not satisfy end-to-end correctness.
