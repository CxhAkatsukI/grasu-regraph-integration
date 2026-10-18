# Production Validation

Each validation package owns one experiment contract. Raw logs, binaries,
exported XOs and compiler projects belong in a fresh external campaign directory,
not in this source tree. Never reuse a passing output path for a new run.

## Complete GraSU Components

`grasu_complete/` validates `kernels/grasu_complete/` without changing its
algorithm. The modules separate command construction, input/runtime freezing,
functional/export analysis, source-reference admission, memory execution and CLI.
The CLI reuses the simulator's existing atomic compiler lease and process-tree
watchdog. Set `PYTHONPATH` to this repository and the explicitly pinned simulator
worktree; it does not invoke a simulator timing model.

| Stage | Required Inputs | Success Means |
| --- | --- | --- |
| `source` | Owned production cores, explicit external search fixture, upstream config, installed vendor headers | Eighteen ordered search oracle checks and six full-cache state checks for **each** token/plain binding |
| `hls` | Same inputs plus passing fresh source campaign and real HLS settings | Source-based csynth and XO export for search/token cache/plain cache; argument names/order checked, full ABI and RTL still pending |
| `rtl` | Passing production HLS campaign, frozen search/token-cache reference interfaces and real HLS settings | Same-core C simulation, synthesis, Verilog co-simulation and full interface review for all three components; still not integrated G or routing |
| `integration.study` | Actual production search/cache, upstream dispatch/cold kernels, external finite host fixture and installed vendor headers | Eighteen connected host transactions, full intermediate PMA state, finite external stalls and a stale-metadata rejection; not integrated RTL or device BO refresh |
| `routing.study` | Independently rechecked production RTL, connected host state, same-export storage ledger and frozen eleven-XO basis | Experimental same-source link packet, then bounded routing when admitted; not integrated RTL, board correctness or performance agreement |

The search fixture executes both generations at the same metadata addresses,
including 0, 1, 63, 64, 65, 127, 128, 129 and 257 updates. Its host-only finite
internal FIFOs are not a hardware timing model. The fixture does not stall the
top-level output. It does **not** establish integrated device metadata refresh
or integrated backpressure correctness. The cache oracle checks all 131072 words
after each case, input drain, and completion token payload/sidebands when enabled.
None of these stages establishes G+R correctness, routing, board timing, publication
matching or simulator performance calibration.

Use the **actual production integration** `kernel_config.h`, including its
completion-token type/helper and cache-capacity override. The pristine author's
header is a different control and does not define that existing integration ABI.
Do not add replacement token definitions to a testbench to conceal a wrong input.

```bash
export PYTHONPATH=/path/to/integration:/path/to/pinned/spine-cycle-sim
python3 -m unittest discover -s tests -p 'test_grasu_complete_validation.py' -v

# Run inside a contained systemd/cgroup job, not an unbounded shell.
python3 -m validation.grasu_complete.study --stage source \
  --output /data/fresh-functional-campaign \
  --fixture /path/to/frozen/common_g/hls \
  --config /path/to/integration/repos/GraSU/GraSU/GraSU_kernels/src/kernel_config.h \
  --include /path/to/Vitis_HLS/2024.1/include

python3 -m validation.grasu_complete.study --stage hls \
  --output /data/fresh-hls-campaign \
  --source-reference /data/fresh-functional-campaign \
  --fixture /path/to/frozen/common_g/hls \
  --config /path/to/integration/repos/GraSU/GraSU/GraSU_kernels/src/kernel_config.h \
  --include /path/to/Vitis_HLS/2024.1/include \
  --hls-settings /path/to/Vitis_HLS/2024.1/settings64.sh

python3 -m validation.grasu_complete.rtl \
  --baseline /data/fresh-hls-campaign \
  --search-reference /path/to/frozen/search-reference-xml-directory \
  --cache-reference /path/to/frozen/token-cache-reference-xml-directory \
  --hls-settings /path/to/Vitis_HLS/2024.1/settings64.sh \
  --output /data/fresh-rtl-campaign

# Read-only recheck in a separate finite-memory job; never edits the RTL result.
python3 -m validation.grasu_complete.admission \
  --attempt /data/fresh-rtl-campaign \
  --config /path/to/integration/repos/GraSU/GraSU/GraSU_kernels/src/kernel_config.h \
  --output /data/fresh-component-recheck
```

