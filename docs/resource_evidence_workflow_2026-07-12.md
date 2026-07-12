# Resource Evidence Workflow, 2026-07-12

This note records how we now collect hardware evidence for GraSU, ReGraph, and
the future combined GraSU+ReGraph build.

The goal is to make the resource question reviewable:

```text
Did any GraSU/ReGraph component change its CU count, HBM/SLR binding, or
LUT/REG/BRAM/URAM/DSP usage after integration?
```

## Scripts Added

```text
scripts/collect_vitis_evidence.py
scripts/compare_vitis_resources.py
```

`collect_vitis_evidence.py` scans a Vitis/Vivado build tree and writes:

```text
artifacts.tsv              host/xclbin path, size, sha256
link_kernels.tsv           kernel names, CU counts, CU names
connectivity.tsv           nk/sp/slr/stream_connect records from link summaries
system_estimate_meta.tsv   design name, target device, target clock
system_estimate_kernels.tsv
hls_area.tsv               FF/LUT/BRAM/URAM/DSP from system estimates
accelerator_util.tsv       placed/routed kernel_util resources when available
slr_util.tsv               SLR-level utilization when available
timing.tsv                 WNS/TNS/WHS/THS when available
summary.md                 compact human-readable summary
copied_reports/            copied report evidence
```

By default it ignores archived report directories under the build root:

```text
evidence/
.tmp_doc/
phase6_results/
__pycache__/
```

This matters for ReGraph scratch trees, which may contain old copied evidence.

`compare_vitis_resources.py` compares two evidence bundles and writes delta
tables:

```text
accelerator_util_delta.tsv
hls_top_area_delta.tsv
kernel_cu_delta.tsv
summary.md
```

## Commands Run

Current evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_011611
```

The `results/` directory is intentionally git-ignored, so regenerate evidence
with these commands when needed.

GraSU standalone U55C `hw`:

```bash
cd /home/chuxiao/grasu-regraph-integration
BASE=results/resource_evidence_$(date +%Y%m%d_%H%M%S)
mkdir -p "$BASE"

./scripts/collect_vitis_evidence.py \
  --label grasu_hw_u55c \
  --build-root /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw \
  --out-dir "$BASE/grasu_hw" \
  --artifact /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c \
  --note 'GraSU standalone U55C hw build completed on 2026-07-09.'
```

ReGraph weighted SSSP fixed-source `hw_emu`:

```bash
./scripts/collect_vitis_evidence.py \
  --label regraph_sssp_hw_emu_fixed \
  --build-root /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch \
  --out-dir "$BASE/regraph_sssp_hw_emu_fixed" \
  --artifact /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/host_graph_fpga_sssp \
  --note 'ReGraph weighted SSSP fixed-source hw_emu build; tiny weighted SSSP passed.'
```

ReGraph old-source `hw` complete build, resource/timing only:

```bash
./scripts/collect_vitis_evidence.py \
  --label regraph_sssp_hw_oldsource_complete \
  --build-root /home/chuxiao/ReGraph_sssp_hw_scratch \
  --out-dir "$BASE/regraph_sssp_hw_oldsource_complete" \
  --artifact /home/chuxiao/ReGraph_sssp_hw_scratch/host_graph_fpga_sssp \
  --note 'Old-source ReGraph hw build completed; useful only for compile/resource monitoring, not fixed SSSP correctness.'
```

Self-check for the compare script:

```bash
./scripts/compare_vitis_resources.py \
  --label grasu_hw_self_check \
  --before "$BASE/grasu_hw" \
  --after "$BASE/grasu_hw" \
  --out-dir "$BASE/compare_grasu_self_check"
```

Expected self-check result:

```text
accelerator_util changes: 0
hls_top_area changes: 0
kernel CU count changes: 0
```

## Current Baseline Evidence

GraSU `hw` artifact hashes:

```text
host:
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c
  sha256 9fb21cc3000f9d3219e194d7cdf6df7fd8a5a592c65e2767247fd0b8af43d34a

xclbin:
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build/GraSU_u55c_hbm.hw.xclbin
  sha256 66ce4ab566fe78c4fafdc3c6798a41394c0d7d56ae17fdc5f599d60fa61469d9
