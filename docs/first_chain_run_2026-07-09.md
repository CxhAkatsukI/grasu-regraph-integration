# First GraSU -> ReGraph Chain Run

Date: 2026-07-09

Repository:

```bash
/home/chuxiao/grasu-regraph-integration
```

## Command

```bash
cd /home/chuxiao/grasu-regraph-integration
timeout 240s ./scripts/run_grasu_regraph_pr.sh \
  --result-dir results/full_chain_tiny
```

## Workload

Generated case:

```text
tiny_spread_v16_u8
vertices: 16
static edges: 16
updates: 8
final edges: 24
```

Files:

```text
workloads/generated/tiny_spread_v16_u8/tiny_spread_v16_u8.graph
workloads/generated/tiny_spread_v16_u8/tiny_spread_v16_u8.result
results/full_chain_tiny/tiny_spread_v16_u8.regraph.edges
```

The GraSU result file uses `src -> dst` with hexadecimal vertex IDs because the
current GraSU checker reads IDs with `%lx`. The ReGraph input uses decimal
`src dst` pairs.

## GraSU Evidence

Log:

```text
results/full_chain_tiny/grasu.log
```

Key lines:

```text
check result passed
node_num: 16
static_edge_num: 16
update_edge_num: 8
kernel finish
time is 1.797941 ms
throughput is 0.004450 M updates per second
```

## Conversion Evidence

Log:

```text
results/full_chain_tiny/convert.log
```

Key line:

```text
converted_edges=24
```

## ReGraph Evidence

Log:

```text
results/full_chain_tiny/regraph.log
```

Key lines:

```text
Graph .../tiny_spread_v16_u8.regraph.edges is loaded.
vertex num: 16
edge num: 24
Device[0]: program successful!
Accelerator starts computation...
BIG_KERNEL finished...
[INFO] little kernel:  executed dense partitions: 1, overall time 0.200535 ms;
[INFO] ... e2e: 0.223626 ms;  Throught: 0.107322 MTEPS :
Verifying end-to-end on hardware vs. end-to-end on software...
Processed edges: 32; Graph edges: 24
```

## Current Caveat

This proves the integration pipe can run:

```text
GraSU update/check -> final graph conversion -> ReGraph PR hardware run
```

It is not yet a fair SSSP comparison against Spine. The current ReGraph artifact
is PageRank (`APP=pr`). For a fair Spine comparison, the next step is to build or
prepare a ReGraph BFS/SSSP-compatible artifact, or restrict graphs to unit-weight
cases and compare against BFS semantics.