Containment is mandatory: source uses exactly 1-GiB `MemoryMax` and at most
768-MiB `MemoryHigh`; HLS/RTL use exactly 8-GiB max and at most 7-GiB high. All
require zero swap and group OOM kill. Admission sums full finite peer budgets
and a 24-GiB reserve under the shared short atomic lease lock. It **does not**
wait for all FPGA tools to exit if those budgets fit. Unknown/unbounded peers
prevent admission. Memory waiting is bounded at 24 hours; children have separate
timeouts and a live-memory watchdog. Keep the supervisor cgroup alive until its
compiler descendants are gone.

`results.json` records identities, commands, affinity, containment, observations
and failures. `source/` freezes cores, fixtures, config and vendor headers;
`runner/` freezes imported experiment code; `raw/` retains per-step logs and
watchdog resources. Source/HLS/RTL children use a fresh campaign-owned
`temporary/` as `TMPDIR`; they never silently fall back to a full global `/tmp`.
Host compilation includes the actual core and testbench in
one translation unit, recording both as dependencies. This avoids duplicate
non-inline globals in vendor stream headers, without a linker waiver or kernel
change. HLS checks the source reference's complete command matrix and replays its
functional log analysis, rather than trusting only a PASS string. Compiler
warnings and HLS estimates remain raw observations, not timing closure.

## Current Evidence

The cache comparison-stage candidate in the source guide is newer than the
component campaigns listed below. Those retained passes do not admit that
new cache source. Its fresh campaigns and physical timing must be evaluated
separately; no frozen campaign or running route is edited in place.

Fresh comparison-stage results use the same external experiment root below.
`g-cache-comparison-functional-v1` passes all eighteen search and six full-state
checks for each cache binding; result SHA-256 is
`1f75d3fc32e5b8f96ab98ab4f018827030da228146561411b2e66c9786f501f5`.
Its 1-GiB, zero-swap service invocation is
`6beb82374f0b447ca1c8e30b52e1bb1d`; every memory-event counter is zero.
The separately compiled `g-cache-segment-comparison-v1/probe` passes all 26112
segment/key cases, checking both insertion and deletion. Binary SHA-256 is
`80c7cf8de897b5a302e16510ee94e16af8110f24c8c85ad9dea03b930f1ee1dc`;
service invocation `3f836942f0ec47968230ab8e08a07049` exits zero. The dependency
file and systemd journal retain this supplemental host check; it is not a
component RTL campaign or latency measurement.

Fresh `g-cache-comparison-hls-v1` is owned by
`spine-g-compare-hls-20261018-v1.service`, invocation
`9a1dfa6f6b3348bcba3de7d0fdedb4b0`, with 8/7-GiB max/high, zero swap and
CPU affinity 123. HLS scheduling/export, fresh RTL and physical timing remain
pending at this checkpoint. Forty-one focused Python tests pass; these validate
the source/evidence runners, not FPGA performance. Connected host testing is
separate in `g-cache-comparison-connected-v1`, invocation
`1215e3c3341548f6a831d273ea1f922b`, under the 1-GiB source containment.

Under `/data/chuxiao/experiments/baseline_hardware_validation_20261015/`,
`g-production-functional-v5` passes all eighteen search and twelve cache checks.
`g-production-hls-v3` consumes that exact source reference and exports all three
components successfully. Each reports a rounded 6.67-ns target and a 4.867-ns
estimate. All cgroup OOM counters remain zero. These are isolated components,
not a newly routed complete G or measured performance agreement.

Earlier attempts remain intact: functional v1/v2 exposed duplicate host
translation units and a wrong upstream configuration; HLS v1 used the wrong
header selection, and v2 rejected the report's rounded clock after successful
search export. The clock parser now accepts only the requested period rounded
to the report's declared precision. It does not relax the target or treat an
estimate as physical timing closure.

