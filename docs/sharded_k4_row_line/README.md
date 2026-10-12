# Whole-Line Row Directory Candidate

This is a default-off follow-up to
[the empty-segment candidate](../sharded_k4_empty_segment/README.md).
`GRASU_REGRAPH_ROW_LINE_READ=1` requires `GRASU_REGRAPH_ROW_PREFETCH=1`.
`kernels/pma_to_regraph_adapter/row_line.hpp` reads one explicit 512-bit
word and unpacks eight existing 64-bit directory entries. The final-row
extent read is still charged separately. No sparse-source index is added.

## Host Contract

The external XO kernel/control/stream ABI is unchanged, but the HLS row
pointer is now 512-bit. The matching native host **must** be built with
`--row-line-read`, which enables `GRASU_REGRAPH_HOST_ROW_LINE_READ=1`.
Runtime planning and packing preserve V+1 logical row entries and zero-pad
to a complete 64-byte line. BO placement remains 4-KiB aligned. GraSU update
kernels still see the same 64-bit entries and sentinel. Do not pair a wide
XO with an unpadded host based only on external ABI equality.

```bash
bash scripts/build_weighted_pma_native_host.sh \
  --pipeline-mode sharded-k4 --algorithm weighted_sssp \
  --row-line-read --out-dir results/fresh_row_line_host

OUT_DIR="$PWD/results/fresh_row_line_check" \
  bash scripts/check_sharded_k4_native_host.sh --row-line-read

bash scripts/check_pma_to_regraph_adapter.sh \
  --out-dir results/fresh_row_line_packets
```

The adapter source checker tests six legacy configurations and nine
candidate format/flag matrices. Every candidate matrix preserves all 1,482
packets in 254 scenarios. `tests/weighted_pma_row_line_plan_test.cpp` covers
eleven directory sizes, including partial 8-entry tails and the 4-KiB
boundary, unchanged PMA/update/state buffers and truncation rejection.

## Evidence And Limits

The simulator repository owns the bounded study and portable evidence at
`docs/experiments/comparisons/grasu_regraph_stage_validation/actual_sharded_k4/adapter_optimization/row_line/`.
Its guide records exact production XO identities, full-top AXI transcripts,
source snapshots and reproducible commands. Four-algorithm default/wide
six-partition host preparation outputs match byte-for-byte.

Production synthesis at requested 150 MHz passes and the complete external
ABI matches the skip-empty XO. In the 17-source dense RTL test, directory
requests fall from 18 to 4 (1152 to 256 bytes), but cycles only change from
1755 to 1735. Do not interpret traffic reduction as proportional FPGA
speedup. Synthetic ordered-memory RTL is not a board or HBM timing result.

No new route or FPGA measurement is admitted. The previously measured
bitstream, production simulator and paper figures are not replaced. Next
gates are route/connectivity timing, padded-host board equivalence, explicit
simulator-version synchronization and the separately matched original-A4
versus actual adapter+K4 comparison. The separate default-off
[cross-row pipeline candidate](CROSS_ROW.md) tests overlap within cached
directory lines; it retains the same host-padding and external ABI contract.
