# Schedule And Integration Repair

This is the active task log for the default-off simulator-aligned HLS profile.
The [contract and source map](README.md) remain authoritative. Earlier raw
evidence is immutable; every synthesis attempt gets a fresh output directory.
The paper and frozen simulator predictions are not being changed.

## Acceptance Gates

| Gate | Current state |
| --- | --- |
| Functional equivalence | Three-format adapter (396 cases), exhaustive 65,536-mask and 4,096-random-segment compactor checks pass; blocking-write repair passes all 24 random-stall RTL transactions |
| Adapter scheduling | Held-input retry estimates 199.01 MHz at requested 150 MHz, with directory fill and bank request II=1; not post-route timing |
| Apply scheduling | Split request/response integer Apply XO estimates 205.47 MHz at requested 150 MHz; not post-route timing |
| Finite channels and stalls | Three formats each pass all eight output comparisons with zero UVM errors; earlier failures remain retained |
| Physical integration | Earlier shared-ingress XOs audit to 26/32 master instances; all eleven components are being rebuilt after the AXIS repair; full link remains gated |
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
depth. Source interface depths now explicitly cover the 2048-word RTL bench;
they do not allocate on-chip copies or impose a runtime graph-size limit.
The replacement RTL attempt keeps all finite FIFO depths and enables random
interface stalls. Its completion is a separate acceptance gate.

## Shared Ingress And RTL Test Environment

The shared-ingress SSSP packet exports all eleven component XOs. Reading the
exported interfaces and multiplying by the actual CU counts gives 26 master
instances against the unchanged 32-port direct-link budget. See
[the physical profile](PHYSICAL_PORTS.md); passing this audit does not establish
that placement, routed timing or execution succeeds.

Vitis HLS 2024.1 generates inconsistent AXI VIP parameterizations for the
shared adapter: the DUT's three logical even-channel clients require two ID
bits, but generated environment/interface/sequence types retain one. The first
RTL run hung after a directory response was assigned to the wrong ID. A first
repair fixed the environment and interfaces, but exposed a remaining one-bit
slave-sequence type as a UVM virtual-interface lookup failure. Both failed
attempts and original generated files are retained, not reclassified as passes.

`tests/repair_cosim_axi_ids.tcl` now derives each bundle's width from DUT RTL
and repairs all five corresponding generated type occurrences across three
testbench files, plus the VIP ID capacity. It never edits the DUT. The repair
is restricted to the inspected 2024.1 template, validates every anchor before
writing anything, backs up originals and refuses repeated application. Python
tests check mixed one/two-bit bundles, unchanged DUT bytes, backups and
fail-closed behavior. This addresses the test environment, not design latency.

Fresh random-stall RTL evidence is under
`/data/chuxiao/builds/gr-prefetch-shared-channels-trif-20261024/complete-id-retry/`.
Routing is gated on all eight output comparisons in each of the three edge
formats and zero protocol errors. The component evidence and actual-port audit
are under the same campaign root in `evidence/` and
`sssp/pipeline_master_budget.json`. Earlier `rtl/` and `id-width-retry/` evidence
remains immutable. No routing or FPGA result is implied by these directories.

Each RTL/compiler worker has a 40-GiB cgroup hard limit, 36-GiB high limit,
no swap and group OOM termination. The current route retry uses those same
40/36-GiB limits; the initial 64/60-GiB supervisor attempts never invoke Vitis.
Admission reserves complete concurrent worker budgets and system headroom;
it does not depend on current RSS alone. Any OOM, timeout, source-pin change,
missing output comparison or failed prerequisite rejects that attempt.

## AXIS Output Backpressure Repair

With all generated VIP ID types repaired, the eight RTL transactions finish
but expose duplicate/missing output packets and invalid terminal ordering.
The C post-check fails and UVM reports errors. This is a design failure,
not another testbench failure, and it blocks full-system routing. Its raw
evidence remains in the `complete-id-retry/` directory above.

`publish_selected` used `write_nb` directly on the top-level AXIS output.
[UG1399 2024.1](https://docs.amd.com/r/2024.1-English/ug1399-vitis-hls/Non-Blocking-API)
does not support nonblocking AXIS writes. The retry uses blocking `write`
and advances the existing three-entry publication queue only after the
write completes. Output stalls can now block the publisher iteration;
the queue is not enlarged, and this is not a cycle-equivalence claim to
the frozen simulator. The HLS estimate remains 199.01 MHz with all requested
loop IIs satisfied; only fresh RTL and routed execution can accept it.

The Tcl driver now also checks UVM error counts and all eight C post-check
markers before printing success: generated `sim.sh` may exit zero despite
a failed comparison. The independent Python supervisor retains the same
checks. Neither exit status nor the pre-RTL C simulation alone is sufficient.

Fresh evidence is isolated under
`/data/chuxiao/builds/gr-prefetch-blocking-axis-trif-20261024/`.
All 92 repository tests pass with explicit external dependency roots.
The shared-HBM wrapper test now respects `REGRAPH_ROOT` instead of requiring
an untracked vendor checkout under `repos/`. The functional recheck passes
396 adapter cases and the exhaustive/random compactor suite. All three RTL
formats each pass eight post-check comparisons, with zero UVM errors. These
results are separate from the eleven fresh SSSP component compiles.

The first route supervisor in this campaign stopped before invoking Vitis:
its inherited containment check only admitted 40/36-GiB cgroups, while the
route service requested 64/60 GiB. This is a supervisor mismatch, not a
synthesis or routing result. A second queued supervisor overrides the direct
check, but inspection finds that the atomic lease also imports the original
40/36-GiB check. It is stopped before Vitis invocation, with a supersession
record retained. The replacement in `route-bounded40/` uses the supported
40/36-GiB profile consistently for cgroup, reservation and watchdog, retaining
40 GiB of system headroom and zero swap. No containment check is bypassed.

## Prediction Boundary

Failure to realize a simulator topology in this FPGA does not by itself make
the simulator a best-case bound. Such a claim needs explicit optimistic
assumptions and a justified lower bound on G+R latency, plus a same-workload,
same-state, same-convergence comparison to Spine. No tenfold advantage is
assumed by this repair task.
