# Connected-components AU U55C gate

This directory records the first real-U55C correctness gate for the routed
destination-sharded K4 connected-components artifact.

- Source: `b2164362c4e74e11dd2c3e058faa5b6d188d1b38`
- Xclbin SHA-256:
  `f871add9ba8333432373df24bac0272b46e7224c592d69bc594e503be51da7e4`
- Workload: AU full-graph materialization, eight destination shards
- Resident graph: 515,281 vertices and 679,246 reciprocal edges
- Batch: eight logical insertions, expanded to 16 physical updates
- State: old graph converged and resident before the timed dynamic update
- Architecture: four PMA/gather frontends and one shared ReGraph downstream
- Handoff: direct stream, with no converted edge array
- Correctness: zero mismatches against the independent CPU oracle

`run.log`, `run.env`, and `summary.tsv` are the compact execution evidence.
The 6.6 MB per-vertex result file remains under `/data/tmp/chuxiao`; its hash
is retained in `evidence.sha256`.
