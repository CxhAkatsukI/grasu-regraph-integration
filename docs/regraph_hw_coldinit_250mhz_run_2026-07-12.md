# ReGraph Cold-start Real HW Run, 250 MHz

Date: 2026-07-12

## Purpose

The current ReGraph weighted SSSP source has passed `hw_emu` with the
host-controlled `reset_tmp_prop` cold-start gather initialization. The previous
fixed-source real `hw` attempt failed timing at the default clock, so this run
tries a lower link target clock first:

```text
kernel_frequency_mhz=250
```

This is a timing-closure experiment. If it succeeds, it gives us a real
hardware artifact to test. If it fails, its routed reports become the next
optimization target.

## Running Session

The build is running in tmux:

```text
session:  regraph_hw_coldinit_250mhz_20260712_092221
scratch:  /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch
evidence: /home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_coldinit_250mhz_20260712_092221
log:      /home/chuxiao/ReGraph/.tmp_doc/regraph_hw_coldinit_250mhz_20260712_092221.tmux.log
```

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_regraph_sssp.sh \
  --target hw \
  --scratch /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch \
  --evidence-dir /home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_coldinit_250mhz_20260712_092221 \
  --kernel-frequency-mhz 250
```

## Monitoring

Check whether the build session is still alive:

```bash
tmux has-session -t regraph_hw_coldinit_250mhz_20260712_092221 && echo running || echo stopped
```

Tail the build log:

```bash
tail -120 /home/chuxiao/ReGraph/.tmp_doc/regraph_hw_coldinit_250mhz_20260712_092221.tmux.log
```

Inspect generated artifacts:

```bash
find /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch -maxdepth 3 \
  \( -name '*.xo' -o -name '*.xclbin' -o -name '*.compile_summary' -o -name '*.link_summary' \) \
  -printf '%TY-%Tm-%Td %TH:%TM %s %p\n' | sort
```

Check live Vitis/Vivado processes:

```bash
ps -eo pid,ppid,etimes,stat,cmd | \
  rg 'ReGraph_sssp_hw_coldinit_250mhz|make APP=sssp|v\+\+|vivado|vitis|podman'
