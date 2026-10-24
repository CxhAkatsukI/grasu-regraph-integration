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
