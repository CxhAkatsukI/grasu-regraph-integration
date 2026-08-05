# Conversion-Free Shared ReGraph Multi-Partition HLS

## Scope

Commit `bb2bd3bf41ae14117fc38979c7fd188e907b85b2` extends the
conversion-free GraSU -> ReGraph pipeline from one destination partition to at
most four `65,536`-vertex destination partitions (`V <= 262,144`). This is the
hardware profile called **K4-shared** in the comparison work.

`K4-shared` does not mean four complete ReGraph workers. The xclbin still has
one adapter, one little scatter/gather worker, one merger, one apply kernel,
and one HBM wrapper. The host invokes the adapter and scatter/gather worker
once per destination partition while one HBM/apply execution covers all state
partitions. Therefore:

- GraSU still uses its four PMA/update lanes;
- ReGraph destination partitions execute serially on one shared worker;
- the PMA-to-ReGraph handoff remains an AXIS stream with no edge-array
  conversion;
- the AXI-master count does not grow with the number of destination
  partitions; and
- complete-worker replication (`--compute-pipelines 4`) remains a separate
  idealized design and is not represented by these xclbins.

## Data path

For destination partition `p`, the host passes
`part_dst_offset = p * 65536` and the valid vertex count to
`pma_to_regraph_adapter`. The adapter scans the PMA image and emits the normal
fixed-length stream, but marks destinations outside that partition as dummy.
`lksg_stream` consumes the stream with the matching destination offset. The
same adapter and worker are then reused for partition `p + 1`.

The state buffers and HBM/apply burst count are padded to
`ceil(V / 65536) * 65536`. This preserves ReGraph's partition-local scratch
addressing while allowing the output state to cover every input vertex.

The cost of the current implementation is explicit: every destination
partition causes another PMA scan and adapter/little-GS pass. Results must not
be described as four-way parallel ReGraph execution.

## Correctness gate

The checked workload is
`workloads/pma_native_two_partition_tiny/pma_native_two_partition_tiny.graph`.
It has `65,537` vertices and edges in both directions across the `65,536`
partition boundary, so a one-partition implementation cannot pass by silently
ignoring the second partition.

All four algorithms passed software emulation against their independent host
oracles:

| Algorithm | Executions | Key result |
| --- | ---: | --- |
| Weighted SSSP | 2 supersteps | `mismatches=0`, converged |
| Connected Components | 2 supersteps | `mismatches=0`, converged |
| Full PageRank | 3 rounds | `rank_mismatches=0`, `degree_mismatches=0` |
| Residual PageRank | correction + 5 propagation rounds | `rank_mismatches=0`, converged at `epsilon=1e-6` |

Each result reports `destination_partitions=2`,
`shared_regraph_pipelines=1`, and `conversion_cost=absent`.

Local artifacts from the acceptance run are:

```text
/data/tmp/chuxiao/grasu_regraph_k4shared_sssp_swemu_20260805/two_partition_run.log
/data/tmp/chuxiao/grasu_regraph_k4shared_cc_swemu_20260805/two_partition_run.log
/data/tmp/chuxiao/grasu_regraph_k4shared_fullpr_swemu_20260805/
/data/tmp/chuxiao/grasu_regraph_k4shared_respr_swemu_20260805/two_partition_run.log
```

Software-emulation times are functional evidence only and must not enter a
performance comparison.

## Short reproducible checks

```bash
cd /home/chuxiao/grasu-regraph-integration
git switch codex/four-algorithm-fpga-matrix
git rev-parse HEAD

./scripts/check_pma_to_regraph_adapter.sh
./scripts/check_weighted_pma_native_host.sh
./scripts/check_connected_components_pma_native_host.sh
./scripts/check_full_pagerank_pma_native_host.sh
./scripts/check_residual_pagerank_pma_native_host.sh
python3 -m unittest discover -s tests -v
```

The adapter HLS reports an estimated `205.47 MHz` at a `150 MHz` target and
`segment_loop` II=2. The old one-partition adapter has the same II=2, so the
partition-range filter did not add an II regression. The weighted and CC
adapters expose five AXI masters; the PageRank adapter shares row offsets with
`gmem0` and exposes four.

## Hardware packets

The final 150 MHz U55C packets are rooted at:

```text
/data/tmp/chuxiao/grasu_regraph_k4shared_sssp_hw_bb2bd3b_20260805
/data/tmp/chuxiao/grasu_regraph_k4shared_cc_hw_bb2bd3b_20260805
/data/tmp/chuxiao/grasu_regraph_k4shared_fullpr_hw_bb2bd3b_20260805
/data/tmp/chuxiao/grasu_regraph_k4shared_respr_hw_bb2bd3b_20260805
```

Each packet records the repository commit in `manifest.env`, hashes every XO
in `xo.sha256`, contains a current host binary, and has a complete
`link_command.sh`. Unchanged XOs were copied byte-for-byte from their accepted
K1 packets; the changed adapter XO was rebuilt from `bb2bd3b`. Every final
xclbin must be newly linked and routed because the adapter control ABI gained
the destination-range arguments.

## Promotion criteria

A packet becomes hardware performance evidence only after all of the
following hold:

1. `v++ --link` completes and the routed timing report is archived.
2. The matching current host passes on a real U55C with the two-partition
   boundary workload.
3. The same xclbin passes at least one frozen calibration workload and one
   disjoint holdout workload.
4. The result reports zero oracle mismatches and records both event-window and
   setup-inclusive timing.
5. Spine and G+R rows use the same graph, mutation batch, algorithm semantics,
   device clock, and timing-window definition.
