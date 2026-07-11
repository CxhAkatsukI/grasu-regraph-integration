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

Fixed-source ReGraph real `hw` artifacts are still the missing prerequisite for
final combined `hw`.

Build fixed-source ReGraph SSSP real hardware:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_regraph_sssp.sh --target hw
```

Then link the real combined hardware:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_combined_grasu_regraph_xclbin.sh \
  --target hw \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_host_compatible \
  --link
```

After real `hw` completes, collect and compare evidence:

```bash
BASE=results/resource_evidence_$(date +%Y%m%d_%H%M%S)_combined_hw
mkdir -p "$BASE"

./scripts/collect_vitis_evidence.py \
  --label grasu_regraph_combined_hw \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_host_compatible \
  --out-dir "$BASE/combined_hw" \
  --note 'Combined GraSU + ReGraph weighted SSSP real hw xclbin.'

./scripts/compare_vitis_resources.py \
  --label grasu_hw_vs_combined_hw \
  --before /path/to/grasu_hw_evidence \
  --after "$BASE/combined_hw" \
  --out-dir "$BASE/compare_grasu_hw_vs_combined"

./scripts/compare_vitis_resources.py \
  --label regraph_hw_vs_combined_hw \
  --before /path/to/regraph_fixed_hw_evidence \
  --after "$BASE/combined_hw" \
  --out-dir "$BASE/compare_regraph_hw_vs_combined"
```
