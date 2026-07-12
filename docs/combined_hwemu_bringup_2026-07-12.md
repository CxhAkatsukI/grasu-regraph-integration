# Combined GraSU + ReGraph hw_emu Bring-Up, 2026-07-12

This note records the first single-xclbin integration proof for:

```text
GraSU dynamic update kernels + ReGraph weighted SSSP kernels
```

The proof here is `hw_emu`, not final real `hw`. It verifies that the two
accelerators can be linked into one Vitis binary and that the existing GraSU and
ReGraph hosts can each load that same binary on their smoke workloads.

## Build Script

Added:

```text
scripts/build_combined_grasu_regraph_xclbin.sh
```

The script:

- checks that GraSU and ReGraph `.xo` inputs exist;
- merges GraSU and ReGraph connectivity into one Vitis config;
- writes a manifest, input hashes, generated config, and exact link command;
- optionally runs `v++ --link` inside `vivado-runner:22.04-feiyang`.

Default ReGraph HBM offset is `0` because the current ReGraph host uses fixed
HBM bank IDs in `host/preprocess/partition_schedule.cpp`. A non-zero offset can
compile, but it also requires matching host-side buffer bank changes.

## Successful Combined hw_emu Link

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_combined_grasu_regraph_xclbin.sh \
  --target hw_emu \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible \
  --link
```

Main output:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin
sha256 daf8bb44c32295a27827993bdf913eb9d311f27e4d21efbaf46edfc57224995f
```

Generated command/config evidence:

```text
link command:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/link_command.sh
  sha256 f29096041f711c9dc32992b62e0ed2d9a0a417be697e940eb92c29a3ef4e2901

link config:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/config/grasu_regraph_combined_hw_emu.cfg
  sha256 9f5e0f9ec7538665c0c0ee14e27ffa0eeca8f2c68326c72ea624824a71e34377

link summary:
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin.link_summary
  sha256 26431f3dd3b74c0f0e60b9aa00dc767049c93ec6194311ea1e729a48ceaa2a32
```

The combined binary contains 15 CUs:

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

## Functional Smoke Evidence

### ReGraph Weighted SSSP

Workload:

```text
dataset: /home/chuxiao/ReGraph_sssp_hw_emu_fixed_scratch/dataset/tiny-weighted-sssp.txt
source: 0
numD: 1
supersteps: 4
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hwemu_function_20260712_020457_host_compatible_retry
```

Key result:

```text
Device[0]: program successful!
Supersteps: 4
Starting superstep 1/4
Starting superstep 2/4
Starting superstep 3/4
Starting superstep 4/4
Processed edges: 8; Graph edges: 5
All the simulator processes exited successfully
mismatch_count=0
```

### GraSU Update Smoke

Workload:

```text
graph:  /home/chuxiao/GraSU/u55c_hbm/smoke/delete_one.graph
result: /home/chuxiao/GraSU/u55c_hbm/smoke/delete_one.result
```

Evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/combined_hwemu_grasu_function_20260712_021521
```

Key result:

```text
check result passed
kernel start running...
kernel finish
All the simulator processes exited successfully
```

The `hw_emu` runtime is slow and not a performance number. ReGraph tiny SSSP on
the combined xclbin reported about 529 s, and GraSU smoke reported about 510 s.
Use these only as functional proof.

## HBM Mapping Finding

An earlier combined `hw_emu` build with `--regraph-hbm-offset 4` linked
successfully:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_emu_link_check
```

But ReGraph host failed at runtime:

```text
XRT WARNING: Argument '0' of kernel 'kernelHBMWrapper' is allocated in memory bank 'HBM[1]';
compute unit 'kernelHBMWrapper_1' cannot be used with this argument and is ignored.
XRT ERROR: kernel 'kernelHBMWrapper' has no compute units to support required argument connectivity.
```

Interpretation: ReGraph's host-side buffers still use the original HBM bank
assignment. Keeping offset `0` is host-compatible. Moving ReGraph to HBM[4..7]
would require host changes in the ReGraph partition/buffer allocation path.

## Resource Evidence

Evidence bundle:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_022520_combined_hwemu_host_compatible
```

Important comparison result:

```text
GraSU baseline vs combined:
  same-component HLS changes: 0
  same-kernel CU count changes: 0

ReGraph baseline vs combined:
  same-component HLS changes: 0
  same-kernel CU count changes: 0
```

This is `hw_emu`, so there is no placed/routed utilization. Final resource
claims still require real `hw` evidence.

## Next hw Steps

Cold-start ReGraph real `hw` artifacts are still the missing prerequisite for
final combined `hw`.

Current preflight status, 2026-07-12:

```text
GraSU hw inputs: present
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build/bin_search.hw.xo
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build/dispatch.hw.xo
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build/process_cache.hw.xo
  /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/build/process_ddr.hw.xo

