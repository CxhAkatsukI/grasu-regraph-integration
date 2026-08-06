# Weighted SSSP full-graph U55C matrix

This directory records one correctness-admitted matched execution for each of
AU, SU, WK, SO, PK, LJ, LJ08, and R19.

- G+R source: `700a8bd11970573dcd01fbf82f8238ee8b19795b`
- Spine source: `3678ad488e0d0fe8538a36a11d87ddffa182fa99`
- G+R xclbin SHA-256:
  `292ae9e468dda3d9d1941d1ab46e1696643956122d134ec366711e4acda2ceaf`
- Spine xclbin SHA-256:
  `b6e415f0d749d831a5ee5d98acbd691749cbd13b8a20945b306085f668b69862`
- Batch: eight logical insertions
- State: old graph converged and resident before the timed dynamic update
- Reported comparison: setup-inclusive dynamic latency
- Correctness gate: independent weighted Dijkstra oracle
- Memory policy: serial architecture execution, per-process hard cap,
  18 GiB runtime reserve, and process-group termination on guard failure

`summary.tsv` contains only admitted performance rows.  `launch_status.tsv`
records process exits and memory-guard status.  `matrix.tsv` pins all workload,
host, source, and xclbin paths.  `raw_evidence.sha256` authenticates the raw
logs and result arrays retained under `/data/tmp/chuxiao`; the large result
arrays are deliberately not committed to Git.

The matrix currently contains one run per row.  It is architectural and
functional hardware evidence, not a claim about run-to-run variance.
