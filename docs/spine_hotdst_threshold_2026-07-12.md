# Spine Edge-File Threshold Probe

Date: 2026-07-12

## Purpose

The previous large-capacity run showed that Spine split-CU stayed in
`maintenance status=RUNNING` for a long time on
`large_hotdst_v262144_u65536`. This note narrows the failure:

- Is it caused by hot-destination fan-in?
- Is it caused by edge-file chunking across multiple batches?
- Does it appear only in the split-CU xclbin?

## Workload Generation

Generator:

```text
/home/chuxiao/grasu-regraph-integration/scripts/generate_spine_edge_threshold_workloads.py
```

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
OUT_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_hotdst_threshold_edges_20260712_205936
./scripts/generate_spine_edge_threshold_workloads.py --out-root "${OUT_ROOT}"
```

Generated edge root:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_hotdst_threshold_edges_20260712_205936
```

Cases:

| case | family | vertices | updates | final edges | batch shape |
| --- | --- | ---: | ---: | ---: | --- |
| chain_v98305_e98304 | chain | 98305 | 0 | 98304 | one batch below threshold |
| chain_v131074_e131073 | chain | 131074 | 0 | 131073 | one full batch + one edge |
| hotdst_v65536_u16384 | hot-dest | 65536 | 16384 | 81919 | one batch |
| hotdst_v98304_u32768_e131071 | hot-dest | 98304 | 32768 | 131071 | one batch just below threshold |
| hotdst_v98304_u32770_e131073 | hot-dest | 98304 | 32770 | 131073 | one full batch + one edge |
| hotdst_v131072_u32768_e163839 | hot-dest | 131072 | 32768 | 163839 | one full batch + 32767 edges |

The edge-file batch threshold is:

```text
HOST_PARTITIONED_RATIO2_MAX_SORT_N = 131072
```

## Runner Change

`run_spine_edge_file_sweep.sh` now supports:

```text
--continue-on-fail
```

This keeps the threshold sweep running after a timeout or diagnostic failure.
Default behavior is unchanged.

## Split-CU Run

This is the latest available split-CU xclbin path.

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
EDGE_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_hotdst_threshold_edges_20260712_205936
OUT_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_hotdst_threshold_split_hw_20260712_205947

SPINE_HOST=/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge \
SPINE_XCLBIN=/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
SPINE_PARTITIONED_SPLIT_VALUE=1 \
OUT_ROOT="${OUT_ROOT}" \
./scripts/run_spine_edge_file_sweep.sh \
  --chain-root "${EDGE_ROOT}" \
  --timeout 180 \
  --continue-on-fail
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_hotdst_threshold_split_hw_20260712_205947/summary.tsv
```

Results:

| case | status | wall seconds | maint ms | conv ms | errors | note |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| chain_v98305_e98304 | PASS | 3.855 | 178.361 | 1870.79 | 0 | One-batch chain passes. |
| chain_v131074_e131073 | FAIL | 185.692 | 250.504 | | | Batch 2 kept RUNNING until timeout. |
| hotdst_v65536_u16384 | PASS | 3.009 | 834.879 | 863.754 | 0 | One-batch hot destination passes. |
| hotdst_v98304_u32768_e131071 | PASS | 4.050 | 0.143064 | 1972.59 | 0 | Just-below-threshold one-batch hot destination passes. |
| hotdst_v98304_u32770_e131073 | FAIL | 2.890 | 0.129754 | | | Batch 2 persisted 0; expected persisted 131073. |
| hotdst_v131072_u32768_e163839 | FAIL | 2.940 | 0.145384 | | | Batch 2 persisted 0; expected persisted 163839. |

Key log lines:

```text
chain_v131074_e131073:
  PARTITIONED_CSR_E2E_BATCH ... batch=1 input_edges=131072 ... maint_ms=250.504
  [part-e2e] maintenance status=RUNNING elapsed_s=160
  exit_code 124

hotdst_v98304_u32770_e131073:
  PARTITIONED_CSR_E2E_BATCH ... batch=1 input_edges=131072 ... persisted=131072
  maintenance diagnostic mismatch batch=2 overflow=0 target=0 expected_target=1
  consumed=0 expected_consumed=1 persisted=0 expected_persisted=131073

hotdst_v131072_u32768_e163839:
  PARTITIONED_CSR_E2E_BATCH ... batch=1 input_edges=131072 ... persisted=131072
  maintenance diagnostic mismatch batch=2 overflow=0 target=0 expected_target=1
  consumed=0 expected_consumed=1 persisted=0 expected_persisted=163839
```

Interpretation:

```text
The threshold is sharply tied to crossing the first 131072-edge batch.
One-batch edge files pass, including hot-destination inputs. Once a second
batch is introduced, the current edge-file path either times out in maintenance
or fails the level-carry diagnostic.

Therefore the observed large_hotdst problem is not purely caused by a
hot-destination reduction hotspot. It is primarily a multi-batch / level-carry
problem in the current Spine edge-file path.
```

## Single-CU Auxiliary Run

The matching single-CU xclbin was also tested on the same threshold files to
check whether the behavior was purely split-CU-specific.

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
EDGE_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_hotdst_threshold_edges_20260712_205936
OUT_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_hotdst_threshold_single_hw_20260712_210400

SPINE_HOST=/home/chuxiao/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke \
SPINE_XCLBIN=/home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/xclbin/spine_partitioned_e2e.hw.xclbin \
SPINE_PARTITIONED_SPLIT_VALUE=0 \
OUT_ROOT="${OUT_ROOT}" \
./scripts/run_spine_edge_file_sweep.sh \
  --chain-root "${EDGE_ROOT}" \
  --timeout 180 \
  --continue-on-fail
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_hotdst_threshold_single_hw_20260712_210400/summary.tsv
```

Auxiliary observations:

```text
chain_v131074_e131073 also timed out in batch 2 maintenance.
hotdst_v65536_u16384 passed.
Some larger one-batch cases reported checker errors with this older single-CU
xclbin/host combination, so the single-CU run should not be used as the final
latest-Spine threshold claim.
```

Useful conclusion from the single-CU run:

```text
The batch-2 running issue is not introduced solely by splitting maintenance and
compute into two CUs; it also appears on the matching single-CU path for the
two-batch chain input.
```

## Current Conclusion

```text
1. ReGraph+GraSU large capacity cases now pass full verification on the
   existing combined xclbin after the ReGraph host verification fix.
2. Spine's latest split-CU edge-file path is reliable for one-batch inputs up
   to 131071 edges in this threshold scan.
3. Spine's edge-file path becomes unreliable immediately after crossing the
   131072-edge batch boundary:
   - pure chain with one extra edge times out in batch 2 maintenance;
   - hot-destination with one extra edge fails level-carry diagnostics.
4. The next Spine optimization/debug target is the multi-batch level-carry
   path, not hot-destination reduction alone.
```

## Next Steps

```text
1. Inspect host/kernel expectations around expected_target=1 vs target_level=0
   for batch 2 in edge-file mode.
2. Add a smaller software-only or hw_emu reproducer if available, so the
   multi-batch level-carry issue can be debugged without repeated real-hw
   timeout runs.
3. For final performance comparison tables, mark Spine multi-batch edge-file
   results as invalid until this carry path is fixed; use one-batch cases for
   strict same-edge timing claims.
```
