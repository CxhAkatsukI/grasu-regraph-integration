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
| Physical integration | Fresh SSSP and CC eleven-XO sets and ResPR twelve-XO set pass; actual master audits are respectively 26/32, 26/32 and 32/32; all three complete Vitis system-link |
| Complete hardware | A local URAM over-allocation is repaired in fresh relink configs; SSSP implementation is running, CC/ResPR await full-budget admission; no fresh routed or FPGA result yet |
| PR correctness gate | Both PR hosts rebuild with finite-value and global L1-error checks; six-partition CPU prepare checks and all 93 repository tests pass; not a board result |
| Spine comparison host | Corrected continuous resident timer passes six board checks on historical owner-FIFO bitstreams; latest sparse-selector hardware and repeated comparison remain pending |

Do not promote an unmet gate to a pass. HLS frequency estimates are not
post-route timing. Full-system acceptance requires the actual interfaces,
clock, state semantics, completion boundary and correctness-checked output.

The followup board gates additionally cover the frozen AU workloads and a
CPU-checked DDR-update stress input. SSSP and CC each report 4,100 actual
DDR updates in that input; PR does not expose the corresponding layout
counter. Every algorithm must first pass its own routed timing and tiny/
six-partition smoke gates. The followup uses the same board mutex and an
atomic full 8-GiB host reservation, a finite process-tree RSS watchdog,
40-GiB live-memory reserve and retained raw evidence. These queued tests
are not board results or performance comparisons. Their run-local code is
`board_followup.py`, with evidence in `board-extended-v1/<algorithm>/`, under
the blocking-AXIS campaign root linked below.

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

## Full-System Implementation And Board Gates

The blocking-write campaign now exports all eleven fresh SSSP XOs. Its own
actual-interface audit passes at 26/32 master instances, and Vitis completes
`system_link`, block-design creation and target generation. These are not
place-and-route or timing passes. The active implementation evidence is
`/data/chuxiao/builds/gr-prefetch-blocking-axis-trif-20261024/route-bounded40/route-sssp/`.
Separate CC and ResPR builds use their own generated packets and XOs; neither
inherits the SSSP component or port-audit result.

Multiplying each SSSP top-level HLS XML resource estimate by its configured
CU count gives 1,006,474 LUTs, 635,558 FFs, 1,434 BRAM18s and 768 URAMs before
platform overhead. That is approximately 77% of whole-device LUTs and 80%
of whole-device URAMs, not a post-synthesis or routed utilization report.
Physical fit and congestion remain open gates.

The queued board gate accepts only this campaign's successful routed artifact,
checks input and executable hashes, rejects an occupied card, and verifies the
150-MHz U55C `DATA_CLK`. The separate platform `KERNEL_CLK` control clock is
not required to be 150 MHz. An earlier queued board supervisor was stopped
before programming to correct that clock classification; its evidence is
retained with a supersession record.

Fresh board smoke tests check update-only and old-converged-state-to-new-
convergence behavior on tiny and six-partition SSSP graphs against CPU oracles.
Passing these four tests would establish bring-up correctness only, not the
full performance matrix, simulator cycle agreement or a speedup over Spine.
The replacement board evidence is `board-sssp-retry/` under the campaign root.

## Finite Route-Budget Retry

The SSSP and CC implementations stop at `tree_rss_budget`, at sampled
process-tree RSS totals of 42,616,696 and 42,386,496 KiB respectively. The
watchdog sums each process's RSS, including shared pages per process; it is
not the same quantity as cgroup charged memory. SSSP's cgroup peak is
38,601,826,304 bytes. Both attempts record zero OOM events and over 120 GiB
of available host memory at their lowest sample. These are containment
stops, not failed device fit or timing. ResPR's 40-GiB attempt is deliberately
interrupted before hitting the same ceiling; its raw output remains retained.

Fresh `route96/{sssp,cc,respr}/` attempts consistently use a 96-GiB cgroup
hard limit, 88-GiB high watermark, zero swap, group OOM termination, and a
96-GiB process-tree RSS watchdog. Both the direct containment check and the
atomic lease validate that finite profile, including peer reservations.
The 40-GiB live-memory floor and 8-GiB background reserve remain. Admission
counts each complete competing budget, so queued services do not imply
simultaneous compiler execution. Old generated build outputs are not reused
as successful results or overwritten: new configuration changes only build
output locations, retaining the same XOs, connectivity and requested clock.

`board96/<algorithm>/` waits for the corresponding fresh routed artifact,
requires the actual routed setup/hold/pulse-width timing summary to pass,
checks the DATA clock, and serializes our tests on device one without
resetting external users. PR uses the new checked host binaries. FullPR has
an independent component compile; its current host computes three fixed
rounds, **not convergence**. Neither that packet nor a successful CPU prepare
check is routed or board evidence.

## Local URAM Placement Repair

The sharded packet generators place `process_cache_1/2` in SLR0/2 and
Little CUs 1/2/3/4 in SLR0/1/2/0. Their own top-level HLS XML reports give
256 URAM per cache CU and 64 per Little CU. Thus the old placement requests
384/64/320 URAM across SLR0/1/2, exceeding SLR0's 320-URAM capacity even
though the whole-device total is only 768/960. This is a local placement
problem, not evidence that the modeled algorithm cannot be realized.

