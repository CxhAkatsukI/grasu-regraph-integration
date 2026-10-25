# Explicit Initial Residency For Sharded K4

The SSSP/CC and separate PageRank production hosts accept the environment
variable `GRASU_SHARDED_PREMIGRATE_INPUTS=0|1`. Default is now on; values other
than 0/1 are rejected. Both hosts use the same residency helper. Residency
alone does not change HLS, scheduling or bitstreams. The separate
[bounded-cache study](sharded_k4_cache_extent/README.md) changes the cache ABI
and requires fresh hardware; do not conflate the two changes.

When enabled, the host explicitly migrates ten initial BOs per destination
shard (four update, four PMA, row table and binary-source table) and waits
before applying any GraSU updates. It prints:

```text
SHARDED_INPUT_RESIDENCY policy=premigrate buffers=... bytes=... wall_ms=... event_ms=... boundary=initial_setup_before_updates
```

This is initial graph/input setup, not free work or a per-batch graph copy.
It deliberately precedes updates: migrating a stale host PMA afterward can
overwrite the modified device state. State/source setup continues through
the existing host path.

The change addresses an observed XRT 2.18.179 behavior: `enqueueWriteBuffer`
and queue completion need not make a previously nonresident input BO
device-resident. A later kernel argument can trigger an implicit transfer.
Explicit initial migration establishes residency. Official sources:
[device write/migrate](https://raw.githubusercontent.com/Xilinx/XRT/2024.2/src/runtime_src/xocl/core/device.cpp)
and [enqueue migration](https://raw.githubusercontent.com/Xilinx/XRT/2024.2/src/runtime_src/xocl/api/enqueue.cpp).

## Evidence And Limits

The simulator repository owns the portable evidence and experiment runners:
`docs/experiments/comparisons/grasu_regraph_stage_validation/actual_sharded_k4/model_sync/sst/input_residency/`.
It retains a frozen-host control, new-host option-off/on controls, diagnostic
XRT traces and the complete original/optimized AU/SU/WK matrix. Thirty runs
pass exact complete-output and round checks. For optimized WK, the median
compute span changes from 96.933 ms (new host/off) to 64.268 ms (on), while
the separate initial migration costs 51.326 ms. Six fixed, unfitted v4 model
predictions differ nominally from resident FPGA medians by -6.40% to +1.69%.
This is not a setup-inclusive speedup or exclusive-stage calibration.

The following historical residency study predates default-on and PageRank
support. SSSP build and FPGA correctness/timing were tested. CC shares this source;
its [compile-only check](evidence/sharded_k4_input_residency/cc_compile.json)
is separate and does not admit CC board timing. PR behavior, other workloads
and matching original ReGraph A4 were unverified by that study. Current
validation is reported in the bounded-cache guide.
Keep original and option-off measurements; do not retroactively relabel them
as already-resident compute.

```bash
bash scripts/build_weighted_pma_native_host.sh \
  --pipeline-mode sharded-k4 --algorithm weighted_sssp --out-dir results/fresh_host
# Apply this option to an otherwise matched board command:
# GRASU_SHARDED_PREMIGRATE_INPUTS=1 bash scripts/run_pma_native_hw.sh ...
```

The host migration is outside its measured update/compute interval and has
its own wall/event record. Include the recorded initialization in any
whole-startup claim. Compare resident execution only after both systems'
initial graph/state loading has genuinely completed.
