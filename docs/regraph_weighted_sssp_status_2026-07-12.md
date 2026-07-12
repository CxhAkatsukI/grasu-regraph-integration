# ReGraph Weighted SSSP Status

Date: 2026-07-12

## Current Scope

This note records the local ReGraph weighted SSSP bring-up status that feeds the
GraSU + ReGraph comparison plan.

ReGraph source tree:

```text
/home/chuxiao/ReGraph
```

Important caveat:

```text
/home/chuxiao/ReGraph is not currently a git repository.
```

Therefore, review evidence is stored in the ReGraph `.tmp_doc` directory and the
latest gather cold-start initialization patch is mirrored in this integration repository:

```text
patches/regraph_gather_cold_start_init_20260712.diff
```

The older always-clear patch remains useful as historical evidence only:

```text
patches/regraph_gather_uram_init_fix_20260712.diff
```

## Implemented ReGraph SSSP Pieces

Weighted SSSP is implemented as a ReGraph app under:

```text
/home/chuxiao/ReGraph/acc_udfs/sssp
```

Key behavior:

```text
input edge format: src dst weight
source vertex: REGRAPH_SOURCE, default 0
supersteps: argv[4] or REGRAPH_SUPERSTEPS, default 1
edge property: 12-bit weight encoded with destination metadata
property semantics: high bit means active update, low 31 bits carry distance
```

The app uses ReGraph scatter/gather/apply:

```text
scatter: active src distance + edge weight
gather: min active update per destination
apply: update destination distance only if the gathered distance is smaller
```

Tiny weighted test graph:

```text
/home/chuxiao/ReGraph/dataset/tiny-weighted-sssp.txt
```

Expected source-0 distances:

```text
vertex 0 -> 0
vertex 1 -> 3
vertex 2 -> 7
vertex 3 -> 8
```

## Verified Evidence

Original sw_emu bring-up passed before the hardware-emulation investigation:

```text
/home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_swemu_20260711
```

After finding a hardware-emulation mismatch, the gather URAM initialization was
fixed and a clean sw_emu regression was run:

```text
/home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_swemu_fix_20260712
```

Key result:

```text
fixed sw_emu build completed
tiny weighted SSSP completed 4 supersteps
no verification mismatch was printed
final line: Processed edges: 8; Graph edges: 5
```

The fixed regression proves source-level compilation and software-emulation
functionality after the gather change. It does not prove hw_emu or real hw yet.

## HW Emulation Finding And Fix

The first user-provided hw_emu xclbin built successfully and ran through xsim,
but the tiny weighted SSSP functional check failed:

```text
vertex 1: expected 3, device 0
vertex 2: expected 7, device 0
vertex 3: expected 8, device 0
```

Evidence:

```text
/home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hwemu_check_20260712
```

Interpretation:

The old little/big gather code cleared `dst_tmp_prop_buffer` only under
`SW_EMU`. In `hw_emu` or real hardware, that local URAM can start with arbitrary
active-looking values. For SSSP min-reduction, this can dominate the result with
an incorrect zero-distance update.

Initial applied fix:

```text
/home/chuxiao/ReGraph/acc_template/kernel_little_gs/acc_gather.h
/home/chuxiao/ReGraph/acc_template/kernel_big_gs/acc_gather.h
```

The first fixed-source version made `initDstTmpProp` run for sw_emu, hw_emu, and
hw, with an explicit loop label and `PIPELINE II=1`. It proved the correctness
issue but added a large per-superstep reset cost to the hardware path.

Fixed-source hw_emu has now been rebuilt and passed the tiny weighted SSSP run:

```text
/home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_emu_fixed_20260712_003353
```

Key evidence:

```text
scratch: /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch
xclbin:  xclbin_hw_emu_sssp/graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
host:    host_graph_fpga_sssp
```

Validation summary:

```text
Device[0]: program successful
Supersteps: 4
Processed edges: 8; Graph edges: 5
All the simulator processes exited successfully
mismatch_count=0
```

HLS evidence shows that `initDstTmpProp` was synthesized in both scatter/gather
kernels:

```text
littleKernelScatterGather: initDstTmpProp Final II = 1, Estimated Fmax 266.63 MHz
bigKernelScatterGather:    initDstTmpProp Final II = 1, Estimated Fmax 281.54 MHz
```

Manual smoke-test rerun:

```text
/home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_emu_manual_check_20260712_0101
```

The rerun used the same fixed `hw_emu` host/xclbin and passed again:

