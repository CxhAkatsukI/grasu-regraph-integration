# Cross-Row Pipeline Candidate

The default-off `GRASU_REGRAPH_CROSS_ROW_PIPELINE=1` path requires whole-line
rows, stop-after-last and skip-empty. It does not replace any routed adapter.
The simulator's passive occupied-row RTL study motivated this change; that
study did not establish a board-level performance penalty or isolate stalls.

`kernels/pma_to_regraph_adapter/cross_row_pipeline.hpp` owns two dataflow
stages: a single directory/PMA memory reader and ordered packet publication,
connected by one finite FIFO of depth 16. Within each cached eight-source
directory line, flattened traversal allows PMA load requests to overlap
across occupied source rows rather than restarting a memory-reading helper
for each row. Directory-line transitions still drain the inner pipeline;
there is no claim of overlap across those transitions. No sparse-source index, extra external
memory port, compacted edge copy or reordered packet stream is introduced.

One terminal record closes all stages, including empty input. Source bounds,
PMA bank selection, slot masking, weights/destination format, dummy bits and
the historical cumulative-slot `last` rule remain unchanged. Whole-line row
padding is still mandatory. The host and control/AXIS ABI are unchanged.
Legacy HLS code remains behind the default-off branch; its previous evidence
must not be silently reassigned to this candidate.

Run the format/packet-equivalence checks from this repository:

```bash
bash scripts/check_pma_adapter_cross_row.sh --out-dir /data/chuxiao/experiments/fresh_cross_row
```

These CPU checks use unbounded software HLS streams; they are not proof of
finite-FIFO liveness or speed. Production synthesis, exact external ABI and
full-top RTL with response latency/backpressure must pass separately. The
simulator repository owns bounded execution and raw evidence packaging.
Routing, resident FPGA measurements, simulator synchronization and the final
original-A4 comparison remain open until explicitly admitted.

The first three-stage development attempt failed production synthesis:
Vitis rejects multiple reading processes on the shared `gmem0` bundle.
Its frozen sources and tool logs are retained by the simulator study. The
two-stage design keeps all external reads in one process; it does not add
another AXI master to avoid that constraint.

## Admitted Synthesis And RTL Checkpoint

Successful attempt-v2 is XO SHA-256
`053a2b27a8a5f84ef05e05c779d23c9add6b313d7c3f4c511cb1a5f547f27504`.
The simulator study's `row_line/cross_row/` folder retains the complete
twelve-case matrix and portable raw archive, including the failed attempt.
All packets and PMA/directory traffic match; all original whole-line reference
handshakes replay exactly. The three C++ formats each pass 254 cases/1,482
packets. Weighted production RTL passes response-latency and sink-stall checks.

Dense 17-source tests improve from 1735 to 588 clocks at synthetic L=64,
and from 3079 to 1036 at L=128. Maximum outstanding rises from 1 to 8.
V2's last-only test regresses from 439 to 564 clocks; this regression remains
in its frozen archive. V3 bypasses wholly empty cached blocks before entering
the inner pipeline, reducing that case to 402 clocks. The other eleven rows,
including complete traffic and start-relative timestamps, remain equal to v2. The check uses
segment bounds, not just nonempty slot intervals, to retain historical
masking semantics for unaligned intervals. No sparse-source index is added.
Do not infer real-HBM speedup from these ordered-memory tests.

The production read loop achieves II=1/depth=74; the publisher half loop II=1/depth=2.
At requested 150 MHz, estimates are 30,466 LUT, 12,850 FF, 15 BRAM_18K,
no DSP/URAM and 4.867 ns. LUT usage is approximately twice the whole-line
reference. No route or board timing is admitted for this candidate.

The current v3 XO is SHA-256
`7d1785677ca7b54861688d7670d813ca2a4cfdc1e2c83cbc53151cd03ad02b6b`.
It passes the same C++, ABI, reference-replay and complete RTL gates, with
31,913 LUT, 13,726 FF, 15 BRAM_18K, no DSP/URAM and estimated 4.867 ns.
The additional bypass logic is not resource-free. The simulator handoff keeps
v3 in `row_line/cross_row/evidence_v3/` without rewriting `evidence/` (v2).
