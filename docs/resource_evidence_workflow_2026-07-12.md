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

ReGraph old-source `hw` build in progress:

```bash
./scripts/collect_vitis_evidence.py \
  --label regraph_sssp_hw_oldsource_inprogress \
  --build-root /home/chuxiao/ReGraph_sssp_hw_scratch \
  --out-dir "$BASE/regraph_sssp_hw_oldsource_inprogress" \
  --artifact /home/chuxiao/ReGraph_sssp_hw_scratch/host_graph_fpga_sssp \
  --note 'In-progress old-source ReGraph hw build; useful only for compile/resource monitoring, not fixed SSSP correctness.'
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

ReGraph old-source `hw` in-progress placed resources:

```text
LUT        55479
LUTAsMem    9964
REG        92137
BRAM         120
URAM         128
DSP            0
```

Important caveat: `/home/chuxiao/ReGraph_sssp_hw_scratch` is still the
pre-fix/old-source build scratch. It is useful for resource monitoring only. It
does not prove the fixed weighted SSSP hardware implementation.

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
