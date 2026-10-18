# Directory And Bank-Stream Adapter Candidate

This is a default-off HLS candidate, not the adapter in the routed bitstream.
Its matching simulator and evidence owner is `spine-cycle-sim`, under
`row_line/directory_tile` in the actual-sharded-K4 adapter-optimization study.
No measured FPGA speedup or publication-level performance match is implied.

## Structure

The existing `gmem0` master remains the sole reader of row metadata and all
four PMA address regions. The reader loads up to 1024 row records per tile,
then reads bounded, sequential even/odd bank intervals. Intervals split at
the cached/external boundary. A separate join restores source/segment order;
the packet publisher emits the unchanged two eight-edge packets per segment.
No compact edge array is materialized.

Storage is explicit: directory FIFO 128 x 512 bits, even and odd bank FIFOs
128 x 512 bits each by default, with an explicit 256-line-per-bank candidate,
eight-way-banked row cache 1024 x 64 bits, loaded-segment FIFO depth 16, and a
depth-two II=1 packet publication pipeline. Bank chunks contain at most twice
the selected bank-line count. Rows must be contiguous, begin at slot zero,
and have 16-slot-aligned boundaries. PMA padding is still read and emitted.

| Source | Responsibility |
| --- | --- |
| `directory_tile.hpp` | Directory-block candidate and aligned row cache |
| `bank_stream.hpp` | Single AXI owner, finite bank streams, ordered join |
| `packet_pipeline.hpp` | Separately pipelined packet formation/publication |
| `cross_row_pipeline.hpp` | Explicit candidate selection, legacy fallback |

## Selection And Validation

Use the existing production compile path with the existing cross-row/row-line
flags plus `GRASU_REGRAPH_DIRECTORY_TILE_ROWS=1024`,
`GRASU_REGRAPH_PACKET_PIPELINE=1`, and `GRASU_REGRAPH_BANK_STREAM=1`.
The final candidate also sets `GRASU_REGRAPH_BANK_FIFO_LINES=256`; only 128
and 256 are accepted. All new selections default off. The external kernel
ABI is unchanged.

Both production packet generators accept `--adapter-policy bank-stream` with
`--pipeline-mode sharded-k4`. This selects the full row-prefetch, last-row,
empty-segment, cross-row, 1024-row directory, packet pipeline and 256-line
bank-stream flag set explicitly. Defaults remain `--adapter-policy legacy`;
legacy compile commands and connectivity have a byte-for-byte regression.
The bank-stream choice uses the existing **512-bit row-line ABI**, so board
hosts must also enable `GRASU_REGRAPH_ROW_LINE_READ=1`. The unchanged-ABI
statement above is relative to the existing cross-row/row-line candidate,
not the original 64-bit scalar-row build. Manifests record the policy and
required host row-line setting; generation is not hardware qualification.

```bash
bash scripts/check_pma_adapter_cross_row.sh \
  --out-dir /path/to/fresh-functional-check --bank-stream-wide
```

The admitted candidate passed three edge-format suites (435 fixtures each),
23 full-top AXI RTL cases, and production synthesis. Packet words, ordering,
`last`, physical PMA beat multisets, directory tail reads and backpressure
are checked. The directory/bank/join/publisher loops achieved II=1; estimated
clock 4.867 ns against 6.67 ns. Final 256-line adapter estimates: 76 BRAM18K,
16,854 FF, 39,326 LUT, zero DSP/URAM. This is not a same-resource A4 claim or a system
place-and-route result.

An earlier attempt gave two independent DATAFLOW readers the same master.
HLS rejected that multiple-owner organization. It is retained as a failed
experiment; the accepted version deliberately has one physical reader.

## Timing Boundary

The simulator retains both aggregate-return and progressive-AXI-beat modes.
Progressive mode consumes returned beats through bounded FIFOs and waits for
the final acknowledgement; it does not change the memory timing constants,
port count, outstanding credits or numerical backend. Model comparisons are
one resident synchronous weighted-SSSP round on a frozen Amazon input, not
convergence, complete GraSU+ReGraph latency, or FPGA timing calibration.

On that fixed prediction control, the final candidate takes 699,141 versus
A4's 668,278 cycles at mock latency 64, and 1,251,794 versus 1,292,225 at
latency 128. It meets the declared <=1.10x-A4 gate in both settings without
changing the original control or timing constants. The complete reproducible
matrix and independent raw recheck belong to the simulator study above;
these figures are not measured board results or a strict resource match.