ReGraph cold-start source: present
  /home/chuxiao/grasu-regraph-integration/repos/ReGraph -> /home/chuxiao/ReGraph
  reset_tmp_prop cold-start gather init is present in little and big kernels

ReGraph cold-start 250 MHz hw scratch: running
  /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch
  all 6 ReGraph hw .xo files are present
  Vitis/Vivado is currently in vpl synth

Combined real-hw link preflight: generated
  /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_preflight
  inputs.tsv records hashes for 4 GraSU .xo files and 6 ReGraph .xo files
```

Build cold-start ReGraph SSSP real hardware and immediately run the tiny
weighted SSSP hardware smoke if board access is available. The current run uses
the same command shape, without `--run-tiny`, inside tmux:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_regraph_sssp.sh \
  --target hw \
  --scratch /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch \
  --evidence-dir /home/chuxiao/ReGraph/.tmp_doc/evidence_sssp_hw_coldinit_250mhz_20260712_092221 \
  --kernel-frequency-mhz 250 \
  --run-tiny \
  --source-vertex 0 \
  --supersteps 4 \
  --num-dense 1
```

If only the long build should run first, omit `--run-tiny` and run the smoke
manually after reviewing the build artifacts.

Monitor the cold-start ReGraph `hw` build:

```bash
tmux has-session -t regraph_hw_coldinit_250mhz_20260712_092221 && echo running || echo stopped

tail -120 \
  /home/chuxiao/ReGraph/.tmp_doc/regraph_hw_coldinit_250mhz_20260712_092221.tmux.log

find /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch -maxdepth 8 \
  \( -name 'graph_fpga.hw*.xclbin' \
     -o -name '*.xclbin.link_summary' \
     -o -name '*kernel_util_routed.rpt' \
     -o -name '*slr_util_routed.rpt' \
     -o -name '*timing_summary*.rpt' \
     -o -name 'dr_timing_summary.rpt' \) \
  -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -120
```

Collect cold-start ReGraph `hw` evidence after it completes:

```bash
cd /home/chuxiao/grasu-regraph-integration
BASE=results/resource_evidence_$(date +%Y%m%d_%H%M%S)_regraph_coldinit_hw_250mhz
mkdir -p "$BASE"

./scripts/collect_vitis_evidence.py \
  --label regraph_sssp_hw_coldinit_250mhz \
  --build-root /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch \
  --out-dir "$BASE/regraph_sssp_hw_coldinit_250mhz" \
  --artifact /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
  --note 'Cold-start ReGraph weighted SSSP real hw build at 250 MHz.'
```

Then link the real combined hardware:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_combined_grasu_regraph_xclbin.sh \
  --target hw \
  --kernel-frequency 250 \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz \
  --link
```

After real `hw` completes, collect and compare evidence:

```bash
BASE=results/resource_evidence_$(date +%Y%m%d_%H%M%S)_combined_hw
mkdir -p "$BASE"

./scripts/collect_vitis_evidence.py \
  --label grasu_hw_u55c \
  --build-root /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw \
  --out-dir "$BASE/grasu_hw" \
  --artifact /home/chuxiao/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c \
  --note 'GraSU standalone U55C hw baseline.'

./scripts/collect_vitis_evidence.py \
  --label regraph_sssp_hw_coldinit_250mhz \
  --build-root /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch \
  --out-dir "$BASE/regraph_sssp_hw_coldinit_250mhz" \
  --artifact /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
  --note 'Cold-start ReGraph weighted SSSP real hw baseline at 250 MHz.'

./scripts/collect_vitis_evidence.py \
  --label grasu_regraph_combined_hw \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz \
  --out-dir "$BASE/combined_hw" \
  --artifact /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz/build/grasu_regraph_combined.hw.xclbin \
  --note 'Combined GraSU + ReGraph weighted SSSP real hw xclbin.'

./scripts/compare_vitis_resources.py \
  --label grasu_hw_vs_combined_hw \
  --before "$BASE/grasu_hw" \
  --after "$BASE/combined_hw" \
  --out-dir "$BASE/compare_grasu_hw_vs_combined"

./scripts/compare_vitis_resources.py \
  --label regraph_hw_vs_combined_hw \
  --before "$BASE/regraph_sssp_hw_coldinit_250mhz" \
  --after "$BASE/combined_hw" \
  --out-dir "$BASE/compare_regraph_hw_vs_combined"
```
