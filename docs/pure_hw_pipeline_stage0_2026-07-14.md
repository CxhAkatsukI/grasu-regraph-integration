# GraSU -> ReGraph Pure-Hardware Pipeline, Stage 0

Date: 2026-07-14 Asia/Shanghai

Branch:

```text
codex/pure-hw-pipeline
```

This note defines the start point and first implementation slice for the U55C
pure hardware pipeline. It is intentionally explicit about what is already
proved and what is not yet true, so later timing claims do not inherit accidental
host-side work.

## Current Proven Baseline

The integration repository already proves these weaker facts:

- GraSU and ReGraph can be linked into the same U55C xclbin.
- The same xclbin can be loaded by the existing GraSU host and ReGraph host.
- GraSU can export the actual post-update device graph after PMA D2H and host
  `merge_data`, and ReGraph can consume that exported graph.
- The host-conversion baseline passes the smoke cases recorded in
  `docs/device_graph_export_handoff_2026-07-14.md`.
- The real combined hardware xclbin recorded in
  `docs/combined_hw_real_validation_2026-07-12.md` has hash:

```text
d4296714739acea95a8f6a2f66e113849f089fe8e026fd72e7ee40c9e56f05b0
```

Those facts are useful, but they do not satisfy the pure pipeline goal yet.

## Stage 0 SW_EMU Link Milestone

As of 2026-07-14 15:40 Asia/Shanghai, the first pure-pipeline `sw_emu`
xclbin links successfully from the current integration source tree.

Successful command sequence:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/prepare_pure_hw_pipeline_build.sh \
  --target sw_emu \
  --build-root .tmp_build/pure_pipeline_sw_emu_stage0
.tmp_build/pure_pipeline_sw_emu_stage0/compile_commands.sh \
  2>&1 | tee .tmp_build/pure_pipeline_sw_emu_stage0/compile_commands_stage14.log
.tmp_build/pure_pipeline_sw_emu_stage0/link_command.sh \
  2>&1 | tee .tmp_build/pure_pipeline_sw_emu_stage0/link_command_stage17.log
```

Output xclbin:

```text
.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
sha256: 6c752a5c6abf56998753fc531dd1f8a7ce7f98395a352824a83c00ffe4dd01d5
size:   6.2M
```

This was the first link-only milestone. It has since been superseded by the
correctness-tested xclbin recorded below.

Generated XO inputs recorded in:

```text
.tmp_build/pure_pipeline_sw_emu_stage0/inputs.tsv
.tmp_build/pure_pipeline_sw_emu_stage0/manifest.env
```

This build does not reuse old GraSU or ReGraph XOs. The generated XOs are:

```text
bin_search.sw_emu.xo
dispatch.sw_emu.xo
process_cache.sw_emu.xo
process_ddr.sw_emu.xo
kernelApply.sw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
kernelHBMWrapper.sw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
kernelLittleGSMerger.sw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
bigKernelScatterGather.sw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
kernelBigGSMerger.sw_emu.xilinx_u55c_gen3x16_xdma_3_202210_1.xo
pma_to_regraph_adapter.sw_emu.xo
lksg_stream.sw_emu.xo
```

Toolchain notes for this host:

- `/tmp` is a 32G tmpfs and was full during link. Generated scripts export
  `TMPDIR`, `TMP`, and `TEMP` to the build-root `tmp/` directory.
- Vitis 2024.1 uses gcc 8.3 headers against newer system pthread headers in
  `sw_emu`. Generated scripts provide a local `gcc_compat/bits/gthr-default.h`
  shim through `CPLUS_INCLUDE_PATH`.
- Vitis internal top-level linking can select Xilinx binutils 2.26, which does
  not understand the system glibc `.relr.dyn` sections. Generated scripts export
  `LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu` and
  `COMPILER_PATH=/usr/bin` so gcc finds the system runtime objects and linker.

## Stage 0 SW_EMU Correctness Milestone

As of 2026-07-14 16:48 Asia/Shanghai, the first pure-pipeline host runner
executes the linked `sw_emu` xclbin and passes CPU-oracle checks for the four
required small graph families: chain, hot-source, spread, and hot-destination.

Source base before this milestone:

```text
dc9f731e200338d657d86c8cb07acca976b233b1
```

Current artifacts:

```text
705fa800d62d04aef4814b275e94b76749ba7120b46aaa0036066e555d65fcdd  .tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
72bd14add4a9922fe3651627f06403875b0d90918ec9637af40979f504429a19  .tmp_build/pure_pipeline_sw_emu_stage0/build/pma_to_regraph_adapter.sw_emu.xo
9f68e9a5f1075cd0ae0c319742cdfa2129937dfeb9a354f7df4f07fdf89c83ad  .tmp_build/pure_pipeline_sw_emu_stage0/build/lksg_stream.sw_emu.xo
ded281e1610545859ca5fcfdc4acfeecece6a1bad2805ba36ec98b0050814b06  .tmp_build/pure_pipeline_host_stage0/pure_pipeline_host
```

Host runner build:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_pure_pipeline_host.sh \
  --out-dir .tmp_build/pure_pipeline_host_stage0
```

