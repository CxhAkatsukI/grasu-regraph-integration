# Connected-components full-graph U55C matrix

This directory records three correctness-admitted matched executions for each
of AU, SU, WK, SO, PK, LJ, LJ08, and R19.

- G+R source: `6a7fa47d05ba6fad8ebf8514135a5af4e3f95c3b`
- Spine source: `3678ad488e0d0fe8538a36a11d87ddffa182fa99`
- G+R xclbin SHA-256:
  `f871add9ba8333432373df24bac0272b46e7224c592d69bc594e503be51da7e4`
- Spine xclbin SHA-256:
  `e3d103fcca2c6718ffaacdc6309db9b39047714c53e15c77a087149997f0096b`
- Batch: eight logical undirected insertions, represented as 16 directed
  updates
- State: old graph converged and resident before the timed dynamic update
- Reported comparison: setup-inclusive dynamic latency
- Correctness gate: independent CPU connected-component membership oracle
- Memory policy: serial architecture execution, per-process 32 GiB hard cap,
  18 GiB runtime reserve, and process-group termination on guard failure

`aggregate_3runs.tsv` reports medians, coefficients of variation, and speedup
ranges.  `summary_run1.tsv`, `launch_status_run1.tsv`, and `matrix.tsv` retain
the first execution and frozen launch identities.  The three raw-evidence hash
files authenticate the complete logs and result arrays retained under
`/data/tmp/chuxiao`; the large arrays are deliberately not committed to Git.

All 24 architecture pairs are correctness admitted.  There is no winner flip.
G+R setup-inclusive latency has at most 0.062% CV; the setup-inclusive
G+R/Spine speedup ranges from 9.96x to 1,107.82x over all individual samples.
