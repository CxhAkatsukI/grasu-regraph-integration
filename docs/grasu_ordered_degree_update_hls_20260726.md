# GraSU Ordered Degree Update HLS Prototype

Date: 2026-07-26

## Claim class

This milestone is a **functional, synthesizable-source prototype** for the
conversion-free PageRank path.  It is not measured FPGA performance and it is
not yet a matching implementation of the simulator's four post-PMA degree
FIFOs and reorder buffer.

The prototype deliberately exposes an `early_degree_sideband` optimization:
`dispatch_degree` restores the original host update order and emits the source
degree delta before the four PMA writers finish their segment writes.  The
current normalized-v3 simulator instead emits each delta after the associated
PMA write response and reorders four completion streams.  Until the simulator
and HLS use the same choice, results from this prototype belong to the
`projected` profile, not the `native` or matching-HLS profile.

## Data path

```text
bin_search[0..3]
       | striped update streams (host index i mod 4)
       v
dispatch_degree -- original GraSU routing --> process_cache[0..1]
       |                                      process_ddr[0..1]
       |
       +-- ordered {ordinal, source, delete} AXIS
                                      |
                                      v
                              grasu_degree_update
                                      |
                                      v
                            out_degree HBM read/modify/write
```

`dispatch_degree` consumes the four `bin_search` streams in round-robin order,
which reconstructs host update ordinals `0, 1, 2, ...`.  A 64-bit AXIS packet
contains:

| Bits | Meaning |
|---|---|
| 31:0 | source vertex |
| 32 | delete flag (`0` insert, `1` delete) |
| 63:33 | original update ordinal |
| `TLAST` | terminal marker |

`grasu_degree_update` accepts exactly `update_count` data packets followed by
one terminal packet.  It checks the ordinal, source range, delete underflow,
and insert overflow.  The first error is returned in `status[0]`; the number of
successfully committed degree updates is returned in `status[1]`.  For errors
that do not consume the terminal packet, the kernel drains the remaining batch
before returning so a finite AXIS FIFO cannot deadlock the producer.

## Correctness scope

The ordered stream makes repeated updates to the same source deterministic.
For example, insert/delete/insert updates for one source produce `+1`, `-1`,
`+1` in host order.  This is required by Full PageRank and thresholded residual
PageRank because their source map divides rank or residual by the current
out-degree.

The current code does not yet prove transaction atomicity when another kernel
accesses the same degree array concurrently.  The host contract for this
milestone is therefore:

1. launch PMA update and degree update as one update phase;
2. wait for both to complete;
3. launch the ReGraph compute round.

No compute CU may read `out_degree` before the update-phase barrier.

## Reproduction

From `/home/chuxiao/grasu-regraph-integration`:

```bash
scripts/check_grasu_degree_update.sh \
  --out-dir .tmp_build/grasu_degree_update_phase1_20260726
```

The test covers routing, reconstructed ordering, repeated-source insert/delete,
source out of range, ordinal mismatch, delete underflow, insert overflow, early
termination, missing termination, and stream draining.  The emitted manifest
hashes every source and the test binary.  Its claim class is
`functional_protocol_test_not_synthesized_hardware`.

## Promotion gates

This prototype can move from `projected` to a normalized matching-HLS profile
only after all of the following are true:

- the simulator models this exact early-sideband location, FIFO depth, HBM
  port, and update/compute barrier, or the HLS path is changed to emit four
  post-PMA completion streams like normalized-v3;
- `sw_emu` validates update plus Full PageRank and residual PageRank against an
  independent CPU oracle;
- HLS/Vitis compile evidence identifies achieved II and all AXIS/HBM ports;
- implementation evidence reports resources and timing at the selected shared
  clock and U55C HBM profile;
- holdout workloads show identical final degrees and algorithm state.

Until those gates pass, this code supports feasibility work and projected
experiments, but not an absolute FPGA throughput or iso-resource speedup claim.