Important runtime environment note: on this Debian host,
`/opt/xilinx/xrt/setup.sh` exits nonzero under `set -e` because its OS release
probe leaves `OSREL` empty. For these runs, XRT was configured explicitly:

```bash
source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
export XILINX_XRT=/opt/xilinx/xrt
export LD_LIBRARY_PATH=/opt/xilinx/xrt/lib:${LD_LIBRARY_PATH:-}
export PATH=/opt/xilinx/xrt/bin:${PATH}
export XCL_EMULATION_MODE=sw_emu
export EMCONFIG_PATH=/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_sw_emu_stage0/run
```

The run command shape is:

```bash
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_host_stage0/pure_pipeline_host \
  /home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin \
  <graph> \
  <result> \
  <source> \
  <supersteps>
```

Correctness evidence:

```text
chain:
  graph: workloads/sssp_benchmark_smoke/tiny_chain_v16/tiny_chain_v16.graph
  command args: source=0 supersteps=16
  log: .tmp_build/pure_pipeline_sw_emu_stage0/run_tiny_chain_step16_stage29.log
  input:  vertices=16 static_edges=15 update_edges=0 final_edges=15 pma_slots=240 source_internal=0
  timing: grasu_ms=2.680516 adapter_ms=51.484484 lksg_ms=3303.307957 apply_ms=5446.306848 hbm_ms=5430.682527 event_e2e_ms=5489.598471 wall_ms=5489.913370
  result: PASS mismatches=0 processed_edge_slots_per_superstep=240

hot-source:
  graph: workloads/sssp_benchmark_smoke/tiny_star_v16_u12/tiny_star_v16_u12.graph
  command args: source=0 supersteps=2
  log: .tmp_build/pure_pipeline_sw_emu_stage0/run_tiny_star_step2_stage30.log
  input:  vertices=16 static_edges=16 update_edges=12 final_edges=28 pma_slots=256 source_internal=0
  timing: grasu_ms=2.703177 adapter_ms=3.035507 lksg_ms=418.941903 apply_ms=696.898421 hbm_ms=694.936735 event_e2e_ms=701.021439 wall_ms=701.262785
  result: PASS mismatches=0 processed_edge_slots_per_superstep=256

spread:
  graph: workloads/generated/tiny_spread_v16_u8/tiny_spread_v16_u8.graph
  command args: source=0 supersteps=16
  log: .tmp_build/pure_pipeline_sw_emu_stage0/run_tiny_spread_step16_stage32.log
  input:  vertices=16 static_edges=16 update_edges=8 final_edges=24 pma_slots=256 source_internal=0
  timing: grasu_ms=3.288354 adapter_ms=66.317556 lksg_ms=3378.034651 apply_ms=5521.057076 hbm_ms=5504.958204 event_e2e_ms=5579.775674 wall_ms=5580.023040
  result: PASS mismatches=0 processed_edge_slots_per_superstep=256

hot-destination:
  graph: workloads/sssp_benchmark_smoke/tiny_hotdst_v64_u32/tiny_hotdst_v64_u32.graph
  command args: source=0 supersteps=16
  log: .tmp_build/pure_pipeline_sw_emu_stage0/run_tiny_hotdst_step16_stage31.log
  input:  vertices=64 static_edges=63 update_edges=32 final_edges=95 pma_slots=1008 source_internal=62
  timing: grasu_ms=2.744948 adapter_ms=151.333529 lksg_ms=3785.447053 apply_ms=5982.583235 hbm_ms=5967.074364 event_e2e_ms=6042.156183 wall_ms=6042.403101
  result: PASS mismatches=0 processed_edge_slots_per_superstep=1008
```

