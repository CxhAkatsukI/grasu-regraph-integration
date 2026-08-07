# Residual PageRank full-graph U55C matrix

This directory records three correctness-admitted matched executions for each
of AU, SU, WK, SO, PK, LJ, LJ08, and R19.

- G+R host source: `07c5da447e099494175ed7c266785e003ef4ce2e`
- G+R routed-kernel source: `bfe20249764284f2f16cd77dc2756a2c7a64f1f9`
- Spine source: `3678ad488e0d0fe8538a36a11d87ddffa182fa99`
- G+R xclbin SHA-256:
  `8d47aef98bcaa4cd338bbe5bd32d649db12b6dc15afb0a1d272bb2e47b7b5653`
- Spine xclbin SHA-256:
  `a8bd5c0b19c5aa57a62f0e0ef630f4359e0823e4c102887f61b233ca2f691c38`
- Batch: eight directed insertions
- Threshold: direct per-vertex `epsilon=1e-6`
- State: old graph converged and resident before the timed dynamic update
- Reported comparison: setup-inclusive dynamic latency
- Correctness gate: independent float32 residual-repair oracle plus rank,
  residual, degree, convergence, and update-state checks
- Handoff: destination-sharded weighted PMA directly to ReGraph AXIS; no
  converted edge array

`aggregate_3runs.tsv` reports medians, coefficients of variation, and speedup
ranges. The three `summary_run*.tsv` files retain every admitted performance
row. `matrix.tsv` and `launch_status_run1.tsv` pin the first execution's
workload, artifact, host, device, timeout, and process-exit identities. Large
per-vertex arrays and logs remain under `/data/tmp/chuxiao`.

All 24 architecture pairs are correctness admitted and there is no winner
flip. Median setup-inclusive G+R/Spine speedup ranges from 12.46x to 595.17x;
the minimum individual speedup is 12.18x. The selected insertion batches need
no post-update propagation on Spine. G+R still performs its required global
degree-correction execution over all destination shards. These rows therefore
measure that realized-work regime and must not be generalized to correction
batches that trigger substantial propagation without additional evidence.