```text
mismatch_count=0
Device[0]: program successful!
Supersteps: 4
Processed edges: 8; Graph edges: 5
All the simulator processes exited successfully
```

User-reported build artifact recheck:

```text
/home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_emu_check_20260712_025255
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_030037_regraph_sssp_hwemu_usercheck/regraph_sssp_hw_emu_fixed_usercheck
```

The artifact check found the fixed-source host, xclbin, and emconfig under:

```text
/home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch
```

The rerun used source vertex 0 on `dataset/tiny-weighted-sssp.txt` for 4
supersteps and passed:

```text
mismatch_count=0
Device[0]: program successful!
Processed edges: 8; Graph edges: 5
All the simulator processes exited successfully
```

During the first rerun, Vitis tried to reuse an existing `.run/7` hardware
emulation cache and asked whether to overwrite files. The stale cache was not
deleted; it was moved to:

```text
/home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/.run.backup_before_hwemu_check_20260712_025445
```

The recheck used this command shape:

```bash
cd /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch
REGRAPH_SOURCE=0 \
  ./host_graph_fpga_sssp \
  xclbin_hw_emu_sssp/graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin \
  dataset/tiny-weighted-sssp.txt \
  1 \
  4
```

Artifact hashes from the same fixed-source `hw_emu` scratch:

```text
host:
  /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/host_graph_fpga_sssp
  sha256 15db9e29a1cb9dc6ebc572c96214e390d331be1996ba1635145bbb0261f39032

xclbin:
  /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/xclbin_hw_emu_sssp/graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
  sha256 e0068aabae0e2547117abd37d291d4ff561be4f2c0591ce994d80d7a3332347f
```

## Current Cold-start Reset Version

The current ReGraph source no longer clears the gather temporary-property URAM
on every hardware invocation. Instead, the host passes a new scalar control
argument, `reset_tmp_prop`, to both little and big scatter/gather kernels:

```text
reset_tmp_prop = (super_step == 0)
```

Current source files touched:

```text
/home/chuxiao/ReGraph/acc_template/kernel_little_gs/acc_gather.h
/home/chuxiao/ReGraph/acc_template/kernel_little_gs/kernel_scatter_gather.cpp
/home/chuxiao/ReGraph/acc_template/kernel_big_gs/acc_gather.h
/home/chuxiao/ReGraph/acc_template/kernel_big_gs/kernel_scatter_gather.cpp
/home/chuxiao/ReGraph/host/host.cpp
```

Important detail:

```text
SW_EMU keeps clearing every call to preserve the C-simulation behavior.
hw_emu/hw clear only when reset_tmp_prop is true.
```

An intermediate attempt used a static `dst_tmp_prop_initialized` flag inside the
HLS dataflow region. That failed `hw_emu` HLS with a dataflow feedback
dependence on the static variable, so it was abandoned.

The current cold-start reset source was rebuilt in `hw_emu` and passed the tiny
weighted SSSP functional smoke test:

```text
scratch:  /home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch
evidence: /home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_emu_coldinit_20260712_0900
bundle:   /home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_091237_regraph_coldinit_hwemu/regraph_sssp_hw_emu_coldinit
```

Build/test command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_regraph_sssp.sh \
  --target hw_emu \
  --run-tiny \
  --scratch /home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch \
  --evidence-dir /home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_emu_coldinit_20260712_0900
```

Cold-start `hw_emu` artifact hashes:

```text
host:
  /home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/host_graph_fpga_sssp
  sha256 9ceb054575e63aa9c6b045875eae2de205e14788a1f211c9116b411df4fed8c8

xclbin:
  /home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/xclbin_hw_emu_sssp/graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
  sha256 5d63557f6a15d8c3ecc25e0fcbf62bb61df1bf04ef29d3c3b8393b4007662f67