Key implementation fixes made during this milestone:

- The adapter now decodes GraSU `row_offset[src]` as packed
  `[begin, end]` 64-bit metadata instead of treating adjacent entries as raw CSR
  offsets.
- The adapter has a `wait_for_completion` scalar. Step 0 waits for the four
  GraSU PMA writer tokens; later SSSP supersteps replay the already-stable PMA
  graph without waiting for one-shot tokens.
- The host runner uses one OpenCL context/program/xclbin for GraSU, adapter,
  and ReGraph. It passes the same PMA buffers from GraSU into the adapter, so
  there is no graph D2H, host graph conversion, or graph H2D between GraSU and
  ReGraph.
- The host launches the steady-state pipeline in the order
  `adapter -> lksg_stream -> kernelHBMWrapper -> kernelApply`. In `sw_emu`,
  launching HBM/Apply first can leave the adapter and lksg CUs queued behind
  blocking stream consumers.

## Reproducible Smoke Runner

As of 2026-07-14 17:21 Asia/Shanghai, the smoke workload manifest is tracked
under:

```text
workloads/sssp_benchmark_smoke/manifest.tsv
```

It contains the four first-stage correctness families:

```text
tiny_chain_v16        chain            V=16 static=15 updates=0  final=15 source=0 supersteps=16
tiny_star_v16_u12     hot-source       V=16 static=16 updates=12 final=28 source=0 supersteps=2
tiny_spread_v16_u8    spread           V=16 static=16 updates=8  final=24 source=0 supersteps=16
tiny_hotdst_v64_u32   hot-destination  V=64 static=63 updates=32 final=95 source=0 supersteps=16
```

Regenerate the same manifest from source if needed:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/generate_sssp_benchmark_workloads.py \
  --preset smoke \
  --out-root workloads/sssp_benchmark_smoke
```

The smoke runner records the host/xclbin hashes, environment, per-case logs,
result line, and timing line:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_smoke.sh \
  --target sw_emu \
  --out-dir results/pure_pipeline_sw_emu_smoke_stage35 \
  --timeout 300
```

Evidence from this run:

```text
summary: results/pure_pipeline_sw_emu_smoke_stage35/summary.tsv
run env: results/pure_pipeline_sw_emu_smoke_stage35/run.env

10ffeca10cba00144378a1fb0c1632053ad7f45eeea80713c4973dc44b05a668  summary.tsv
e30ffbe2b791c21bc613cb51d9396e22eff14540e0d9938acdb43520665ee4c7  run.env

host_sha256=ded281e1610545859ca5fcfdc4acfeecece6a1bad2805ba36ec98b0050814b06
xclbin_sha256=705fa800d62d04aef4814b275e94b76749ba7120b46aaa0036066e555d65fcdd
git_head=12b4fe7090b46f7867453bf174adeff1437ae9b4
```

Result summary:

```text
tiny_chain_v16       PASS mismatches=0 vertices=16 final_edges=15  supersteps=16 event_e2e_ms=5934.524338
tiny_star_v16_u12    PASS mismatches=0 vertices=16 final_edges=28  supersteps=2  event_e2e_ms=726.008724
tiny_spread_v16_u8   PASS mismatches=0 vertices=16 final_edges=24  supersteps=16 event_e2e_ms=5894.365224
tiny_hotdst_v64_u32  PASS mismatches=0 vertices=64 final_edges=95  supersteps=16 event_e2e_ms=5919.880981
```

## Same-Input Host Baseline

