# Resident CC And Weighted SSSP Retention Probe

This opt-in host entry runs the integrated sharded-K4 adapter and ReGraph
compute path for one resident superstep without launching GraSU. It does not
change the kernel ABI, the input layout, or the default convergence path.
It is a component control against the public-source four-Little implementation,
not a convergence test or an end-to-end Spine result.

## Input And Output

- Both arms take the same logical CSR graph and initial property values,
  including the active bit. The candidate uses the existing PMA builder and
  address permutation. CC label **values** stay in the original numeric
  domain, even though their storage addresses move.
- The host independently replays a single active-source min relaxation on the
  shared CSR. It rejects duplicates, out-of-domain values, empty propagation,
  and differences from the pinned reference expectation. The reference output
  includes 16 guard words; the candidate checks them on input but does not
  allocate a reference-only guard in the device layout.
- In board mode, both published property replicas and the Apply property
  buffer are converted back to external order and checked against the oracle,
  including the zero-padded tail. The active count must also match.

## Reproduction

Build the native host with
`scripts/build_weighted_pma_native_host.sh --pipeline-mode sharded-k4 --prefetch-compact --algorithm ALGORITHM --out-dir BUILD`
for `weighted_sssp` or `connected_components`. The fixture directory contains
`execution.u32le`, `csr_offsets.u32le`, `csr_destinations.u32le`, and either
`cc_initial.u32le` or `sssp_initial.u32le` plus `sssp_weights.u32le`.
Use the corresponding A4-generated `expected.u32le` as the reference:

```bash
HOST --active-min-prepare FIXTURE_DIR REFERENCE_EXPECTED FRESH_OUTPUT_DIR
```

This mode writes the aligned expected output and does not enumerate or
program FPGA devices. Both Amazon policies passed offline (735,324 vertices,
5,158,388 edges, 12 candidate shards, 10 improved vertices per policy).
The XRT Release hosts built successfully and rejected an incorrect oracle and
an unleased board invocation before device access.

The paired supervisor must pin the image and host, hold an exclusive board
lease, and pass its inherited lock descriptor, device index, and expected
BDF to `HOST --active-min-once XCLBIN FIXTURE_DIR REFERENCE_EXPECTED FRESH_OUTPUT_DIR`.
Compare first R device start through final R publication for each arm on
the same board, with migration, readback, and host packing outside the timer.
Retain each kernel's raw timestamps and the correctness outputs. The physical
layouts and event schedules differ; do not sum overlapping kernel durations.
No FPGA timing or 15% retention result is claimed by the offline checks.