The complete exported search and token-cache interfaces match their frozen
hardware references: argument registers, memory/control ports, control protocol
and AXIS payload/sidebands. The plain cache has a separate **derived** contract:
the token-cache interface with only its completion port removed. It is not
claimed to be the same interface as the routed token-cache reference.

`g-production-rtl-v1` passed source freezing, full ABI review and concurrent
memory admission, then failed at C-simulation compilation: HLS stripped the
quotes from a header-name `-D` flag. No RTL transaction ran. The retained result
is a test-launch failure, not a hardware or numerical failure. The new launcher
freezes a host-only preinclude header instead; synthesis sees no harness macro.
Thirteen focused tests pass, including actual preprocessing in both modes.
`g-production-rtl-v2` completed alongside both 40-GiB routes under its 8-GiB
limit and the 24-GiB reserve. Its final result is
`PRODUCTION_COMPONENT_RTL_ABI_PASS_NOT_INTEGRATED_OR_ROUTED`: eighteen search,
six token-cache and six plain-cache Verilog transactions pass, as do all three
full exported-interface checks. Every cgroup memory-event counter is zero.
Service `spine-g-production-rtl-20261016-v2.service`, invocation
`42c27a70bef64799868a738cddcb3929`, owns this run. The original diagnostic
route still uses its frozen older exports, not these new production outputs.

The RTL continuation keeps input freezing (`rtl_preparation.py`), interface
inspection (`abi.py`), functional/transaction analysis (`rtl_analysis.py`) and
execution (`rtl.py`) separate. It hashes the original and frozen source members,
requires the earlier complete HLS matrix, and checks the exported interfaces
again after co-simulation. Isolated tests do not stall the top-level output and
do not close integrated-G backpressure or metadata-refresh gates.

`admission.py` independently rechecks the complete successful RTL matrix, raw
execution records, current owned source/config, frozen source and all exported
interfaces. It refuses partial, changed or promoted evidence. Its output is
`PRODUCTION_COMPONENT_RTL_RECHECK_PASS_NOT_COMPLETE_G`; it does not admit an
integrated route, external RTL backpressure, board timing or publication match.
Run this read-only command in a 1-GiB hard / 768-MiB high / zero-swap job.
`g-production-readmission-v1` passed in 0.760 seconds with a 23.7-MiB cgroup
peak, without modifying the original component report. Six focused negative
and preservation tests accompany the reviewer.

The separate `g-production-resource-fit-v1` storage screen uses these production
search/token-cache HLS reports and the reviewed bank-wide adapter. Its unrelocated
configuration exceeds SLR0 URAM capacity (384 versus 320). Moving only
`lksg_stream_4` from SLR0 to SLR1 gives 320/128/320 URAM across the three SLRs;
the device total is 768 versus 960. This is a storage-placement screen, not
complete resource fit or timing closure. A fresh integrated route still needs
its own same-version composition, metadata/backpressure and physical gates.

## Connected Production Host Check

`grasu_complete/integration/` owns input freezing, execution, result admission
and evidence delivery separately. Its fixture connects four actual production
search cores, upstream dispatch, two full-capacity registered cache halves and
two upstream cold-DDR kernels. All six PMA buffers are checked in full after
every transaction. Counts 0, 1, 63, 64, 65, 127, 128, 129 and 257 each run with
two metadata generations, reusing the same allocations and persistent PMA state.
External FIFOs have depth two (completion depth one); delayed consumers force
backpressure for every count at least 63. Search's internal finite metadata
credit and update/END conservation checks remain enabled.

```bash
python3 -m validation.grasu_complete.integration.study \
  --output /data/fresh-connected-host-campaign \
  --fixture /path/to/frozen/common_g/hls \
  --upstream /path/to/integration/repos/GraSU/GraSU/GraSU_kernels/src \
  --include /path/to/Vitis_HLS/2024.1/include

python3 -m validation.grasu_complete.integration.delivery \
  --output /data/fresh-connected-host-capsule \
  --attempt /data/retained-connected-host-failure \
  --attempt /data/fresh-connected-host-campaign
```