```

Validation summary:

```text
mismatch_count=0
Device[0]: program successful!
Supersteps: 4
Starting superstep 1/4
Starting superstep 2/4
Starting superstep 3/4
Starting superstep 4/4
Processed edges: 8; Graph edges: 5
All the simulator processes exited successfully
```

HLS top-module area from the cold-start `hw_emu` evidence:

```text
bigKernelScatterGather:    FF=78689, LUT=66736, BRAM=44,  URAM=64, DSP=0
littleKernelScatterGather: FF=31199, LUT=44240, BRAM=143, URAM=64, DSP=0
kernelApply:               FF=12465, LUT=7402,  BRAM=30,  URAM=0,  DSP=0
kernelHBMWrapper:          FF=49696, LUT=11889, BRAM=60,  URAM=0,  DSP=0
kernelBigGSMerger:         FF=522,   LUT=582,   BRAM=0,   URAM=0,  DSP=0
kernelLittleGSMerger:      FF=751,   LUT=6141,  BRAM=0,   URAM=0,  DSP=0
```

## Old-source HW Build Caveat

A ReGraph `hw` build has been monitored under:

```text
/home/chuxiao/ReGraph_sssp_hw_scratch
```

Process shape:

```text
podman -> make APP=sssp TARGETS=hw -> v++ link -> vpl -> vivado impl_1
```

It reached routed reports on 2026-07-12:

```text
/home/chuxiao/ReGraph_sssp_hw_scratch/_x/link/vivado/vpl/prj/prj.runs/impl_1/kernel_util_routed.rpt
/home/chuxiao/ReGraph_sssp_hw_scratch/_x/link/vivado/vpl/prj/prj.runs/impl_1/slr_util_routed.rpt
/home/chuxiao/ReGraph_sssp_hw_scratch/_x/link/vivado/vpl/prj/prj.runs/impl_1/hw_bb_locked_timing_summary_routed.rpt
```

Evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_024815_regraph_oldsource_routed/regraph_sssp_hw_oldsource_routed
```

At the first evidence collection time, no final `.xclbin` had been observed yet:

```text
xclbins: 0
```

The same old-source build later completed and produced a final real-hardware
xclbin:

```text
/home/chuxiao/ReGraph_sssp_hw_scratch/xclbin_hw_sssp/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
sha256: 0f8e9f786b35c951b76b33f9ecac30b25ef888823a99de21be50a7e58f98b76d
```

Completed-build evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_030317_regraph_oldsource_hw_complete/regraph_sssp_hw_oldsource_complete
```

Key routed utilization:

```text
LUT=55479
LUTAsMem=9964
REG=92137
BRAM=120
URAM=128
DSP=0
```

Timing was closed for this old-source build:

```text
WNS=0.003 ns
TNS=0.000 ns
WHS=0.009 ns
THS=0.000 ns
```

However, that scratch tree still contains the pre-fix gather files with the
`#ifdef SW_EMU` guard around `dst_tmp_prop_buffer` initialization. If it
succeeds, it is useful as old-source compile/resource evidence only. It is not
valid evidence that the weighted SSSP hardware fix works.

## Next Proof Required

Fixed-source real `hw` was attempted from:

```text
/home/chuxiao/ReGraph_sssp_hw_fixed_scratch
```

The attempt reached routed/post-route reports but failed during the `impl_1`
bitstream/write-bitstream flow, so it did not produce a runnable real-hardware
xclbin or host executable:

```text
xclbins: 0
host_graph_fpga_sssp: missing
```

Failure evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_083525_regraph_fixed_hw_failed/regraph_sssp_hw_fixed_failed
```

Important failure signals:

```text
Vivado/VPL: Failed runs(s): impl_1
CrashLog:  /home/chuxiao/ReGraph_sssp_hw_fixed_scratch/_x/logs/link/CrashLog/hs_err_pid27009.log
Timing:    WNS=-1.160 ns, TNS=-9465.562 ns, WHS=0.008 ns, THS=0.000 ns
Resources: LUT=55886, LUTAsMem=9964, REG=93490, BRAM=120, URAM=128, DSP=0
```

The CrashLog stack points into Vivado timing-report generation
(`librdi_timing.so`) after post-route physical optimization. The timing report
also says constraints are not met, so this should be treated as real `hw`
failure evidence, not as a timing-closed hardware artifact.

The current `hw_emu` functional status is good. To close ReGraph weighted SSSP
item 1 on real hardware:

```text
1. rebuild real hw from the current cold-start reset source
2. if the default clock fails timing again, retry with an explicit lower kernel frequency
3. collect xclbin, host, link summary, system estimates, routed utilization and timing
4. run a tiny or small weighted SSSP hardware smoke test if board access is available
```

Reusable build helper:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_regraph_sssp.sh --target hw_emu --run-tiny
./scripts/build_regraph_sssp.sh --target hw
./scripts/build_regraph_sssp.sh --target hw --kernel-frequency-mhz 250
```

Only after that should the GraSU + ReGraph combined hardware build be treated as
the next primary milestone.
