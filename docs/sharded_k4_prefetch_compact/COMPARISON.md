# Resident FPGA Comparison

This protocol is separate from component export, routing and board bring-up.
It does not declare any pending hardware run successful. Do not use the older
`run_matched_fpga_matrix.sh` defaults for this campaign: they select a historical
Spine worktree and summarize component spans instead of the corrected resident
host's continuous wall.

## Admission

Use the same immutable graph file, insertion batch, algorithm, SSSP source and
old-graph state on both sides. Both must reach new-state convergence. Residual
PR uses damping 0.85, 128 old-state initialization rounds and a direct per-vertex
threshold of `1e-6`, not a threshold divided by the vertex count. The initial
rank convention and correction semantics must match. FullPR's current
three-fixed-round check is not admitted as a convergence comparison.

Every result requires its own accepted artifact, actual routed setup/hold/
pulse-width timing, 150-MHz DATA clock, device identity and CPU-oracle check.
Retain input, executable and bitstream SHA256s, source provenance, compiler
version, commands, environment and raw stdout/stderr. Historical owner-FIFO
Spine bitstreams may establish compatibility but must not be relabeled as
fresh sparse-selector hardware. Source or build equivalence needs its own
explicit provenance evidence; a matching filename is not that evidence.

Serialize card programming with the campaign's common mutex and external-user
check. Each host needs a finite cgroup and atomic budget admission against
compiler workers, no swap, a live available-memory floor and a timeout.
No device reset or unbounded host launch is part of this protocol.

## Timing And Repetition

The primary quantity is the continuous resident update-to-final-readback wall,
including host relaunch and intermediate readbacks. Initial file parsing,
old-state oracle construction, allocation and graph/state migration are
outside. Final oracle checks are also outside. Spine's remaining CPU residual
correction is **inside** its wall. G+R's legacy `setup_inclusive_ms` field is
its continuous resident wall, not initial graph setup. Do not substitute a sum
or union of kernel events, or Spine's `dynamic_setup_inclusive_ms`, for these
two wall measurements.

Start with tiny/six-partition bring-up, then the frozen AU and DDR functional
gates. Only after acceptance, collect one excluded warm-up and at least three
new-process repetitions per architecture and workload. Each process preloads
the same old state and applies the batch once. Alternate architecture order;
record CPU affinity and other compiler activity. Preserve all samples,
including failures; report the two wall medians, variation and the ratio of
wall medians, not a selected best run. A short demo is not the eight-graph
matrix or a universal speedup claim.

## Log Check

`scripts/compare_resident_fpga_logs.py` checks one completed log pair. It rejects
duplicate records, cold starts, nonconvergence, count/source mismatches,
diagnostic repeated updates, incorrect PR threshold, nonfinite values and
invalid global rank-error limits. It reads the wall fields above. For example:

```bash
python3 scripts/compare_resident_fpga_logs.py \
  --algorithm weighted_sssp --source 11 \
  --gr-log /ABS/NEW/gr/run.log --spine-log /ABS/NEW/spine.stdout.txt \
  --output /ABS/NEW/pair.json
```

The output is explicitly `log_semantics_only_not_provenance_or_hardware_acceptance`.
The checker cannot infer source equivalence, matching graph hashes, successful
routing or board identity from stdout. Those remain independent runner gates.
Its synthetic unit fixtures are parser tests, not hardware measurements.

A failed FPGA realization also does not establish that the frozen simulator
is a proven optimal-performance bound. An optimistic prediction needs stated
assumptions and evidence that every omitted cost benefits the baseline; a
claimed tenfold advantage still needs an admitted measured or predicted pair.