```

## Early Evidence

The build entered hardware compilation successfully:

```text
[1/5] Copying current ReGraph source into scratch...
[2/5] Checking that the scratch contains the gather init fix...
[3/5] Building ReGraph APP=sssp TARGETS=hw...
```

Observed first completed kernel:

```text
kernelApply.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
kernelApply estimated Fmax: 293.28 MHz
```

Later status from the same run:

```text
all 6 kernel .xo files were generated
bigKernelScatterGather passed real hw HLS and produced its .xo
v++ link command included --kernel_frequency=250
system_link completed
vpl started and reached Step synth at 2026-07-12 09:32:26 Asia/Shanghai
vpl synth completed at 2026-07-12 09:49:06 Asia/Shanghai
vpl impl started at 2026-07-12 09:49:06 Asia/Shanghai
vpl finished logic optimization at 2026-07-12 09:59:46 Asia/Shanghai
vpl placement started at 2026-07-12 09:59:46 Asia/Shanghai
placement reached global placement phase 2.1.1.4 at 2026-07-12 10:06:22 Asia/Shanghai
global placement core completed at 2026-07-12 10:19:04 Asia/Shanghai
detail placement completed at 2026-07-12 10:23:08 Asia/Shanghai
post-placement optimization started at 2026-07-12 10:23:08 Asia/Shanghai
place_design completed successfully at 2026-07-12 10:28:02 Asia/Shanghai
placed kernel utilization report was generated at 2026-07-12 10:28:03 Asia/Shanghai
post-placement phys_opt_design completed successfully at 2026-07-12 10:30:46 Asia/Shanghai
route_design started at 2026-07-12 10:30:46 Asia/Shanghai
route reached rip-up and reroute global iteration 0 at 2026-07-12 10:35:51 Asia/Shanghai
```

Observed HLS Fmax values from the build log:

```text
kernelApply:                293.28 MHz
kernelHBMWrapper:           405.02 MHz
littleKernelScatterGather:  266.63 MHz
kernelLittleGSMerger:       447.16 MHz
bigKernelScatterGather:     281.54 MHz
kernelBigGSMerger:          869.57 MHz
```

`bigKernelScatterGather` completed HLS successfully; use its per-kernel report
for exact loop/Fmax details if needed:

```text
/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/_x/reports/bigKernelScatterGather.hw.xilinx_u55c_gen3x16_xdma_3_202210_1/system_estimate_bigKernelScatterGather.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xtxt
```

The compile command did not include `--kernel_frequency` in the per-kernel
compile stage. The helper now applies the frequency option only to `LDCLFLAGS`,
matching ReGraph's original `host.mk` comment and avoiding accidental compile
option incompatibility.

## Placement Notes

During placement, Vivado printed warnings like:

```text
WARNING: [Place 30-1239] Failed to find partition obeying USER_SLR_ASSIGNMENT constraint, SLR -1, for Cell level0_i/ulp/<ReGraph CU>/inst.
```

This warning is not new to the cold-start build: the previous old-source
ReGraph standalone `hw` implementation logged the same warning for the same six
ReGraph CUs. The current link evidence still records the intended SLR
connectivity:

```text
kernelLittleGSMerger_1:      SLR1
kernelBigGSMerger_1:         SLR1
kernelApply_1:               SLR1
kernelHBMWrapper_1:          SLR0
littleKernelScatterGather_1: SLR0
bigKernelScatterGather_1:    SLR1
```

Treat the warning as an item to preserve in evidence, not as a current failure.
The final routed reports should be used to confirm the actual physical
placement and timing.

Placed-stage timing is close but not final:

```text
Estimated Timing Summary: WNS=-0.006 ns, TNS=-0.049 ns
Post Placement Timing Summary: WNS=-0.006 ns
Post-placement phys_opt Estimated Timing Summary: WNS=0.003 ns, TNS=0.000 ns
```

Do not use these values as final timing closure evidence. Route and post-route
physical optimization may still change timing materially.

Placed-stage reports generated so far:

```text
kernel_util_placed.rpt
slr_util_placed.rpt
full_util_placed.rpt
```

## Routing Notes

Early route has not failed, but it shows pressure that should be preserved for
post-run analysis:

```text
Intermediate Timing Summary: WNS=-0.021 ns, TNS=-0.173 ns, WHS=-0.178 ns, THS=-65.556 ns
Intermediate Timing Summary: WNS=-0.021 ns, TNS=-0.064 ns, WHS=-0.186 ns, THS=-111.286 ns
Intermediate Timing Summary: WNS=-0.098 ns, TNS=-0.393 ns, WHS=N/A, THS=N/A
Intermediate Timing Summary: WNS=-0.017 ns, TNS=-0.132 ns, WHS=0.008 ns, THS=0.000 ns
Local routing congestion detected: at least 372 CLBs have high pin utilization
Estimated Global/Short routing congestion: level 5 (32x32)
High bus-skew violations detected during initial routing
```

These are intermediate route values. The final judgment still depends on
routed timing, post-route physical optimization, and bitstream/xclbin
generation.

As of the latest check, the Vivado process is still active in route. The hold
side has improved to non-negative WHS/THS in the most recent intermediate
summary, but setup still has small negative slack and must not be treated as
closed until final routed timing is emitted.

## Completion Criteria

This run is useful only after one of these outcomes is recorded:

```text
success:
  host_graph_fpga_sssp exists
  xclbin_hw_sssp/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin exists
  collect_vitis_evidence.py captures artifact hashes, CU structure, resources and timing
  board smoke test is attempted if a U55C device is available

failure:
  build log records the failing phase
  routed/utilization/timing reports are collected if present
  the failure is summarized with WNS/TNS and the next likely fix
```