```

GraSU CU structure:

```text
bin_search:    4 CUs
dispatch:      1 CU
process_cache: 2 CUs
process_ddr:   2 CUs
```

GraSU routed kernel utilization, `Used Resources`:

```text
LUT       244390
LUTAsMem    7000
REG       178172
BRAM         104
URAM         512
DSP            0
```

GraSU routed timing:

```text
WNS 0.003 ns
TNS 0.000 ns
WHS 0.009 ns
THS 0.000 ns
```

GraSU routed SLR pressure:

```text
CLB LUTs:      SLR0 145265, SLR1 92890,  SLR2 164391
CLB Registers: SLR0 161613, SLR1 142463, SLR2 159524
Block RAM:     SLR0 78.5,   SLR1 124,    SLR2 102.5
URAM:          SLR0 256,    SLR1 0,      SLR2 256
```

ReGraph fixed-source `hw_emu` artifact hashes:

```text
host:
  /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/host_graph_fpga_sssp
  sha256 15db9e29a1cb9dc6ebc572c96214e390d331be1996ba1635145bbb0261f39032

xclbin:
  /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/xclbin_hw_emu_sssp/graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
  sha256 e0068aabae0e2547117abd37d291d4ff561be4f2c0591ce994d80d7a3332347f
```

ReGraph fixed-source `hw_emu` CU structure:

```text
kernelApply:                1 CU
kernelHBMWrapper:           1 CU
littleKernelScatterGather:  1 CU
kernelLittleGSMerger:       1 CU
bigKernelScatterGather:     1 CU
kernelBigGSMerger:          1 CU
```

ReGraph fixed-source `hw_emu` does not provide placed/routed utilization,
because it is not a real `hw` implementation. Its current evidence is HLS/system
estimate plus the successful tiny weighted SSSP `hw_emu` run.

Latest fixed-source `hw_emu` functional recheck evidence:

```text
/home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_emu_check_20260712_025255/run_tiny_weighted_sssp_hw_emu_after_cache_backup.log
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_030037_regraph_sssp_hwemu_usercheck/regraph_sssp_hw_emu_fixed_usercheck
```

The recheck programmed the `hw_emu` device, ran source vertex 0 for 4
supersteps on `tiny-weighted-sssp.txt`, and finished with:

```text
Device[0]: program successful!
Supersteps: 4
Processed edges: 8; Graph edges: 5
All the simulator processes exited successfully
```

Spine real `hw` baseline evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_023103_spine_hw_fixedcollector/spine_split_e2e_hw
```

Spine xclbin:

```text
/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin
sha256 69145517738cc1ffff95e91c24393260c346ac683db9eef2989bbc1bdb7a3469
```

Spine smoke:

```text
PARTITIONED_CSR_E2E_HOT_COLD PASS ... maint_ms=0.357061 conv_ms=9.60089 errors=0
```

Spine routed kernel utilization, `Used Resources`:

```text
LUT       160300
LUTAsMem   11445
REG       185396
BRAM          77
URAM          16
DSP           57
```

Spine routed timing:

```text
WNS -0.851 ns
TNS -2468.856 ns
WHS  0.004 ns
THS  0.000 ns
```

Important caveat: the Spine xclbin exists and the smoke test passed, but the
selected post-route timing report still has negative WNS/TNS. Keep this visible
when using it as a comparison baseline.

ReGraph old-source `hw` resource-monitoring evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_024815_regraph_oldsource_routed/regraph_sssp_hw_oldsource_routed
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_030317_regraph_oldsource_hw_complete/regraph_sssp_hw_oldsource_complete
```

The first evidence bundle was collected after the old-source build reached
routed reports on 2026-07-12. It still had no final xclbin at collection time:

```text
xclbins: 0
```

The later evidence bundle includes the completed old-source xclbin:

```text
/home/chuxiao/ReGraph_sssp_hw_scratch/xclbin_hw_sssp/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
sha256 0f8e9f786b35c951b76b33f9ecac30b25ef888823a99de21be50a7e58f98b76d
```

Use this only for resource/timing monitoring. It does not prove the fixed
weighted SSSP hardware implementation because the scratch predates the gather
URAM initialization fix.

ReGraph old-source routed kernel utilization, `Used Resources`:

```text
LUT        55479
LUTAsMem    9964
REG        92137
BRAM         120
URAM         128
DSP            0
```

ReGraph old-source routed timing:

```text
WNS 0.003 ns
TNS 0.000 ns
WHS 0.009 ns
THS 0.000 ns
```

Important caveat: `/home/chuxiao/ReGraph_sssp_hw_scratch` is still the
pre-fix/old-source build scratch. It is useful for resource monitoring only. It
does not prove the fixed weighted SSSP hardware implementation.

ReGraph fixed-source real `hw` failed-build evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_083525_regraph_fixed_hw_failed/regraph_sssp_hw_fixed_failed
```