The accepted `GraSU -> host -> ReGraph` baseline was rerun on the same tracked
smoke manifest. This is not the pure pipeline: GraSU and ReGraph load the same
combined hardware xclbin, but graph handoff still goes through D2H, host
serialization, and H2D. The `zero-cost` number below follows the current
comparison rule: `GraSU kernel ms + ReGraph E2E ms`, with the middle handoff
cost intentionally set to zero.

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset smoke \
  --workload-root workloads/sssp_benchmark_smoke \
  --out-root results/grasu_regraph_smoke_device_export_combined_hw_stage1 \
  --skip-generate \
  --device-graph-export \
  --grasu-host repos/GraSU/.tmp_build/u55c_hbm_hw/GraSU_host_u55c_export \
  --regraph-host /data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
  --combined-xclbin .tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin \
  --timeout 600
```

Evidence:

```text
summary: results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv
sha256:  719a48da5eacc18957903212d788106e923df08f596eb9635a8b7df533315945

GraSU export host sha256:
  95edb2a0b0028cd17ae340c56f3a642c86a7d6d4fd03e19e3ab1ac505c89b9e1
combined xclbin sha256:
  d4296714739acea95a8f6a2f66e113849f089fe8e026fd72e7ee40c9e56f05b0
ReGraph SSSP host sha256:
  9ceb054575e63aa9c6b045875eae2de205e14788a1f211c9116b411df4fed8c8
```

Result:

```text
tiny_chain_v16       PASS final_edges=15 zero_cost_ms=6.127929 mismatches=0
tiny_star_v16_u12    PASS final_edges=28 zero_cost_ms=2.526626 mismatches=0
tiny_spread_v16_u8   PASS final_edges=24 zero_cost_ms=5.743649 mismatches=0
tiny_hotdst_v64_u32  PASS final_edges=95 zero_cost_ms=6.202223 mismatches=0
```

The current stage comparison table is generated with:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 scripts/summarize_pure_pipeline_smoke.py \
  --host-summary results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv \
  --pure-summary results/pure_pipeline_sw_emu_smoke_stage35/summary.tsv \
  --pure-env results/pure_pipeline_sw_emu_smoke_stage35/run.env \
  --out-dir results/pure_pipeline_smoke_compare_stage0
```

Comparison artifacts:

```text
46ce81f7d4180fae62d93aed79f594d5a80f3ab7ea11117393a89508c070af37  results/pure_pipeline_smoke_compare_stage0/comparison.tsv
9f15207f422d3b62890bf70167e66e9a318f0b86f52117fd873ef692088c14be  results/pure_pipeline_smoke_compare_stage0/comparison.md
```

Current comparison note: the pure-pipeline timing is still `sw_emu`, so it is
correctness/control-flow evidence only. The first real timing comparison starts
after `hw_emu` and `hw` pure-pipeline xclbins are built and validated.

After `hw_emu` or `hw` xclbins exist, run the same smoke cases with:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_pure_pipeline_host.sh \
  --out-dir .tmp_build/pure_pipeline_host_stage0

./scripts/run_pure_pipeline_smoke.sh \
  --target hw_emu \
  --out-dir results/pure_pipeline_hw_emu_smoke_<label> \
  --timeout 1800

./scripts/run_pure_pipeline_smoke.sh \
  --target hw \
  --out-dir results/pure_pipeline_hw_smoke_<label> \
  --timeout 600
```

## HW_EMU And HW Build Commands

The command scripts for the next two builds are generated and ready to hand to
the long-running build process:

```bash
cd /home/chuxiao/grasu-regraph-integration

.tmp_build/pure_pipeline_hw_emu_stage0/compile_commands.sh \
  2>&1 | tee .tmp_build/pure_pipeline_hw_emu_stage0/compile_commands_after_12b4fe7.log
.tmp_build/pure_pipeline_hw_emu_stage0/link_command.sh \
  2>&1 | tee .tmp_build/pure_pipeline_hw_emu_stage0/link_command_after_12b4fe7.log

.tmp_build/pure_pipeline_hw_stage0/compile_commands.sh \
  2>&1 | tee .tmp_build/pure_pipeline_hw_stage0/compile_commands_after_12b4fe7.log
.tmp_build/pure_pipeline_hw_stage0/link_command.sh \
  2>&1 | tee .tmp_build/pure_pipeline_hw_stage0/link_command_after_12b4fe7.log
