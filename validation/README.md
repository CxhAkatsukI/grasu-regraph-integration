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
watchdog resources. Host compilation includes the actual core and testbench in
one translation unit, recording both as dependencies. This avoids duplicate
non-inline globals in vendor stream headers, without a linker waiver or kernel
change. HLS checks the source reference's complete command matrix and replays its
functional log analysis, rather than trusting only a PASS string. Compiler
warnings and HLS estimates remain raw observations, not timing closure.

## Current Evidence

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