Use the same mandatory 1-GiB hard / 768-MiB high / zero-swap source containment,
atomic admission and 24-GiB reserve as above. Cache C simulation gets an explicit
32-MiB host stack; search workers retain their 1-MiB host stacks. These are host
execution limits, not proposed FPGA storage or performance parameters.

`g-production-connected-functional-v2` passes all eighteen transactions and
rejects the deliberate stale-metadata run at one update, generation one. It
retains exactly 417 independently counted pairs of the upstream cold insertion
width warnings and rejects any unknown diagnostic. v1 completed the functional
rows but its analyzer rejected those warnings; it remains `FAILED_RETAINED`.
The v2 service invocation is `eb4580e16cde4cedbf9e763ca98db3e2`; all cgroup memory
event counters are zero. Compilation took 6.41 s and the positive host check
23.31 s, not device latency. This is a new check of the promoted production
owner, not the first connected source test in the simulator campaign.

Internal cache/cold streams remain unbounded in C simulation. The fixture
neither calls XRT nor checks real device BO refresh, RTL scheduling, adapter/R
handoff, routing, board timing or publication agreement. The diagnostic route
still uses older frozen exports and must not be promoted to this source version.

## Production-Source Experimental Route

`grasu_complete/routing/` keeps upstream reuse checks, candidate gates, packet
freezing and the thin CLI separate. It reuses the simulator's tested eleven-XO
freezer and atomic memory supervisor; it does not copy their orchestration or
change an algorithm, clock, request budget, stream connection or timing factor.
Only search and token cache are replaced with `g-production-rtl-v2` exports.
The other nine XOs retain the adapter-route basis. Only the fourth Little CU's
placement moves from SLR0 to SLR1, as screened against platform URAM capacity.

```bash
export PYTHONPATH=/path/to/frozen/integration:/path/to/frozen/spine-cycle-sim
python3 -m validation.grasu_complete.routing.study \
  --build /path/to/historical/sharded-k4-build \
  --basis /data/frozen-adapter-route-basis \
  --rtl /data/g-production-rtl-v2 \
  --connected /data/g-production-connected-functional-v2 \
  --fit /data/g-production-resource-fit-v1 \
  --config /path/to/actual/upstream/kernel_config.h \
  --output /data/fresh-production-source-route --link-timeout-seconds 43200 \
  --execute
```

Use a 40-GiB hard / 36-GiB high / zero-swap / group-OOM-kill service with
two synthesis/implementation jobs. Allow the 24-hour memory queue plus the
12-hour link deadline and cleanup in its finite service lifetime. Admission
requires all finite peer caps plus 40 GiB own, 24 GiB reserve and 8 GiB
background, under the shared lease. It starts alongside other tools when
that budget fits; unknown or unbounded peers prevent admission.

The gates replay production component RTL/ABI, connected full-state results
and the storage screen, and compare all eleven owned cores plus provenance
and upstream configuration. Isolated and connected host-only fixtures have
different purposes and separate hashes; they are not synthesis inputs. The
initial input-review v1 incorrectly compared a host fixture as an owned core
and stopped before packet creation. Its journal is retained. Corrected v2
checks all thirteen owned/configuration members and 2,308 pins successfully,
with a 24.7-MiB cgroup peak and zero memory events. Tests still reject any
owned-source mismatch, missing member or changed frozen runner.

Reused dispatch/cold XOs must match their historical compile flags, target,
150-MHz clock, original/current source hashes and embedded source. The
connected CPU fixture defines `GRASU_SHARE_HBM_PORTS`; the reused cold hardware
XO does not. That flag changes AXI pragmas, not CPU operations. This difference
is explicitly recorded: CPU agreement cannot verify four-master device aliasing.

Preparation freezes every imported validation/experiment runner and Python
identity. The manifest records `candidate_owner=production-source-grasu-complete`
and keeps integrated RTL, device metadata refresh, production baseline and
publication matching unadmitted. A link exit code still requires strict routed
timing/topology review and actual continuous-batch state, PMA handoff and host
window tests. The earlier diagnostic route remains separate and unchanged.