```

Expected xclbin paths after successful link:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin
```

## Not Yet True

The current baseline still has these gaps:

- `hw_emu` and `hw` command scripts are generated, but the pure-pipeline
  xclbins have not been produced or validated yet.
- The timing above is `sw_emu` timing and is useful for control-flow evidence,
  not performance claims.
- Spine still needs to be rerun or remapped on exactly the same graph files
  before a full four-way performance table is claim-ready.

## Start-State Evidence Command

Run this before major pure-hardware changes and after each stable milestone:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/collect_pure_hw_start_state.sh \
  --out-dir .tmp_build/pure_hw_start_state_20260714
```

The command writes:

```text
.tmp_build/pure_hw_start_state_20260714/environment.env
.tmp_build/pure_hw_start_state_20260714/git_state.txt
.tmp_build/pure_hw_start_state_20260714/artifact_hashes.tsv
.tmp_build/pure_hw_start_state_20260714/source_fingerprints.tsv
.tmp_build/pure_hw_start_state_20260714/summary.md
```

Large xclbins and build directories are not copied into git. The script records
hashes and paths instead.

## Interface Facts From Current Source

GraSU update side:

- The final graph lives in four PMA buffers passed as `data_device_1` through
  `data_device_4` in `GraSU/GraSU/src/host.cpp`.
- The four PMA writers are two `process_cache` CUs and two `process_ddr` CUs:
  `process_cache_1`, `process_cache_2`, `process_ddr_1`, `process_ddr_2`.
- Each PMA segment has `SEGMENT_SIZE = 16` 32-bit destination slots.
- A destination with bit 31 set is empty/deleted.
- Host `merge_data` reconstructs `(src, dst)` by scanning `row_offset` and
  choosing one of the four PMA buffers from the segment index.

ReGraph compute side:

- The current SSSP build uses `PARTITION_SIZE = 65536`,
  `LITTLE_KERNEL_NUM = 1`, `BIG_KERNEL_NUM = 1`, and uncompressed edge input.
- `littleKernelScatterGather` and `bigKernelScatterGather` consume one
  `edge_burst_dt` per iteration, where `edge_burst_dt` contains 8
  `(src, dst)` pairs.
- For weighted SSSP, the packed destination word stores local destination bits
  in `[18:0]`, weight in `[30:19]`, and dummy in bit 31.
- For unit-weight SSSP, the adapter should pack weight `1` and use dummy
  records for empty PMA slots or final padding.

## First Implementation Slice

The first hardware slice should target `V <= 65536`, unit-weight SSSP, one
destination partition, and the little ReGraph GS path. This keeps the initial
correctness proof small while preserving the final dataflow shape.

Planned dataflow:

```text
GraSU bin_search/dispatch
  -> process_cache_1/process_cache_2/process_ddr_1/process_ddr_2
  -> four completion tokens
  -> pma_to_regraph_adapter
  -> AXI4-Stream edge_burst_dt, 8 edges/burst
  -> ReGraph littleKernelScatterGather stream-input variant
  -> kernelLittleGSMerger
  -> kernelApply
  -> kernelHBMWrapper
```

The first adapter can emit every PMA slot, including dummy records for empty
slots. That means `part_edge_num` can be the PMA capacity known by the host at
launch time, avoiding a new dynamic metadata return path in the first version.
It is conservative for performance, but it removes graph D2H/H2D and proves
correctness against the real PMA.

Later optimization can compact valid PMA edges and pass a real edge count or
partition descriptor through a metadata stream.

## Required Source Changes

Current integration-branch seed code:

```text
kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp
```

Lightweight syntax check:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_pma_to_regraph_adapter.sh
```

This check only proves that the adapter source parses against the Vitis HLS C++
headers. It is not an XO compile, link, or hardware correctness proof.

GraSU kernel changes:

- Add one AXI4-Stream completion-token output to each PMA writer kernel.
- Emit exactly one token after the PMA writer has completed all writes.
- Applied in local GraSU branch `codex/explore-grasu-u55c` as commit
  `25d1bb5 Add optional PMA writer completion tokens`.