The fresh relink changes only `lksg_stream_4` from SLR0 to SLR1, giving
320/128/320. It retains the accepted XOs, all memory/stream connections,
cache capacities, clock and algorithms. `uram-screen.json` records the
actual HLS XML hashes; Vivado's generated fourth-Little SLR XDC independently
confirms SLR1. This screen covers those URAM consumers, not all resources,
shell capacity, routing congestion or timing.

Evidence is isolated in `route-slr-v2/{sssp,cc,respr}/` beneath
`/data/chuxiao/builds/gr-prefetch-blocking-axis-trif-20261024/`.
The corresponding `board-slr-v2/` workers require routed timing and smoke
correctness before any result can be called a board pass. Older `route96/`
jobs are deliberately interrupted with their logs retained, not reported as
device-fit failures. The finite 96/88-GiB policy remains unchanged.

An attempted generator edit during a concurrent FullPR component compile
triggered its final source-pin check. That run remains `FAILED_RETAINED`;
its unaccepted cache XO is not promoted. The generator edits were restored
to the exact pinned version. `route-slr/` also retains its before-Vitis pin
rejections. Current repairs change only independently pinned relink configs;
the default generator correction must wait until no active run pins it.
FullPR restarts all twelve components from a fresh `fullpr-retry/fullpr/`
packet and `fullpr-retry/algorithm-evidence/fullpr/` evidence root. Its route
and board gates accept only that retry's own component results.

## Additional CPU Preflight Coverage

The unchanged AU matrix inputs pass all four host capacity/oracle prepare
checks. They have 515,281 vertices and eight destination partitions:
390,847 initial SSSP edges, 679,246 CC edges, and 826,848 PR edges. SSSP
performs two resident propagation rounds, CC one, and residual PR zero at
the fixed per-vertex `1e-6` threshold. FullPR still means three fixed rounds,
not convergence. These checks are CPU-only, not speedup or FPGA evidence.

Those sparse AU updates all hit the cache path. A separate deterministic
reciprocal-star input has 131,076 vertices, 262,150 initial edges and
262,149 updates. Its SSSP/CC layout counters each identify 4,100 DDR-path
updates beyond the unchanged 131,072-segment cache boundary. All four CPU
oracles/capacity checks pass in `ddr-preflight-v2/`, with zero OOM events.
PR hosts do not expose this layout counter, so their DDR count is not
inferred from the integer-host logs. This is a functional stress input,
not a performance workload or a board test. An earlier `ddr-preflight/`
attempt rejected a finite 96-GiB peer through an older 40-GiB-only check;
the retry validates both the 8-GiB host limit and finite peer budgets.

## PR Validation Strengthening

The original per-vertex absolute tolerance could admit a badly wrong global
rank vector when each rank is small. The existing per-vertex condition is
retained, but both PR hosts now additionally require finite expected/actual
values and total L1 error no greater than `1e-4 + 1e-3 * expected_l1`.
The allowance is not multiplied by the number of vertices. Regression checks
reject an all-zero vector, systematic bias, NaN and infinities while accepting
the oracle and small floating-point noise. This strengthens correctness
admission only; it does not alter epsilon, algorithm work or timing windows.
Host manifests also hash the included shared native-host source and new
validation header. New PR binaries and six-partition CPU preflights are in
`hosts-rankguard/{respr,fullpr}/` under the blocking-write campaign root.

## Spine Comparison Prerequisite

The old Spine summed timing field is not the continuous resident wall used
by the G+R host. A separate resident host mode includes maintenance,
propagation, inter-round host relaunch, in-window transfers and final
readback. Source review also finds per-round CPU reference edge counting
inside that new timer; Spine commit `877ae3d` moves it after final readback
while retaining each round's source frontier for validation.

All four corrected hosts compile and the three injected-runtime tests pass.
Six corrected-host tests then pass on real U55C hardware: SSSP, CC and
residual PR, each on tiny and six-G+R-partition inputs. Residual PR performs
22 and three propagation rounds. Evidence is under `spine-resident-host-v6/`
and `spine-resident-legacy-smoke-v6/` in the blocking-write campaign root.
The earlier twelve legacy/resident checks remain separately retained.

These use fixed historical owner-FIFO bitstreams, not the latest sparse
selector. They are host-compatibility gates, not latest-architecture timing
calibration or repeated performance results. The complete G+R routes and
their own board gates remain prerequisites to a new comparison.

Spine commit `e6a7503` also matches the resident PR global L1/finite-value
guard to the G+R host. Four v7 hosts compile and three offboard tests pass,
including rejection of small per-vertex errors that accumulate beyond the
global limit. This changes only post-timing host validation, not kernel inputs.
The fresh sparse-ResPR Spine build is queued behind the three G+R smoke gates;
its own timing/clock and tiny/six-partition/AU/DDR board checks are queued
separately. These are pending gates, not fresh hardware or speedup results.

## Prediction Boundary

Failure to realize a simulator topology in this FPGA does not by itself make
the simulator a best-case bound. Such a claim needs explicit optimistic
assumptions and a justified lower bound on G+R latency, plus a same-workload,
same-state, same-convergence comparison to Spine. No tenfold advantage is
assumed by this repair task.
