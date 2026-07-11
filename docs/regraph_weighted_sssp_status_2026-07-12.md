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
latest gather initialization patch is mirrored in this integration repository:

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

Applied fix:

```text
/home/chuxiao/ReGraph/acc_template/kernel_little_gs/acc_gather.h
/home/chuxiao/ReGraph/acc_template/kernel_big_gs/acc_gather.h
```

The initialization now runs for sw_emu, hw_emu, and hw, with an explicit
`initDstTmpProp` loop label and `PIPELINE II=1`.

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

## Current Running HW Build Caveat

As of this note, a ReGraph `hw` build is running under:

```text
/home/chuxiao/ReGraph_sssp_hw_scratch
```

Process shape:

```text
podman -> make APP=sssp TARGETS=hw -> v++ link -> vpl -> vivado impl_1
```

It has live Vivado CPU activity and does not appear deadlocked.

However, that scratch tree still contains the pre-fix gather files with the
`#ifdef SW_EMU` guard around `dst_tmp_prop_buffer` initialization. If it
succeeds, it is useful as old-source compile/resource evidence only. It is not
valid evidence that the weighted SSSP hardware fix works.

## Next Proof Required

To close ReGraph weighted SSSP item 1:

```text
1. rebuild hw from the same fixed source
2. collect xclbin, host, link summary, system estimates, routed utilization and timing
3. run a tiny or small weighted SSSP hardware smoke test if board access is available
```

Reusable build helper:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_regraph_sssp.sh --target hw_emu --run-tiny
./scripts/build_regraph_sssp.sh --target hw
```

Only after that should the GraSU + ReGraph combined hardware build be treated as
the next primary milestone.
