# Schedule And Integration Repair

This is the active task log for the default-off simulator-aligned HLS profile.
The [contract and source map](README.md) remain authoritative. Earlier raw
evidence is immutable; every synthesis attempt gets a fresh output directory.
The paper and frozen simulator predictions are not being changed.

## Acceptance Gates

| Gate | Current state |
| --- | --- |
| Functional equivalence | Three-format adapter (396 cases), exhaustive valid-mask and random compactor tests pass; connected SSSP/CC/PR Gather and integer Apply pass; RTL validation pending |
| Adapter scheduling | Held-input retry estimates 199.01 MHz at requested 150 MHz, with directory fill and bank request II=1; not post-route timing |
| Apply scheduling | Split request/response integer Apply XO estimates 205.47 MHz at requested 150 MHz; not post-route timing |
| Finite channels and stalls | Random-stall RTL validation in progress; the first attempt stopped before RTL for a missing interface depth and is retained |
| Physical integration | Direct-ingress projection exceeds 32; choose and account for actual sharing rather than raising the audit limit |
| Complete hardware | Not newly linked, routed or board tested; no performance result follows from component export |

Do not promote an unmet gate to a pass. HLS frequency estimates are not
post-route timing. Full-system acceptance requires the actual interfaces,
clock, state semantics, completion boundary and correctness-checked output.

## Current Iteration

The four-level prefix retry (`7876b8a`) passes all adapter/compactor checks and
exports the XO. Estimated clock improves from 62.91 to 78.31 MHz, but still
fails the 150-MHz gate. HLS reassociates prefix arithmetic and reports a
12.770-ns compactor path. The next attempt disables expression rebalancing
in that function rather than declaring this solved.

The bank reader now separates requests and responses into DATAFLOW processes,
as supported by [Vitis HLS 2024.1 manual burst](https://docs.amd.com/r/2024.1-English/ug1399-vitis-hls/Using-Manual-Burst).
Explicit parent and returned-or-reserved line limits remain 16 and 512.
Parent credit returns after response consumption; line credit returns only
after the join consumes that line. Finite internal descriptor/credit FIFOs
are depth 16. C-only locking protects the vendor model's shared pointer map.

Directory tiles now hold 128 packed 512-bit words rather than 1024 individual
64-bit rows. This retains two 8-KiB tiles and row contents, while replacing
eight writes per response with one. The join extracts at most two packed
words for eight consecutive rows. The ignored array partition is removed.
Three-format independent adapter and exhaustive compactor tests pass in
`/data/chuxiao/checks/adapter-split-bank-20261024/`; synthesis is pending.

Raw prefix evidence is retained in
`/data/chuxiao/builds/gr-prefetch-compact-trif-prefix-valid-20261024/`.
The earlier `...-prefix-20261024/` attempt failed before Vitis invocation
because dependency-root environment variables were absent. Neither attempt
is a route or board test. No OOM was recorded.

The first split-bank compile stops at HLS 214-272: expression balancing
cannot be attached to the same function as `INLINE`. The retry puts that
directive on the non-inlined compactor owner. This is a pragma-scope repair,
not a functional pass or a timing result. Failed raw evidence is retained at
`/data/chuxiao/builds/gr-prefetch-compact-trif-split-bank-20261024/`.

Subsequent work targets join/segment registration, compactor feedback timing,
integer Apply timing and explicit physical sharing.
Any changed timing or arbitration contract must be documented and propagated
to a separate simulator profile before claiming matching behavior.

## Selector And Publisher Repair

The split-bank retry exports an XO and changes the bank request II from 36
to 1 and directory fill II from 4 to 1, but its estimate is only 80.43 MHz.
Balancing the source-level OR tree alone does not prevent HLS from flattening
the selection logic. The next implementation separates lane selection from
the stateful publisher using a depth-three `Selected` FIFO. Its estimate is
138.06 MHz. Splitting integer Apply's old-value requests and responses gives
205.47 MHz without changing read-before-write protection for aliased buffers.

The held-input retry moves publisher input acquisition to the end of the
iteration, so a new selected segment is not used in the same iteration.
A statically extracted, fully partitioned lane array replaces the variable
1024-bit range shift. Bank reservation uses an explicit ten-bit count bounded
by 512, retaining the separate 16-parent limit and consume-only line release.
The resulting adapter estimate is 199.01 MHz; all requested loop IIs are met.
These are HLS estimates, not proof of 150-MHz full-system routing.

This adds a selector pipeline and input holding latency versus the frozen
simulator contract. Capacities, edge order, filtering and TLAST semantics
remain covered by the functional tests, but cycle identity is not claimed.
Join registration is still scheduled at three cycles rather than the requested
two. Any simulator/hardware timing comparison must account for both changes.

Evidence roots (never overwrite):

- `/data/chuxiao/builds/gr-prefetch-compact-trif-split-scope-20261024/`
- `/data/chuxiao/builds/gr-prefetch-compact-trif-selector-valid-20261024/`
- `/data/chuxiao/builds/gr-prefetch-compact-trif-held-20261024/`
- `/data/chuxiao/checks/adapter-selector-pipeline-20261024/`
- `/data/chuxiao/checks/adapter-held-20261024/`
- `/data/chuxiao/checks/regraph-selector-split-20261024/`

The selector-valid RTL attempt passes C simulation but stops before RTL
execution because the generated `directory` interface has no cosimulation
depth. Source interface depths now explicitly cover the 16384-word RTL bench;
they do not allocate on-chip copies or impose a runtime graph-size limit.
The replacement RTL attempt keeps all finite FIFO depths and enables random
interface stalls. Its completion is a separate acceptance gate.

## Prediction Boundary

Failure to realize a simulator topology in this FPGA does not by itself make
the simulator a best-case bound. Such a claim needs explicit optimistic
assumptions and a justified lower bound on G+R latency, plus a same-workload,
same-state, same-convergence comparison to Spine. No tenfold advantage is
assumed by this repair task.
