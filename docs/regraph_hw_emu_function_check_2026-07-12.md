# ReGraph Cold-start HW Emulation Function Check

Date: 2026-07-12

## Checked Artifacts

Build root:

```text
/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch
```

Required runtime artifacts exist:

```text
/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/host_graph_fpga_sssp
/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/xclbin_hw_emu_sssp/graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/xclbin_hw_emu_sssp/xilinx_u55c_gen3x16_xdma_3_202210_1/emconfig.json
```

Hashes from the check:

```text
9ceb054575e63aa9c6b045875eae2de205e14788a1f211c9116b411df4fed8c8  host_graph_fpga_sssp
5d63557f6a15d8c3ecc25e0fcbf62bb61df1bf04ef29d3c3b8393b4007662f67  xclbin_hw_emu_sssp/graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
9aa63a3b683163fda7e374efbfeacbeadd45e2dbd58e0e5a148ccb357aa6fefd  xclbin_hw_emu_sssp/xilinx_u55c_gen3x16_xdma_3_202210_1/emconfig.json
```

## Function Test

Dataset:

```text
/home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch/dataset/tiny-weighted-sssp.txt
```

Edges:

```text
0 1 3
0 2 10
1 2 4
1 3 7
2 3 1
```

The run used source vertex 0, one dense partition, and four SSSP supersteps.
Expected shortest distances are 0, 3, 7, and 8.

Command:

```bash
cd /home/chuxiao/ReGraph_sssp_hw_emu_coldinit_scratch
source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
source /home/chuxiao/grasu-regraph-integration/scripts/env.sh
cp -f xclbin_hw_emu_sssp/xilinx_u55c_gen3x16_xdma_3_202210_1/emconfig.json ./emconfig.json
timeout 600s env XCL_EMULATION_MODE=hw_emu REGRAPH_SOURCE=0 ./host_graph_fpga_sssp \
  xclbin_hw_emu_sssp/graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin \
  dataset/tiny-weighted-sssp.txt \
  1 \
  4
```

Result:

```text
exit_code=0
Device[0]: program successful!
[INFO] Supersteps: 4
[INFO] Starting superstep 1/4
[INFO] Starting superstep 2/4
[INFO] Starting superstep 3/4
[INFO] Starting superstep 4/4
Processed edges: 8; Graph edges: 5
INFO: [HW-EMU 06-1] All the simulator processes exited successfully
```

The ReGraph verification path compares the device result against software
end-to-end SSSP and prints `error: mismatch` plus an error count on differences.
This run produced no mismatch or error lines.

Full run evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/regraph_hw_emu_function_check_20260712_095347
```

Repeat check after the user's successful `hw_emu` build:

```text
/home/chuxiao/grasu-regraph-integration/results/regraph_hw_emu_function_check_20260712_103942
```

Key lines from the repeat check:

```text
Device[0]: program successful!
[INFO] Supersteps: 4
[INFO] Starting superstep 1/4
[INFO] Starting superstep 2/4
[INFO] Starting superstep 3/4
[INFO] Starting superstep 4/4
[INFO] dataset/tiny-weighted-sssp.txt,  numD: 1,  e2e: 156017 ms;  Throught: 1.28192e-07 MTEPS :
Processed edges: 8; Graph edges: 5
INFO: [HW-EMU 06-1] All the simulator processes exited successfully
mismatch_count=0
```

Fresh local rerun for artifact/function inspection:

```text
/home/chuxiao/grasu-regraph-integration/results/regraph_hw_emu_function_check_20260712_111222_fresh
```

The fresh rerun copied the host, xclbin, and dataset into an isolated
`run_work` directory and completed all four supersteps. It printed
`Device[0]: program successful!`, `Processed edges: 8; Graph edges: 5`, and
`All the simulator processes exited successfully`, with no `mismatch` lines.
This rerun did not copy `emconfig.json` into the isolated run directory, so XRT
printed `Unable to find emconfig.json` and used its default hw-em device model.
The functional result still matches the earlier clean repeat check above; use
the clean repeat check command for final reproducibility.

Fresh evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_111630_regraph_hwemu_fresh_function/regraph_sssp_hw_emu_coldinit
```

The repeated run used the same artifact hashes:

```text
9ceb054575e63aa9c6b045875eae2de205e14788a1f211c9116b411df4fed8c8  host_graph_fpga_sssp
5d63557f6a15d8c3ecc25e0fcbf62bb61df1bf04ef29d3c3b8393b4007662f67  graph_fpga.hw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin
9aa63a3b683163fda7e374efbfeacbeadd45e2dbd58e0e5a148ccb357aa6fefd  emconfig.json
```

## Resource Evidence

Collected evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_095752_regraph_coldinit_hwemu_usercheck/regraph_sssp_hw_emu_coldinit_usercheck
```

The bundle includes copied Vitis reports, artifact hashes, connectivity, HLS
area, system estimates, and commands.

Observed top-module HLS area from the bundle:

```text
bigKernelScatterGather     FF 78689  LUT 66736  BRAM 44   URAM 64  DSP 0
kernelApply                FF 12465  LUT 7402   BRAM 30   URAM 0   DSP 0
kernelBigGSMerger          FF 522    LUT 582    BRAM 0    URAM 0   DSP 0
kernelHBMWrapper           FF 49696  LUT 11889  BRAM 60   URAM 0   DSP 0
kernelLittleGSMerger       FF 751    LUT 6141   BRAM 0    URAM 0   DSP 0
littleKernelScatterGather  FF 31199  LUT 44240  BRAM 143  URAM 64  DSP 0
```

The linked design has six kernels, one compute unit each:

```text
bigKernelScatterGather
kernelBigGSMerger
kernelLittleGSMerger
kernelApply
kernelHBMWrapper
littleKernelScatterGather
```

## Notes

An initial rerun failed before simulation because the shell did not have
`XILINX_VITIS` set and `emconfig.json` was not in the run directory. Sourcing
Vitis and copying the generated `emconfig.json` into the current directory fixed
the runtime environment issue.
