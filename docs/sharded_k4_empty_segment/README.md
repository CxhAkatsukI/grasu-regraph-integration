# Sharded-K4 Empty-Segment Candidate

The default-off `GRASU_REGRAPH_SKIP_EMPTY_SEGMENT=1` flag avoids starting
`emit_row_segments` when its rounded segment range is empty. It is a
follow-up to the row-prefetch and stop-after-last adapter optimization, not a
replacement for the previous routed bitstream or its measured results.

The candidate keeps that helper non-inlined so HLS can bypass its start.
A caller-side `continue` alone did not improve RTL cycles; the explicit
helper boundary did. With the flag off, the helper is inlined and all thirteen
paired baseline RTL latencies remain identical to the earlier implementation.
Kernel arguments, shared AXI interfaces and packet fields are unchanged.

The segment-range guard intentionally preserves the legacy treatment of
unaligned empty rows and allocated all-dummy/source-zero reservation segments.
It introduces no host-created sparse-source index or omitted update work.

## Gates And Reproduction

```bash
bash scripts/check_pma_to_regraph_adapter.sh --out-dir results/fresh_empty_segment_check
```

All six legacy C++ configurations and six candidate format/flag combinations
pass. The latter each cover 254 scenarios and 1,482 exact packets. Test-only
`PMA_COSIM_SKIP_EMPTY=0|1` controls the paired RTL Tcl runner; it is distinct
from the production HLS compiler define. Do not define
`GRASU_REGRAPH_COSIM_DEPTH` when compiling a production XO.

The simulator repository owns the bounded runners and portable raw evidence:
`docs/experiments/comparisons/grasu_regraph_stage_validation/actual_sharded_k4/adapter_optimization/empty_segment/`.
It retains both historical controls, complete C/RTL packet checks, source
snapshots, generated Verilog, effective flags, part/clock and resource records.

At requested 150 MHz on U55C, the 1,025-source last-only RTL control changes
from 89,878 to 14,230 cycles. The first-only control stays at 297 cycles.
HLS estimates change from 17,202 to 17,473 LUTs and 12,183 to 12,314 FFs;
BRAM remains 15, with no DSP or URAM. These are local co-simulation and
synthesis results, **not routed or measured FPGA speedups**.

## Still Open

Production XO/ABI checks, route timing/connectivity admission, alternating
old/new resident FPGA tests and explicit-version simulator synchronization
must precede any whole-path claim. The new flag has not been enabled in the
previously measured production bitstream. Original-A4 comparison and
publication-performance matching remain separate goals.