- Current patch:
  `patches/grasu_completion_tokens_20260714.diff`
- Lightweight syntax check:
  `./scripts/check_grasu_completion_tokens.sh`
- Current check evidence:
  `.tmp_build/grasu_completion_token_check_20260714_stage2`
- HLS semantics:
  - `hls::stream<ap_axiu<32,0,0,0>> &done`
  - `#pragma HLS INTERFACE axis port=done`
  - write the token only after the final PMA store loop or DDR process loop.

Adapter kernel:

- New HLS kernel, likely owned by this integration repository or patched into
  a scratch build tree.
- Inputs:
  - four PMA `m_axi` ports, same device buffers as GraSU's `data_device_1..4`
  - `row_offset` device buffer
  - `node_count`, `pma_slot_count`, `source_vertex`
  - four completion-token AXI streams
- Output:
  - AXI4-Stream edge bursts carrying 8 edges/burst
- HLS semantics:
  - read all four completion tokens before scanning PMA
  - use `#pragma HLS PIPELINE II=1` on the burst emission loop
  - use fixed 512-bit stream payload compatible with `edge_burst_dt`
  - pack unit weight as `1`
  - mark dummy lanes with bit 31 in src or encoded dst

ReGraph kernel changes:

- Add a stream-input variant of the little scatter-gather kernel or guard the
  current `m_axi part_edge_array` path behind a compile-time switch.
- Current integration-owned stream wrapper:
  `kernels/regraph_stream_little_gs/little_gs_stream.cpp`
- Lightweight syntax check:
  `./scripts/check_regraph_stream_little_gs.sh`
- HLS semantics:
  - `hls::stream<edge_burst_pkt> &edge_burst_in`
  - `#pragma HLS INTERFACE axis port=edge_burst_in`
  - keep existing scatter/gather/apply streams unchanged after the edge reader.

Host changes:

- Create one OpenCL context/program from the combined xclbin.
- Allocate GraSU PMA buffers once and pass the same `cl::Buffer` objects to the
  adapter without migrating graph data back to host.
- Enqueue GraSU, adapter, ReGraph, and apply/HBM wrapper with event profiling.
- Record separate timing fields: GraSU, barrier, adapter/ReGraph, apply, and
  unified pipeline E2E.
- Keep the existing host-conversion and zero-cost handoff baselines on the same
  generated inputs.

Connectivity changes:

- Add stream connections from each PMA writer to the adapter.
- Add stream connection from adapter to the ReGraph stream-input GS kernel.
- Keep ReGraph internal connections from GS to merger/apply/HBM wrapper.
- Keep all kernels in one xclbin.

Generate the first pure-pipeline build commands without running Vitis:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/prepare_pure_hw_pipeline_build.sh \
  --target sw_emu \
  --build-root .tmp_build/pure_pipeline_sw_emu_stage0
```

The generated `compile_commands.sh` rebuilds every XO used by the first
pipeline xclbin from current local source: GraSU `bin_search`, `dispatch`,
tokenized `process_cache`, tokenized `process_ddr`, ReGraph apply/HBM/merger/big
GS kernels, `pma_to_regraph_adapter`, and `lksg_stream`. The generated
`link_command.sh` links those XOs into one xclbin and adds the completion-token
and adapter-to-ReGraph stream connections.

## Correctness Matrix

The first matrix remains:

```text
chain
hot-source
spread
hot-destination
```

For every case:

- `V <= 65536`
- unit edge weight
- same input files for pure pipeline, host baseline, zero-cost handoff baseline,
  and Spine comparison
- CPU oracle checks final SSSP distances
- record source fingerprints, xclbin hash, command, log path, result path

## Commit And Push Discipline

Use this branch for all pure pipeline work:

```bash
cd /home/chuxiao/grasu-regraph-integration
git switch codex/pure-hw-pipeline
```

After each stable step:

```bash
git status --short
git add <changed-files>
git commit -m "<short milestone>"
git push -u origin codex/pure-hw-pipeline
```

Do not force push. Build products and raw logs stay out of git unless they are
small curated evidence files; large artifacts should be represented by paths
and SHA-256 hashes.
