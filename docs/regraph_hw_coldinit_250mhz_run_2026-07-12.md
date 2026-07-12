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
[1/5] Copying fixed ReGraph source into scratch...
[2/5] Checking that the scratch contains the gather init fix...
[3/5] Building ReGraph APP=sssp TARGETS=hw...
```

Observed first completed kernel:

```text
kernelApply.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
kernelApply estimated Fmax: 293.28 MHz
```

The compile command did not include `--kernel_frequency` in the per-kernel
compile stage. The helper now applies the frequency option only to `LDCLFLAGS`,
matching ReGraph's original `host.mk` comment and avoiding accidental compile
option incompatibility.

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
