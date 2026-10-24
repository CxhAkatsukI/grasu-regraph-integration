# Routed Signoff Before Programming

## Separate Checks

Setup, hold and pulse-width summaries do not check bus-skew assertions.
AMD documents that bus-skew is reported separately and is optimized only by
`route_design`, not by ordinary timing optimization. See
[UG903, About Bus Skew Constraints](https://docs.amd.com/r/2024.2-English/ug903-vivado-using-constraints/About-Bus-Skew-Constraints?contentId=kXqymQdxWW597oxcQ4ClQw)
and [UG906, Running Report Bus Skew](https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/Running-Report-Bus-Skew).
An intermediate routing warning is not a final violation; equally, a passing
ordinary timing summary does not establish passing bus-skew constraints.

The 2026-10-24 campaign therefore holds all pending new G+R board smoke
workers and the fresh Spine sparse-ResPR board worker frozen until a separate
read-only audit accepts each own final checkpoint. Existing source pins,
algorithm semantics and timing boundaries are unchanged. This gate does not
prove the frozen simulator's arbitration or timing assumptions realizable.

## Reviewed Helpers

- `scripts/report_routed_bus_skew.tcl` opens a final checkpoint in Vivado
  2024.1 and generates an unfiltered, default min/max report. It does not
  route, change clocks, remove constraints or write a replacement checkpoint.
- `scripts/check_routed_bus_skew.py` validates routed report state, command
  scope, sequential constraint IDs, complete summary rows, finite values,
  nonnegative slack and requirement/actual/slack consistency. Wrapped cell
  selectors and negative actual skew are supported. Unsupported versions,
  partial commands and malformed or violating rows fail closed.
- `NA` rows are retained as unmeasured, not counted as numeric passes.
  They produce `ROUTED_BUS_SKEW_REVIEW_REQUIRED`. A review must identify each
  exact report and summary and explain why no bus-skew path exists; a broad
  waiver for arbitrary future constraints is not accepted.
- `tests/test_check_routed_bus_skew.py` checks both accepted and rejected
  fixtures. These are parser tests, not a new routed or board result.

The parser was also exercised on the historical Spine CC 2024.1 post-route
report. It found 370 constraints: 369 numerical rows and one `NA` row on a
single-bit platform frequency-counter crossing. It correctly required review
instead of silently reporting that all 370 constraints were measured. This
historical report is not signoff for any new G+R design.

The full Python regression suite passes 100 tests after this addition
(`gr-routed-signoff-source-tests-v2`, 2026-10-24): 27.923 seconds of test
execution, 266.9 MiB peak service memory, under a 4/3-GiB hard/high cgroup
with no swap. The first invocation retained seven dependency/import errors
because it omitted the external repository paths. The successful invocation
sets `REGRAPH_ROOT=/home/chuxiao/regraph/ReGraph`,
`GRASU_ROOT=/home/chuxiao/GraSU`,
`HLS_INCLUDE=/data/yxx/tools/xilinx/Vitis_HLS/2024.1/include`, and
`PYTHONPATH=/home/chuxiao/spine-cycle-sim/spine-cycle-sim-fullgraph-evidence`.
No model or kernel was changed to obtain this regression pass.

## Campaign Evidence

Live records and raw reports are in
`/data/chuxiao/builds/gr-prefetch-blocking-axis-trif-20261024/bus-skew-signoff-v1/<algorithm>/`.
The algorithm key is `sssp`, `cc`, `respr`, `fullpr` or `spine-respr`.
The run-local supervisor `bus_skew_audit.py` pins its helpers, final checkpoint,
artifact and build acceptance record; it reserves 40 GiB atomically, uses a
40/36-GiB hard/high cgroup with zero swap and group OOM termination, and keeps
40 GiB live headroom. Source changes, tool failures and watchdog stops retain
evidence and do not release a pending board worker. Focused run-local review
tests check missing, altered, incomplete and duplicated review rejection.

`BUS_SKEW_SIGNOFF_PASS_NOT_BOARD_TESTED` only releases the frozen board gate.
Setup/hold/pulse-width acceptance, actual DATA clocks, CPU-oracle correctness,
resident convergence and repeated performance measurements remain distinct
requirements. No helper success is labeled a full FPGA performance result.

## Fixed Clock Configuration

The platform's Vitis 2024.1 scripts enable automatic frequency scaling for
both kernel and scalable system clocks, including `hbm_aclk`. A successful
link and a 150-MHz DATA clock alone therefore do not prove that the original
HBM frequency was retained. `scripts/check_vitis_clock_scaling.py` checks the
complete `_new_clk_freq` metadata against DATA 150 MHz, the platform's auxiliary
kernel clock 500 MHz, and HBM 450 MHz. Missing, duplicated, unknown or invalid
rows fail closed; any frequency change is a configuration mismatch. Its tests
include reduced HBM frequency while the DATA frequency is unchanged.

This is a metadata check, not timing or board acceptance. Checkpoint clock
reports, final setup/hold/pulse-width and independent bus-skew checks, xclbin
clocks and board correctness remain required. A lower-frequency result may be
retained as a different physical configuration, not substituted for the frozen
configuration without disclosure. No timing constraint is weakened by this
helper.

## Optional Post-Route Repair

`scripts/optimize_routed_checkpoint.tcl` accepts a fully routed Vivado 2024.1
checkpoint and an isolated output directory. It records pre/post timing,
route status and clocks, runs `phys_opt_design -directive ExploreWithHoldFix`,
reports bus-skew, and writes a separate candidate checkpoint. It asserts the
150/500/450-MHz platform clock periods both before and after optimization.
Existing outputs
are rejected. It does not change frequencies or constraints, overwrite the
input, or declare signoff. This is a physical implementation optimization,
not a kernel or simulator change. AMD documents the post-route operation in
[UG835, phys_opt_design](https://docs.amd.com/r/2024.1-English/ug835-vivado-tcl-commands/phys_opt_design).

The Tcl-stub tests in `tests/test_optimize_routed_checkpoint.py` check command
sequencing and rejection of unsupported versions, unrouted inputs, changed or
missing clocks, and output collisions. They are not hardware timing evidence. Any actual candidate must
still pass final setup/hold/pulse-width timing, an independent bus-skew audit,
the original DATA clock requirement and the existing board correctness gates.

The full source regression including this helper passes 102 tests on
2026-10-24 (`gr-routed-source-tests-v4`): 24.291 seconds of test execution,
273.5 MiB peak service memory, under the same 4/3-GiB, no-swap containment.
Raw logs and unchanged tracked-source hashes are retained in the campaign's
`source-regression-v4/`. This does not claim the repair has run on a checkpoint
or that routed timing or board tests have passed.

With the fixed-clock metadata checker and the before/after checkpoint-clock
guards, the full source regression passes 106 tests (`gr-routed-source-tests-v5`,
2026-10-24): 28.218 seconds of test execution, 277.6 MiB peak service memory,
the same 4/3-GiB no-swap containment, and zero OOM events. Raw logs, environment
and unchanged tracked-source hashes are retained in `source-regression-v5/`.
This remains source-level evidence, not a routed or board acceptance result.

`scripts/check_routed_timing_summary.py` separately checks the twelve-column
design timing summary: finite setup/hold/pulse-width slack, zero failing
endpoints and zero total negative slack, nonempty coverage, routed design
state and the passing Vivado 2024.1 summary. A passing caption alone cannot
override failed numeric values. It deliberately does not replace the clock,
bus-skew, constraint-coverage or board checks. The actual initial SSSP report
is rejected (WNS -0.050 ns, TNS -1.639 ns, 59 setup-failing endpoints).

The expanded source regression passes 110 tests (`gr-routed-source-tests-v6`,
2026-10-24), with raw logs and unchanged source hashes in
`source-regression-v6/`; service peak memory is 276.1 MiB under 4/3-GiB
no-swap limits. An isolated campaign worker uses the documented Vitis
`--reuse_impl` flow only after the repaired checkpoint passes this timing
check. All XO inputs, connectivity and requested frequencies remain unchanged.
Packaging must again pass the fixed-clock metadata check; no implicit HBM
downclock is accepted. See AMD's
[2024.1 checkpoint-reuse tutorial](https://docs.amd.com/r/2024.1-English/Vitis-Tutorials-Hardware-Acceleration/Reuse-the-Optimized-Checkpoint-to-Create-the-Device-Binary).
