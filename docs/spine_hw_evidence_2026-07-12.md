# Spine Real-hw Evidence, 2026-07-12

This note records the current Spine real `hw` baseline that we can use while
building the GraSU+ReGraph comparison.

## Build

Build root:

```text
/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100
```

Main output:

```text
/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin
sha256 69145517738cc1ffff95e91c24393260c346ac683db9eef2989bbc1bdb7a3469
```

Build log result:

```text
=== SPLIT HW BUILD COMPLETE ===
end: Sun Jul 12 02:26:39 CST 2026
elapsed: 5h08m10s
```

## Smoke Test

Smoke log:

```text
/tmp/split_hw133_hot_cold_smoke.log
```

Key result:

```text
PARTITIONED_CSR_E2E_HOT_COLD PASS ... maint_ms=0.357061 conv_ms=9.60089 errors=0
```

The xclbin was produced and the board smoke test passed.

## Resource Evidence

Evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_023103_spine_hw_fixedcollector/spine_split_e2e_hw
```

Collection command:

```bash
cd /home/chuxiao/grasu-regraph-integration
BASE=/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_023103_spine_hw_fixedcollector

./scripts/collect_vitis_evidence.py \
  --label spine_split_e2e_hw_150_depth32_bram \
  --build-root /data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100 \
  --out-dir "$BASE/spine_split_e2e_hw" \
  --artifact /home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke \
  --note 'Spine partitioned split e2e U55C real hw build at 150 MHz, MAX_N=16777216, VS_PARTITION_SIZE=1048576, depth32 bram.'
```

Routed kernel utilization, `Used Resources`:

```text
LUT       160300
LUTAsMem   11445
REG       185396
BRAM          77
URAM          16
DSP           57
```

Routed CU resources:

```text
spine_partconv_compute_kernel_1: LUT 6458,   LUTAsMem 1370,  REG 7746,   BRAM 36, URAM 16, DSP 0
spine_partconv_rdmaint_kernel_1: LUT 153842, LUTAsMem 10075, REG 177650, BRAM 41, URAM 0,  DSP 57
```

Routed SLR pressure:

```text
CLB LUTs:      SLR0 222980, SLR1 70202,  SLR2 25401
CLB Registers: SLR0 304426, SLR1 91571,  SLR2 35169
Block RAM:     SLR0 101,    SLR1 126.5,  SLR2 50
URAM:          SLR0 0,      SLR1 16,     SLR2 0
DSPs:          SLR0 57,     SLR1 0,      SLR2 4
```

Timing from the selected post-route physopt report:

```text
WNS -0.851 ns
TNS -2468.856 ns
WHS  0.004 ns
THS  0.000 ns
```

Important caveat: this is a produced xclbin with a passing smoke test, but the
timing report still has negative WNS/TNS. Treat it as a useful performance and
functionality baseline, not as a fully timing-closed build.

## Evidence Collector Fix

During this collection, `collect_vitis_evidence.py` was updated to recognize
Vivado-copied report names such as:

```text
impl_1_kernel_util_routed.rpt
impl_1_slr_util_routed.rpt
impl_1_hw_bb_locked_timing_summary_postroute_physopted.rpt
```

The previous matcher only recognized exact names like
`kernel_util_routed.rpt`, so it missed the Spine routed utilization reports.
