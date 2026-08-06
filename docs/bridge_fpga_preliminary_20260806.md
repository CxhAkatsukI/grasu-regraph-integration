# Preliminary bridge-workload FPGA comparison (2026-08-06)

> Superseded for performance claims by
> `bridge_fpga_resident_comparison_20260806.md`. This document is retained as
> bring-up history and explains why the original cold-start rows were rejected.

## Purpose and evidence boundary

This experiment checks that the routed Spine and conversion-free GraSU+ReGraph
hardware paths can consume matched real-topology bridge workloads. It is a
bring-up experiment, not yet a complete validation of the paper's resident-state
dynamic-update claim.

The workload converter compacts external vertex IDs. The resulting graphs retain
the selected AskUbuntu topology and updates, but they do not retain the original
external-ID address occupancy. All rows use insertion batch 8 at the logical
workload level. Reciprocal CC and PageRank files contain 16 physical directed
updates.

## Reproduction

Prepare the three workloads:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/prepare_bridge_fpga_workloads.sh \
  /data/tmp/chuxiao/matched_fpga_bridge_workloads_20260806
```

Run the matrix on two U55C cards:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_matched_fpga_matrix.sh \
  --matrix configs/bridge_fpga_k4_matrix_20260806.tsv \
  --out-dir /data/tmp/chuxiao/matched_fpga_bridge_k4_20260806 \
  --gr-device 0 \
  --spine-device 1 \
  --timeout 1800
```

The generated summary is:

```text
/data/tmp/chuxiao/matched_fpga_bridge_k4_20260806/summary.tsv
```

## First-run results

| Algorithm | Initial edges | Vertices | G+R event E2E | Spine dynamic kernel | G+R / Spine | Admission |
|---|---:|---:|---:|---:|---:|---|
| Weighted SSSP | 540,000 | 157,107 | 3255.116 ms | 4192.540 ms | 0.776x | Diagnostic only |
| CC | 540,000 | 94,931 | 932.974 ms | n/a | n/a | Rejected |
| CC | 903,774 | 156,289 | 2540.102 ms | n/a | n/a | Rejected |
| Residual PageRank | 540,000 | 94,931 | 586.077 ms | 97.078 ms | 6.037x | Functional only |
| Residual PageRank | 903,774 | 156,289 | 961.750 ms | 159.460 ms | 6.031x | Functional only |

Every passing G+R row reports zero oracle mismatches. Both residual PageRank
Spine rows also pass their independent host checks. These checks establish that
each routed path implements its own current host contract; they do not establish
cross-architecture semantic equivalence. No row in this first run is admitted
as publication performance evidence.

## Why the SSSP row is not a paper-result comparison

The current Spine hardware host initializes SSSP state to infinity, activates
only the source, and then converges over the final graph. It therefore executes
13 cold-start propagation rounds on the 540K-edge workload. The current G+R host
also initializes from the source and executes 13 final-graph supersteps.

The paper's dynamic-update contract starts from a converged resident state for
the old graph, applies the update batch, and propagates only the resulting
differential frontier. The observed 0.776x ratio measures cold recomputation;
it neither validates nor refutes the paper's dynamic SSSP speedup. A valid rerun
must preload the old-graph distances and derive the post-update frontier on the
device.

## Why the CC rows are rejected

The current Spine CC host similarly starts with every vertex active rather than
preloading the old graph's converged labels. On both bridge sizes, the large
cold-start frontier reaches the owner/reactivation path and the host detects an
active-payload mismatch at iteration 1. These rows fail correctness admission
and must not enter any performance aggregate.

The next CC run should first use the resident old-graph labels and a
device-derived update frontier. If the payload mismatch remains under that
paper-aligned workload, it is an owner-FIFO correctness bug that must be fixed
before performance measurement.

## Why the residual PageRank ratios are functional-only

The G+R host preloads the full PageRank solution of the old graph, computes the
post-update correction, and then propagates residuals. The Spine host currently
starts with zero rank and a residual at one source. Both paths are internally
correct, but they solve different initial-value problems and use different
active-frontier semantics. The observed 6.03x ratios are useful for routed-path
bring-up only and must not be quoted as Spine-versus-G+R speedup. A valid rerun
must preload the same old-graph rank in both architectures and apply the same
device-generated degree correction and seed frontier.

## Full-graph simulator versus current HLS boundary

The simulator does use runtime destination partitions and partition offsets,
but that is only part of the explanation for its large-graph support. The
publication campaign uses the
`runtime_packed_interleaved_v2_23pc_capacity_checked` address profile, whose
contract explicitly labels the full-graph mapper as simulator-only and HLS
integration pending.

The routed G+R host currently uses 65,536-vertex destination partitions and
passes a runtime `part_dst_offset` to the shared adapter/compute pipeline. It
nevertheless caps the run at four partitions (`V <= 262,144`) and does not yet
implement the simulator's 23-pseudo-channel runtime-packed full-graph mapping.
Consequently, the routed hardware is aligned with the simulator's compact core
execution domain, not with its full-graph address-mapping domain.

## Next acceptance step

1. Preload converged old-graph SSSP and CC state before the timed update.
2. Generate the update-induced active frontier in the device path.
3. Rerun all five rows and require cross-architecture final-state equivalence as
   well as zero architecture-oracle mismatches.
4. Repeat each semantically matched row at least three times and report the
   median.
5. Keep full-graph mapper integration as a separate HLS milestone; do not infer
   routed full-graph feasibility solely from the simulator mapper.