This build root was:

```text
/home/chuxiao/ReGraph_sssp_hw_fixed_scratch
```

It reached routed/post-route reports but did not emit a final real-hardware
xclbin or host executable:

```text
xclbins: 0
host_graph_fpga_sssp: missing
```

Selected failure reports and logs copied into the evidence bundle:

```text
build_hw.log
v++.log
vivado.log
impl_1_runme.log
hs_err_pid27009.log
```

Failure summary:

```text
VPL failed run: impl_1
CrashLog: hs_err_pid27009.log
Timing: WNS=-1.160 ns, TNS=-9465.562 ns, WHS=0.008 ns, THS=0.000 ns
Routed Used Resources: LUT=55886, LUTAsMem=9964, REG=93490, BRAM=120, URAM=128, DSP=0
```

Do not use this fixed-source failed build as the final ReGraph `hw` baseline.
It is useful for debugging timing/resource pressure only. The next valid
resource baseline needs a fixed-source `hw` build that emits a real xclbin.

## How To Use For The Combined Build

After a combined GraSU+ReGraph xclbin is produced:

```bash
./scripts/collect_vitis_evidence.py \
  --label grasu_regraph_combined_hw \
  --build-root /path/to/combined/build/root \
  --out-dir "$BASE/combined_hw" \
  --artifact /path/to/combined/host \
  --note 'Combined GraSU + ReGraph hardware build.'
```

Then compare component resources:

```bash
./scripts/compare_vitis_resources.py \
  --label grasu_baseline_vs_combined \
  --before "$BASE/grasu_hw" \
  --after "$BASE/combined_hw" \
  --out-dir "$BASE/compare_grasu_vs_combined"

./scripts/compare_vitis_resources.py \
  --label regraph_baseline_vs_combined \
  --before "$BASE/regraph_sssp_hw_fixed" \
  --after "$BASE/combined_hw" \
  --out-dir "$BASE/compare_regraph_vs_combined"
```

Here `$BASE/regraph_sssp_hw_fixed` is a placeholder for the future fixed-source
real `hw` ReGraph evidence bundle. The current fixed-source proof is `hw_emu`;
it is not enough for final post-route resource comparison.

Every non-zero delta should be reviewed before we use the build in performance
claims. Some differences may be expected from floorplanning or stream wiring,
but they need to be recorded explicitly.

## Combined hw_emu Evidence Update

The first host-compatible combined `hw_emu` xclbin evidence is:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_022520_combined_hwemu_host_compatible
```

Build root:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible
```

Combined xclbin:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin
sha256 daf8bb44c32295a27827993bdf913eb9d311f27e4d21efbaf46edfc57224995f
```

CU structure:

```text
GraSU:
  bin_search:    4
  dispatch:      1
  process_cache: 2
  process_ddr:   2

ReGraph:
  kernelApply:                1
  kernelHBMWrapper:           1
  littleKernelScatterGather:  1
  kernelLittleGSMerger:       1
  bigKernelScatterGather:     1
  kernelBigGSMerger:          1
```

The same-component `hw_emu` comparison showed:

```text
GraSU baseline vs combined:
  hls_top_area same-component changes: 0
  kernel CU count same-kernel changes: 0

ReGraph baseline vs combined:
  hls_top_area same-component changes: 0
  kernel CU count same-kernel changes: 0
```

This is not a routed-resource result. It proves link structure and HLS-level
component preservation only. The final resource answer still needs fixed-source
ReGraph real `hw`, then a combined real `hw` link, then routed reports.
