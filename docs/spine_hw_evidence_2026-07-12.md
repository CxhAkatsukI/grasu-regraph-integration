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

## Later Split-CU Build Monitor, 2026-07-12 21:39 CST

Evidence snapshot:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_hw_monitor_20260712_2139
```

### 200 MHz Retry

Build root:

```text
/data/feiyang/spine-dynamic-graph/target/split_e2e_hw_200
```

The retry generated both kernel object files but did not generate the final
hardware xclbin:

```text
/data/feiyang/spine-dynamic-graph/target/split_e2e_hw_200/xclbin/spine_partconv_rdmaint_kernel.hw.xo
/data/feiyang/spine-dynamic-graph/target/split_e2e_hw_200/xclbin/spine_partconv_compute_kernel.hw.xo
missing: /data/feiyang/spine-dynamic-graph/target/split_e2e_hw_200/xclbin/spine_partitioned_split_e2e.hw.xclbin
```

Failure evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_hw_monitor_20260712_2139/split_e2e_hw_200/v++_spine_partitioned_split_e2e.hw.log
/home/chuxiao/grasu-regraph-integration/results/spine_hw_monitor_20260712_2139/split_e2e_hw_200/link.steps.log
/home/chuxiao/grasu-regraph-integration/results/spine_hw_monitor_20260712_2139/split_e2e_hw_200/impl_1_runme.log
```

Key log lines:

```text
[21:35:47] Run vpl: FINISHED. Run Status: impl ERROR
ERROR: [VPL 18-1000] Routing results verification failed due to partially-conflicted nets
ERROR: [VPL 12-13638] Failed runs(s) : 'impl_1'
ERROR: [v++ 60-661] v++ link run 'run_link' failed
```

The implementation log reports a legal-routing failure:

```text
CRITICAL WARNING: [Route 35-2] Design is not legally routed. There are 18816 node overlaps.
ERROR: [Constraints 18-1000] Routing results verification failed due to partially-conflicted nets
route_design failed
```

Interpretation: this 200 MHz retry is not stuck and is not a host/runtime
crash. It reached Vivado implementation and failed during route verification.
The conflicted nets are inside `spine_partconv_rdmaint_kernel_1`, including
`gmem_p2_m_axi` and `gmem_meta_m_axi` paths, so the next useful action is
physical-closure/placement/routing relief rather than changing the benchmark
host.

Note: an earlier 200 MHz attempt in
`/data/feiyang/spine-dynamic-graph/target/split_e2e_hw_200_build.log` failed
at block-design creation with:

```text
You have run out of port connections on /hmss_0. All 33 connections are used
```

That older failure involved the pre-split/three-kernel connectivity. The later
retry progressed further with the current two-kernel split link, so the current
authoritative 200 MHz blocker is the route-verification failure above.

### 150 MHz Retry

Build root:

```text
/data/feiyang/spine-dynamic-graph/target/split_e2e_hw_150
```

Monitor command:

```bash
ps -eo pid,ppid,stat,etime,%cpu,%mem,cmd | rg -n "spine_partitioned_split_e2e|v\\+\\+|vivado|runme|hw_150"
tail -n 120 /data/feiyang/spine-dynamic-graph/target/split_e2e_hw_150/logs/v++_spine_partitioned_split_e2e.hw.log
```

Status at `2026-07-12 21:39:11 CST`:

```text
v++ link process is still active.
Vivado block-level synthesis is active.
No final xclbin exists yet.
Latest progress: Block-level synthesis in progress, 210 of 211 jobs complete, 1 job running.
```

Important active process:

```text
vivado -log ulp_spine_partconv_rdmaint_kernel_1_0.vds ... ulp_spine_partconv_rdmaint_kernel_1_0.tcl
```

Interpretation: the 150 MHz retry is slow but still alive. The log timestamp is
advancing and the Vivado synthesis process is consuming CPU and memory. It is
too early to classify it as failed or stuck.

Follow-up at `2026-07-12 21:42:19 CST`:

```text
The top-level v++ log still reports 210 of 211 synthesis jobs complete.
The remaining job is ulp_spine_partconv_rdmaint_kernel_1_0_synth_1.
That job's runme.log and .vds files were still updating at 21:42.
The child Vivado log had reached XDC/netlist preparation with peak memory near 96.8 GB.
```

Additional child-log snapshots:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_hw_monitor_20260712_2139/split_e2e_hw_150/rdmaint_synth_runme_2142.log
/home/chuxiao/grasu-regraph-integration/results/spine_hw_monitor_20260712_2139/split_e2e_hw_150/rdmaint_synth_vds_2142.log
```

This supports the current classification as "slow active synthesis" rather
than a confirmed deadlock.
