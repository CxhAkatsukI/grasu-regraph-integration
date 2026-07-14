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
- Step 0 adapter launch waits on the profiled `pma_completion_barrier` event;
  later SSSP supersteps replay the already-stable PMA graph without waiting for
  one-shot GraSU tokens.
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

## Same-Input Spine Smoke

Spine was also run on the same edge files exported by GraSU's actual PMA image.
This gives a first three-way smoke table: host-conversion baseline,
zero-cost handoff baseline, and Spine. The pure-pipeline column is still
`sw_emu` only.

Important setup note: this edge-file host must be paired with the split-CU
Spine xclbin and `SPINE_PARTITIONED_SPLIT=1`. A non-split xclbin fails because
`spine_partconv_rdmaint_kernel` and `spine_partconv_compute_kernel` are absent;
non-split mode with the split host can also fail active-bin validation.

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
source /data/yxx/tools/xilinx/Vitis/2024.1/settings64.sh
export XILINX_XRT=/opt/xilinx/xrt
export LD_LIBRARY_PATH=/opt/xilinx/xrt/lib:${LD_LIBRARY_PATH:-}
export PATH=/opt/xilinx/xrt/bin:${PATH}

SPINE_PARTITIONED_SPLIT_VALUE=1 \
./scripts/run_spine_edge_file_sweep.sh \
  --chain-root results/grasu_regraph_smoke_device_export_combined_hw_stage1 \
  --out-root results/spine_edge_file_smoke_hw_stage2_split_xclbin \
  --spine-host .tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge \
  --spine-xclbin /data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
  --timeout 300 \
  --no-source-xrt
```

Evidence:

```text
summary: results/spine_edge_file_smoke_hw_stage2_split_xclbin/summary.tsv
sha256:  9188dc379ce2c68d6bd2ec9b29d222c94f0e02503abb9c474dd4141935137409

Spine edge-file host sha256:
  df0aa0dca3eddb09aa58805fe7bb1c65e4c1a7484ab8ae6ca230c11bbff90bdd
Spine split xclbin sha256:
  69145517738cc1ffff95e91c24393260c346ac683db9eef2989bbc1bdb7a3469
```

Result:

```text
tiny_chain_v16       PASS input_edges=15 spine_kernel_e2e_ms=1.58718 errors=0
tiny_star_v16_u12    PASS input_edges=28 spine_kernel_e2e_ms=1.57177 errors=0
tiny_spread_v16_u8   PASS input_edges=24 spine_kernel_e2e_ms=1.59870 errors=0
tiny_hotdst_v64_u32  PASS input_edges=95 spine_kernel_e2e_ms=2.26057 errors=0
```

Spine-vs-zero-cost comparison:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 scripts/compare_spine_chain_summaries.py \
  --chain-summary results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv \
  --spine-summary results/spine_edge_file_smoke_hw_stage2_split_xclbin/summary.tsv \
  --out-dir results/spine_vs_grasu_regraph_smoke_same_input_hw_stage0
```

Comparison artifacts:

```text
ddea6bde1d2b69180db197aa72a8ab12c7c531d82b0b7d8c0f43bb4b8f1a64ce  results/spine_vs_grasu_regraph_smoke_same_input_hw_stage0/comparison.tsv
1ca8f862d9c1502134b361f9f1181757ad6cec52a6534f91e592a22fce111689  results/spine_vs_grasu_regraph_smoke_same_input_hw_stage0/comparison.md
```

Three-way smoke table:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 scripts/summarize_pure_pipeline_smoke.py \
  --host-summary results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv \
  --spine-summary results/spine_edge_file_smoke_hw_stage2_split_xclbin/summary.tsv \
  --pure-summary results/pure_pipeline_sw_emu_smoke_stage35/summary.tsv \
  --pure-env results/pure_pipeline_sw_emu_smoke_stage35/run.env \
  --out-dir results/pure_pipeline_smoke_compare_stage1_with_spine
```

Three-way artifacts:

```text
9a4a3a6f2005b8c4b830bd2523f432d366e59616c69168d78f72c5b7ba86759d  results/pure_pipeline_smoke_compare_stage1_with_spine/comparison.tsv
c1125dd3d8b3c018618a57c2b75b06a13c51418f352a82ef699064e1f37c9582  results/pure_pipeline_smoke_compare_stage1_with_spine/comparison.md
```

Current smoke-level observation:

```text
tiny_chain_v16       zero_cost_ms=6.127929 spine_kernel_e2e_ms=1.58718 zero_cost/spine=3.860891
tiny_star_v16_u12    zero_cost_ms=2.526626 spine_kernel_e2e_ms=1.57177 zero_cost/spine=1.607504
tiny_spread_v16_u8   zero_cost_ms=5.743649 spine_kernel_e2e_ms=1.59870 zero_cost/spine=3.592700
tiny_hotdst_v64_u32  zero_cost_ms=6.202223 spine_kernel_e2e_ms=2.26057 zero_cost/spine=2.743654
```

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

## Build Wrapper And Evidence

As of this stage, the long `hw_emu` and `hw` builds can be run through a wrapper
that records source state, command hashes, XO hashes, xclbin hash, and log
paths. This does not change the generated Vitis commands; it makes the build
run auditable.

Status-only check:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label status_8e19745 \
  --status-only
```

Current status evidence:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_status_8e19745.env
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_status_8e19745_evidence.tsv

5a8cbc2ef590e7fa68c12956833e67a173114a9af8134c07b922bea15d967335  build_status_8e19745.env
e01867430bc5414213da34a3c33f827dc0c565a09a73ac5798f5bcb3e3f7fd56  build_status_8e19745_evidence.tsv
```

The evidence currently records the generated command script hashes and confirms
that the `hw_emu` xclbin is still missing:

```text
d72d8ca7272f7ee07b924979d2048894c0376bf2c3985ba427b17e80395a0235  manifest.env
d471282a9f92c38759f14600f6c0e53a53a5481790051a82f06f920ad4ef4a77  inputs.tsv
d2a071aebca70a850852d8a42dd3e45546400be714fea41475c5f25a11df57a4  compile_commands.sh
9faf8e9ef27add5f802ac1b95cbc793161c4fee9e912f3f24c8dc6ad5827ece4  link_command.sh
MISSING                                                           grasu_regraph_pure_pipeline.hw_emu.xclbin
```

Recommended `hw_emu` build command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label after_8e19745 \
  --require-idle
```

Recommended `hw` build command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_build.sh \
  --target hw \
  --label after_8e19745 \
  --require-idle
```

The wrapper writes:

```text
.tmp_build/pure_pipeline_<target>_stage0/run_logs/build_<label>.env
.tmp_build/pure_pipeline_<target>_stage0/run_logs/build_<label>_evidence.tsv
.tmp_build/pure_pipeline_<target>_stage0/run_logs/compile_<label>.log
.tmp_build/pure_pipeline_<target>_stage0/run_logs/link_<label>.log
```

Monitor a long-running build with:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/monitor_pure_pipeline_build.sh \
  --target hw_emu \
  --tail-lines 20
```

Current monitor evidence:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_20260714_181831.txt
sha256: 187208c542a0cf7377dc4ceff761e7bb99a0f626de6d7edd3612b8afd1cea510
```

Current monitor result:

```text
target=hw_emu
out_xclbin=.../grasu_regraph_pure_pipeline.hw_emu.xclbin
out_xclbin_status=MISSING
matching_processes=none
latest_compile_log=compile_dryrun_fa17c35.log
latest_link_log=MISSING
```

## Requirement Audit Snapshot

The current hard-requirement status can be regenerated with:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 scripts/audit_pure_pipeline_status.py \
  --out-dir results/pure_pipeline_requirement_audit_276d040
```

This audit reads the existing smoke summaries, xclbin paths, command scripts,
build/finalize evidence, and source-level stream/barrier checks. It writes:

```text
results/pure_pipeline_requirement_audit_276d040/audit.json
results/pure_pipeline_requirement_audit_276d040/audit.md

cc8c085f5ce2f147c3337c9053dff7ccd55098b150c859d36aa5bd7d0c8a0572  audit.json
5fdd78a17c7241879ae72c6cd8bcccfda53c7454f1dad939302b5b14bc48d4f1  audit.md
```

Current audit status counts:

```text
proven: 1
partial: 8
blocked_by_missing_artifact: 1
```

The only fully proven hard requirement at this point is preserving the accepted
host baseline and zero-cost handoff baseline on identical smoke inputs. The
main blocked item is the final cross-target correctness matrix: `sw_emu` passes
all four smoke families, but pure-pipeline `hw_emu` and `hw` xclbins, smoke
summaries, and final timing evidence are still missing. The audit result is
local under ignored `results/`; rerun it after each new build/finalize step to
refresh hashes and statuses.

## V65536 Boundary Prepare Check

The first-stage design target is `V <= 65536`, but the fast smoke correctness
suite intentionally uses tiny graphs. To keep the boundary capacity check
reproducible without making every `sw_emu` run enormous, the workload generator
now has a `boundary` preset and the pure-pipeline host has a `--prepare-only`
mode.

Boundary preset:

```text
boundary_star_v65536_u4096    hot-source  V=65536 updates=4096 supersteps=2
boundary_spread_v65536_u4096  spread      V=65536 updates=4096 supersteps=16
```

Generate the boundary inputs:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/generate_sssp_benchmark_workloads.py \
  --preset boundary \
  --out-root workloads/sssp_benchmark_boundary
```

Run the host-side boundary preparation check:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_pure_pipeline_host.sh \
  --out-dir .tmp_build/pure_pipeline_host_stage0

./scripts/run_pure_pipeline_prepare_check.sh \
  --preset boundary \
  --out-dir results/pure_pipeline_prepare_boundary_<label> \
  --timeout 240
```

This check does not load an xclbin. It validates graph ingest, the
`1 <= V <= 65536` bound, GraSU PMA packing, row-offset/binary metadata sizing,
and the CPU oracle. The runner records `PURE_PIPELINE_INPUT` and
`PURE_PIPELINE_PREP` lines per case. It is capacity evidence for the host/PMA
preparation path, not a replacement for the required pure `hw_emu` and `hw`
correctness runs.

After this evidence exists, rerun the requirement audit. Requirement 6 should
remain `partial` until the boundary input is also validated on pure hardware,
but its gap should change from "no V=65536 evidence" to "hardware boundary
execution still missing".

Clean evidence after commit:

```text
57f02679c914c6147019d1b9ea798088d9891e34
```

Boundary prepare command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/build_pure_pipeline_host.sh \
  --out-dir .tmp_build/pure_pipeline_host_stage0

./scripts/run_pure_pipeline_prepare_check.sh \
  --preset boundary \
  --out-dir results/pure_pipeline_prepare_boundary_after_57f0267 \
  --timeout 240
```

Boundary prepare evidence:

```text
results/pure_pipeline_prepare_boundary_after_57f0267/summary.tsv
results/pure_pipeline_prepare_boundary_after_57f0267/run.env
workloads/sssp_benchmark_boundary/manifest.tsv

bd59ef3b2a7013b6efe871102f1e31072b29533857fbbaf33155d1132206b20d  summary.tsv
e8323cf44ff4d7093484509fc922be3f15398ea6215ed2420839198de770f765  run.env
e8110d3b222ab35f3ca27a646128e4b864d6dbfd5450dacc79e0ee6f23170a62  manifest.tsv
e7bcd78b94e0cdf7bac3af4f3f07f035cc888419e99cb1b7f4d1eb4d5d99ed51  pure_pipeline_host
```

Boundary result:

```text
boundary_star_v65536_u4096    PASS V=65536 final_edges=69632 pma_slots=1052672 row_offset_words=65537 binary_segments=65792
boundary_spread_v65536_u4096  PASS V=65536 final_edges=69632 pma_slots=1048576 row_offset_words=65537 binary_segments=65536
```

Updated requirement audit from the same clean commit:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 scripts/audit_pure_pipeline_status.py \
  --out-dir results/pure_pipeline_requirement_audit_after_57f0267
```

```text
ea381e55c4b4ff045650a3275a247f884e8ad555165590e00133d74a82b85951  audit.json
daea9cebd4d1b3b6ddbf683a47c2f2d54c34d867fb71625ee6d80497726fab72  audit.md

Dirty: False
proven: 1
partial: 8
blocked_by_missing_artifact: 1
```

The status count is unchanged, but requirement 6 now has concrete `V=65536`
prepare evidence. Its remaining gap is specifically pure `hw_emu/hw` boundary
execution.

Current boundary rerun after the event-dependency barrier commit:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_prepare_check.sh \
  --preset boundary \
  --out-dir results/pure_pipeline_prepare_boundary_after_25c553a
```

Evidence:

```text
25c553a427ad5079b1eda3cbbbee8185bbb12eca  source commit

fed191c8142ca36e49f0e5f7902d694693a76b11b4c014df5a59d9224793b95b  results/pure_pipeline_prepare_boundary_after_25c553a/summary.tsv
1e7a4c1a999a223c393121b55f4609e576a5c40aa3d86fa10309110a5fd1a512  results/pure_pipeline_prepare_boundary_after_25c553a/run.env
e8110d3b222ab35f3ca27a646128e4b864d6dbfd5450dacc79e0ee6f23170a62  workloads/sssp_benchmark_boundary/manifest.tsv
cb40efbffe3a091be8a8bffe03c2ee364c794a2cddb315a0571601b38c2cad5d  .tmp_build/pure_pipeline_host_stage0/pure_pipeline_host
```

Result:

```text
boundary_star_v65536_u4096    PASS V=65536 final_edges=69632 pma_slots=1052672 row_offset_words=65537 binary_segments=65792
boundary_spread_v65536_u4096  PASS V=65536 final_edges=69632 pma_slots=1048576 row_offset_words=65537 binary_segments=65536
```

Updated audit:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/audit_pure_pipeline_status.py \
  --out-dir results/pure_pipeline_requirement_audit_after_boundary_25c553a
```

```text
f772eb61f22896e6aff26ed0f3522ddc7cdcfdf318bfdc0eb19434f8d73c320d  audit.json
68033ce91bf9d1f97fad19019b884257dda5c20edee78278903aeff265d60608  audit.md

Dirty: False
proven: 1
partial: 8
blocked_by_missing_artifact: 1
```

Current boundary rerun after the idle-guard/audit-command updates:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_prepare_check.sh \
  --preset boundary \
  --out-dir results/pure_pipeline_prepare_boundary_after_ca20b9c \
  --timeout 120
```

Evidence:

```text
ca20b9c9689a199d49054b7c24b60e876b2412c4  source commit

2dea9d5ad149e6c71162f8e05329e6bcbfb6761b58649bac909009c6bd7fb65e  results/pure_pipeline_prepare_boundary_after_ca20b9c/summary.tsv
d1488c75cec604da265ae2515b35080084daafcfcbfc16a55ad64c7b56555dea  results/pure_pipeline_prepare_boundary_after_ca20b9c/run.env
e8110d3b222ab35f3ca27a646128e4b864d6dbfd5450dacc79e0ee6f23170a62  workloads/sssp_benchmark_boundary/manifest.tsv
cb40efbffe3a091be8a8bffe03c2ee364c794a2cddb315a0571601b38c2cad5d  .tmp_build/pure_pipeline_host_stage0/pure_pipeline_host
```

Result:

```text
boundary_star_v65536_u4096    PASS V=65536 final_edges=69632 pma_slots=1052672 row_offset_words=65537 binary_segments=65792
boundary_spread_v65536_u4096  PASS V=65536 final_edges=69632 pma_slots=1048576 row_offset_words=65537 binary_segments=65536
```

## Profiled Completion Barrier Slice

The initial pure-pipeline runner waited for the four GraSU PMA writer tokens
inside `pma_to_regraph_adapter`, which made `barrier_ms` unmeasurable as a
separate XRT event. The current source splits this into an independent
`pma_completion_barrier` kernel:

```text
process_cache_1.completion_token \
process_ddr_1.completion_token   -> pma_completion_barrier -> barrier_event
process_cache_2.completion_token /
process_ddr_2.completion_token  /

barrier_event -> host wait list for step-0 adapter enqueue
```

The host now creates `pma_completion_barrier:{pma_completion_barrier_1}` from
the same OpenCL program/context, enqueues it once after GraSU launch, and records
its event duration as `barrier_ms`. The adapter no longer consumes a barrier
token stream. Instead, step 0 is enqueued with an OpenCL wait list containing
`barrier_event`; later supersteps replay the already-stable PMA graph without
waiting for one-shot GraSU tokens.

Source files:

```text
kernels/pma_completion_barrier/pma_completion_barrier.cpp
kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp
tools/pure_pipeline_host.cpp
scripts/prepare_pure_hw_pipeline_build.sh
```

Lightweight checks:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_pma_to_regraph_adapter.sh \
  --out-dir .tmp_build/pma_to_regraph_adapter_check_barrier_stage0
./scripts/check_pma_completion_barrier.sh \
  --out-dir .tmp_build/pma_completion_barrier_check_stage0
./scripts/build_pure_pipeline_host.sh \
  --out-dir .tmp_build/pure_pipeline_host_stage0
```

Evidence:

```text
55eda7df87478f074b59fb630dd5b8e2e0cca039  source commit

7e650de096dedddcd369b6ec864fe6c9e78f5a288a759642f30c871c0dd17aa0  .tmp_build/pma_to_regraph_adapter_check_after_55eda7d/SHA256SUMS
23c103f01e25d3c13a5c2783fb2d07d7cf723b3501f4becfb4a0bab6d02a23f1  .tmp_build/pma_completion_barrier_check_after_55eda7d/SHA256SUMS
d44e9d7781fad21b60f48fb0d27abbefd3f5d9d130f0086ec19ff306e609c65d  .tmp_build/pure_pipeline_host_stage0/pure_pipeline_host
```

Regenerated `hw_emu` command script hashes:

```text
163faf2095038f4c7e4b5074000943bfe30c1e3e78440224d7960becadf5dd18  .tmp_build/pure_pipeline_hw_emu_stage0/compile_commands.sh
e8ba03b8f222ed81b411db3b279007a761f33e909b9799dfff86bb2a4888d971  .tmp_build/pure_pipeline_hw_emu_stage0/link_command.sh
```

The generated link config now contains:

```text
stream_connect=process_cache_1.completion_token:pma_completion_barrier_1.done0:16
stream_connect=process_ddr_1.completion_token:pma_completion_barrier_1.done1:16
stream_connect=process_cache_2.completion_token:pma_completion_barrier_1.done2:16
stream_connect=process_ddr_2.completion_token:pma_completion_barrier_1.done3:16
```

The earlier `done_out -> adapter.done` stream form was superseded because it
made the sw_emu bring-up harder to reason about. The active implementation uses
the barrier kernel only as a profiled event and lets XRT enforce the adapter
launch dependency.

Requirement audit after this source change:

```text
c4a90c2d4b437ca60916adb60b187d04c3a711615b8d654a156994e2fc0f61f4  audit.json
09a9c2e654a68547d9286ad18279a9a46296ab417428750485c0a04ae28ebc9c  audit.md

Dirty: False
proven: 1
partial: 8
blocked_by_missing_artifact: 1
```

The audit count is unchanged because rebuilt `sw_emu/hw_emu/hw` xclbins are
still missing. The important difference is that requirement 8 now has a
source-level profiled barrier event; the next validation step is to rebuild and
rerun the pure-pipeline smoke so `barrier_ms` becomes measured evidence instead
of source intent.

## Event-Dependency SW_EMU Smoke

After switching the barrier to an event dependency, the first sw_emu rebuild
still appeared to hang around ReGraph apply/merge. The root cause was in the
generated compile command for the integration-owned stream-input little-GS
wrapper: it did not pass `-DSW_EMU`, so `lksg_stream` missed ReGraph's
sw_emu-specific `DATAFLOW disable_start_propagation` path. The generated build
script now passes the target define to:

```text
pma_completion_barrier
pma_to_regraph_adapter
lksg_stream
```

Rebuild command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_build.sh \
  --target sw_emu \
  --label eventdep_debug_stage0 \
  --prepare
```

Smoke command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_smoke.sh \
  --target sw_emu \
  --out-dir results/pure_pipeline_sw_emu_smoke_eventdep_debug_stage0 \
  --timeout 180
```

Evidence:

```text
b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862  .tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
56457940c0be89ddfa6592f985b604d174d2730753d32feb5ebb241bdb547d77  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/build_eventdep_debug_stage0.env
397f75cf624fe28fa8d3a47ebd1ab95202bb10d658d74feb702f80e9ba1d67ac  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/build_eventdep_debug_stage0_evidence.tsv
a5e3e432e91c5020e9e87cdff511eaf4ae33bee638b6bc883e7e759341675fe7  results/pure_pipeline_sw_emu_smoke_eventdep_debug_stage0/summary.tsv
2c0ae9e325df034d9b7f740ebf011e40a2e9c839b67055aeb89c6fee8f6493d4  results/pure_pipeline_sw_emu_smoke_eventdep_debug_stage0/run.env
```

Smoke results:

```text
tiny_chain_v16       PASS  barrier_ms=0.288238  event_e2e_ms=5970.182599
tiny_star_v16_u12    PASS  barrier_ms=0.265498  event_e2e_ms=761.096521
tiny_spread_v16_u8   PASS  barrier_ms=0.260708  event_e2e_ms=5915.480553
tiny_hotdst_v64_u32  PASS  barrier_ms=0.187585  event_e2e_ms=6139.775744
```

Updated requirement audit:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/audit_pure_pipeline_status.py \
  --out-dir results/pure_pipeline_requirement_audit_eventdep_debug_stage0
```

```text
e73e576ee7563bb3d9cb1bf41dec7db3cb8e21a9900efa0d6815a8cf09de6329  audit.json
a93185747661ab88cb73554a76c4cbd0bcc8b9d7d47f9e995cef57fce8ba7e06  audit.md

proven: 1
partial: 8
blocked_by_missing_artifact: 1
```

The long-build command scripts were also regenerated without launching v++:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label eventdep_debug_stage0 \
  --prepare \
  --status-only
./scripts/run_pure_pipeline_build.sh \
  --target hw \
  --label eventdep_debug_stage0 \
  --prepare \
  --status-only
```

```text
374ab45b772bc3d00711288bbbf14b2157fd8de324cdd4dfd70a38fb83132ab7  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_eventdep_debug_stage0.env
c66ab35cb423e026b43675e27137bd23ba2633130345bcbd48b8706959d1ff88  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_eventdep_debug_stage0_evidence.tsv
163faf2095038f4c7e4b5074000943bfe30c1e3e78440224d7960becadf5dd18  .tmp_build/pure_pipeline_hw_emu_stage0/compile_commands.sh
e8ba03b8f222ed81b411db3b279007a761f33e909b9799dfff86bb2a4888d971  .tmp_build/pure_pipeline_hw_emu_stage0/link_command.sh
6bcf1162146767e5c371aea2e76f5b3bbdb8e3c38acb79948ff83a310ed7db99  .tmp_build/pure_pipeline_hw_stage0/run_logs/build_eventdep_debug_stage0.env
be2618d72ad15db3850a54b3c0b9c9868234a99124e00e08a22edc53e4de0d36  .tmp_build/pure_pipeline_hw_stage0/run_logs/build_eventdep_debug_stage0_evidence.tsv
c6f161389358532c001f217d433067c173ac3984b671e5f1a1fbfec19277a4cd  .tmp_build/pure_pipeline_hw_stage0/compile_commands.sh
d6488813e0ed366a7fb0ef052b5c865f50190fe9ff9a37af3a6511336f1b6d1e  .tmp_build/pure_pipeline_hw_stage0/link_command.sh
```

This means the sw_emu correctness and profiled-barrier timing evidence are now
real, while pure `hw_emu` and `hw` xclbins/smokes remain the blocking artifacts.

## Long-Build Preflight Monitor

The pure-pipeline monitor now records more than current-build artifacts. It also
captures host disk/memory state and unrelated Vitis/Vivado processes so a long
`hw_emu` or `hw` build can be interpreted in context.

Preflight command before launching the pure `hw_emu` build:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/monitor_pure_pipeline_build.sh \
  --target hw_emu \
  --tail-lines 20 \
  --out-file .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_pre_hwemu_after_1a1d8d8.txt
```

Evidence:

```text
c70a4493cac3135dce4c83c0b2607ff2781d6f9ef025ca2bd2e52fb193556424  scripts/monitor_pure_pipeline_build.sh
bb7dd270a15726c30d4060fbea56960c627d4a3a0b59765fc3c59898d5d144ab  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_pre_hwemu_after_1a1d8d8.txt
```

Current observation from that report:

```text
pure pipeline matching_processes: none
pure hw_emu xclbin: MISSING
/tmp available: 2.2G
/data available: 26T
other_vitis_vivado_processes: active unrelated Spine hw/vpl/vivado process tree
```

The generated pure-pipeline scripts set `TMPDIR/TMP/TEMP` under the build root,
so `/tmp` pressure is not the main blocker. The practical reason not to launch
the pure `hw_emu` build in the same moment is resource contention with the
active unrelated Spine hardware implementation.

The build wrapper now also has an active guard:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label after_<commit> \
  --require-idle
```

With `--require-idle`, the script scans for active Vitis/Vivado processes before
executing compile/link. If any are found, it writes an idle-check report and
exits with code `3` instead of starting a competing build.

For unattended launch, the same wrapper can wait for the machine to become
idle before starting:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label after_<commit> \
  --wait-idle 7200 \
  --idle-poll 60
```

`--wait-idle` implies `--require-idle`. If Vitis/Vivado processes are still
active when the timeout expires, the script exits with code `3` and leaves the
latest idle-check report in the build root.

Guard regression while the unrelated Spine `hw` link was active:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +e
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label idle_guard_check \
  --require-idle \
  --dry-run \
  --skip-compile \
  --skip-link
echo "idle_guard_rc=$?"
```

Evidence:

```text
idle_guard_rc=3
2999e549c21ef86eb67f892888ee35e9e2556a01f43dae5a5fc03a0ce2080d5c  scripts/run_pure_pipeline_build.sh
afc13697844f7391caf7d6bfa9d3403f7130c5b81b22470548b28a612bd603c0  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/idle_check_idle_guard_check.txt
```

Process-name filtering refinement after this regression:

- `monitor_pure_pipeline_build.sh` now filters Vitis/Vivado activity primarily
  by `ps` `comm` name instead of substring matches over the whole command line.
  This avoids reporting the monitor's own `awk/ps` command as a build process.
- `run_pure_pipeline_build.sh --require-idle` uses the same process-name
  family and includes `vrs`, `xelab`, `xsim`, `xsimk`, `xsc`, `xvlog`,
  `xvhdl`, and `genericpcie*` workers.
- The report headers now distinguish the short process name from full args.

Recheck commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/monitor_pure_pipeline_build.sh
bash -n scripts/run_pure_pipeline_build.sh

./scripts/monitor_pure_pipeline_build.sh \
  --target hw_emu \
  --tail-lines 20 \
  --out-file .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_process_filter_after_ab81cd4.txt

set +e
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label idle_guard_comm_check2 \
  --require-idle \
  --dry-run \
  --skip-compile \
  --skip-link
echo "idle_guard_rc=$?"
```

Evidence:

```text
idle_guard_rc=3
6a423982ce768cfe4ddaebdb805cb8d894d778715e6ab993eb02a9b9e74e4f6b  scripts/monitor_pure_pipeline_build.sh
2dc8ffc1efa1d294fc62800c997a2a5c3606ec35dd8b61562e5229621cbae4b2  scripts/run_pure_pipeline_build.sh
794e806203ef9e5925a4f9638d5ded28f3cad894254a674bc5e9c84c950a6b4f  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_process_filter_after_ab81cd4.txt
31ee2d6d3328d13ca5a580f0ddfad0d01b84abf2bfc37efb908b9717bc5faf21  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/idle_check_idle_guard_comm_check2.txt
```

Current observation from the refined monitor:

```text
pure pipeline matching_processes: none
pure hw_emu xclbin: MISSING
other_vitis_vivado_processes: active unrelated Spine hw link plus vadd hw_emu probe
```

Wait-idle regression while the unrelated Spine `hw` link was still active:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +e
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label wait_idle_probe_1s \
  --wait-idle 1 \
  --idle-poll 1 \
  --dry-run \
  --skip-compile \
  --skip-link
echo "wait_idle_rc=$?"

./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --wait-idle nope \
  --dry-run \
  --skip-compile \
  --skip-link
echo "invalid_wait_rc=$?"
```

Evidence:

```text
wait_idle_rc=3
invalid_wait_rc=2
a2aec907715fd3aaf1b75da2c5aab374de0eedb9afd46708a83a28fdce8c8d1c  scripts/run_pure_pipeline_build.sh
d4302bd3bfeae47037e29ac9d3e384dce8fc26ae7805c47836652fb15be5c79f  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/idle_check_wait_idle_probe_1s.txt
5a47ff1d2c8f2ebc2443babe39dbc3fb5b1a891424f81b12ecc3fb42039a790f  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_wait_idle_probe_1s.env
c66ab35cb423e026b43675e27137bd23ba2633130345bcbd48b8706959d1ff88  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_wait_idle_probe_1s_evidence.tsv
```

## Staged Smoke Gate

The full requirement still needs all four smoke families on `sw_emu`, `hw_emu`,
and `hw`. For bring-up, however, the smoke runner now supports running a subset
first:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_smoke.sh \
  --target hw_emu \
  --case tiny_star_v16_u12 \
  --out-dir results/pure_pipeline_hw_emu_smoke_case_gate_after_<label> \
  --timeout 900
```

Supported filters:

```text
--case LIST       comma-separated case names; may be repeated
--family LIST     comma-separated family names; may be repeated
--max-cases N     stop after N selected cases
```

The requirement audit was updated to prefer the newest complete four-case smoke
summary. That prevents a later one-case bring-up gate from hiding the last full
four-family smoke evidence.

SW_EMU filter regression:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_smoke.sh \
  --target sw_emu \
  --case tiny_star_v16_u12 \
  --out-dir results/pure_pipeline_sw_emu_smoke_case_filter_check \
  --timeout 180

./scripts/audit_pure_pipeline_status.py \
  --out-dir results/pure_pipeline_requirement_audit_after_smoke_filter_check
```

Evidence:

```text
714287bc4c731f0b909e4f19e37e06cd37c7add5e22230d69005701aabcdd9e5  results/pure_pipeline_sw_emu_smoke_case_filter_check/summary.tsv
4a7e4cb470b7c6970f4ccddeaae4b1f2664202cea5a60e45b4feda5fab58ad4a  results/pure_pipeline_sw_emu_smoke_case_filter_check/run.env
c69673b8383746d141ec48947fa384a3ddb28af97fc9957d2ab151c584536868  results/pure_pipeline_requirement_audit_after_smoke_filter_check/audit.json
12b344ea04cd93ba8ccce0f0ec227d987a2de3859b6968eb1e2c20bcf0c8cebd  results/pure_pipeline_requirement_audit_after_smoke_filter_check/audit.md
```

The filtered run passed only `tiny_star_v16_u12`; the audit correctly kept the
complete `results/pure_pipeline_sw_emu_smoke_eventdep_debug_stage0/summary.tsv`
as the authoritative `sw_emu` smoke evidence.

## Post-Build Finalization

After a pure-pipeline xclbin is produced, run the finalization wrapper. It
collects artifact hashes, runs the smoke correctness suite, and generates the
same-input comparison against the current host/zero-cost and Spine baselines.
The wrapper can optionally run a single gate case first. The gate is only a
bring-up shortcut; after it passes, the wrapper still runs the full four-family
smoke suite.

Status-only check before the xclbin exists:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/finalize_pure_pipeline_build.sh \
  --target hw_emu \
  --label status_7623a8c \
  --status-only
```

Current status evidence:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/finalize_status_7623a8c.env
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/finalize_status_7623a8c_evidence.tsv

0909498c6c2a752dc22c0d6e880cd7c436f53fe63c7cef9b7c15b3d7f3004353  finalize_status_7623a8c.env
2fbfb988dee09b34ca6d5bdc8ec5fa68f30a2b3dddcb9092bdaad86a35c4f98b  finalize_status_7623a8c_evidence.tsv
```

The evidence currently records:

```text
ded281e1610545859ca5fcfdc4acfeecece6a1bad2805ba36ec98b0050814b06  pure_pipeline_host
MISSING                                                           grasu_regraph_pure_pipeline.hw_emu.xclbin
d72d8ca7272f7ee07b924979d2048894c0376bf2c3985ba427b17e80395a0235  manifest.env
d471282a9f92c38759f14600f6c0e53a53a5481790051a82f06f920ad4ef4a77  inputs.tsv
d2a071aebca70a850852d8a42dd3e45546400be714fea41475c5f25a11df57a4  compile_commands.sh
9faf8e9ef27add5f802ac1b95cbc793161c4fee9e912f3f24c8dc6ad5827ece4  link_command.sh
MISSING                                                           pure_pipeline_hw_emu_smoke_status_7623a8c/summary.tsv
MISSING                                                           pure_pipeline_hw_emu_compare_status_7623a8c/comparison.tsv
```

When the `hw_emu` xclbin exists, run:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/finalize_pure_pipeline_build.sh \
  --target hw_emu \
  --label after_7623a8c \
  --build-host \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

When the `hw` xclbin exists, run:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/finalize_pure_pipeline_build.sh \
  --target hw \
  --label after_7623a8c \
  --build-host \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

The finalization wrapper writes:

```text
.tmp_build/pure_pipeline_<target>_stage0/run_logs/finalize_<label>.env
.tmp_build/pure_pipeline_<target>_stage0/run_logs/finalize_<label>_evidence.tsv
results/pure_pipeline_<target>_smoke_gate_<label>/summary.tsv
results/pure_pipeline_<target>_smoke_<label>/summary.tsv
results/pure_pipeline_<target>_compare_<label>/comparison.tsv
results/pure_pipeline_<target>_compare_<label>/comparison.md
```

Gate dry-run regression, without requiring an xclbin:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/finalize_pure_pipeline_build.sh \
  --target hw_emu \
  --label gate_dryrun_check \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 45 \
  --timeout 123 \
  --dry-run
```

Evidence:

```text
69a29969a4e707c8580fb158ff515010148ac5f32520c85e65a9c61b6d809b27  scripts/finalize_pure_pipeline_build.sh
12744cc861cc96c92004cfada15ebedda24a2288fe08a2385842ae22d6810ab9  scripts/audit_pure_pipeline_status.py
d6170cea7d928d4c46f0272f09e0bb68c252073c5957bda6247015666f25721c  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/finalize_gate_dryrun_check.env
7a3244073b433f24b6a980b640638b1814b8d6bf7510dcd78918f76176add865  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/finalize_gate_dryrun_check_evidence.tsv
bac57a120c3aca4624699bf9c77f2671c08af795abd9b743b3b2f963538cfcce  /tmp/finalize_gate_dryrun_check.log
```

## Target Flow Wrapper

The target-flow wrapper strings the post-`sw_emu` target steps together:

```text
run_pure_pipeline_build.sh --wait-idle
  -> monitor_pure_pipeline_build.sh
  -> finalize_pure_pipeline_build.sh --gate-case ...
  -> audit_pure_pipeline_status.py
```

It does not hide or replace the lower-level commands; it prints each command and
lets the underlying wrappers record their normal logs, hashes, smoke summaries,
comparison files, and audit files.

Recommended `hw_emu` flow once the machine is idle enough to start:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_<commit> \
  --wait-idle 7200 \
  --idle-poll 60 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Dry-run regression, without starting Vitis:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label flow_dryrun_check \
  --wait-idle 1 \
  --idle-poll 1 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 45 \
  --timeout 123 \
  --dry-run
```

Evidence:

```text
2b8ec3aa8afbf153e3116f76684bd440887462091cd2ca2f3fcb2a103a647b2b  scripts/run_pure_pipeline_target_flow.sh
cff1fdc08c277f141d12f5f9e0565ff949dd47c4222f0b6b78e94510e7d7d54e  scripts/audit_pure_pipeline_status.py
96271bb06a330ee47a051ba958b4ed0c96e3aeb2066c6d5985f2aea09b912b98  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_flow_dryrun_check.env
b60698a253e72a7bb1cc280611fe43c3f471397fd7e9305da8fb47fc65bf1a16  /tmp/pure_target_flow_dryrun_check.log
```

The target-flow wrapper now runs a readiness preflight before the build step.
By default the preflight records active external Vitis/Vivado builders as a
warning, because `run_pure_pipeline_build.sh --wait-idle` is still responsible
for waiting until the machine is idle. Use `--strict-readiness` to fail before
the wait-idle phase when any unrelated builder is active.

Metadata-only regression, without compile/link/finalize/audit:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label flow_readiness_metadata_63d95c5 \
  --skip-build \
  --skip-finalize \
  --skip-audit \
  --monitor-tail 20
```

Strict-readiness regression while external builders are active:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label flow_readiness_strict_63d95c5 \
  --strict-readiness \
  --skip-build \
  --skip-finalize \
  --skip-audit
```

The strict command exits `3` with `ready=no`, `blocking_count=1`, and
`active_builders=FAIL related=0 external=10`.

Evidence:

```text
d389bd23d32aa5319bff8b1f86e43bb9503af64569f9ced7378561a5c706adfb  scripts/run_pure_pipeline_target_flow.sh
57615752e72f69eccca1df28bf18b37ce310ceb4d535269587e8e995eed4822f  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_flow_readiness_metadata_63d95c5.env
53b0c23199d7fa480ff1c9e603d42389675f514e66a6837736f3197a39d4c0cf  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_target_flow_flow_readiness_metadata_63d95c5.txt
c8ba5344b62e3d186dfff43da3cc55fe085498d8e92209c439261c91a2ed321b  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_flow_readiness_metadata_63d95c5.txt
7e02c3a6eaff756346fdfffd277e185a7a0048e263ceca512fd98410c0fc687e  /tmp/pure_target_flow_readiness_dryrun.log
f43f1f6e34cbef134ad2c6709a276aae385aa378c2b5ee81844aa775301c7ecf  /tmp/pure_target_flow_readiness_metadata.log
21a29e043c2b981e4c4d5584c96d38881f31833d9b5826930bfa28c00807b63b  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_target_flow_flow_readiness_strict_63d95c5.txt
8add304a6b4eb5bba3b9850639aa5ae4ea2c783b25d7d217f05ca262b8dd9695  /tmp/pure_target_flow_readiness_strict.log
```

Post-commit evidence after `da31403`:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_da31403 \
  --wait-idle 1 \
  --idle-poll 1 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 45 \
  --timeout 123 \
  --dry-run
./scripts/monitor_pure_pipeline_build.sh \
  --target hw_emu \
  --tail-lines 30 \
  --out-file .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_da31403.txt
./scripts/run_pure_pipeline_prepare_check.sh \
  --preset boundary \
  --out-dir results/pure_pipeline_prepare_boundary_after_da31403
./scripts/audit_pure_pipeline_status.py \
  --label after_da31403_boundary \
  --out-dir results/pure_pipeline_requirement_audit_after_da31403_boundary
```

Results:

```text
status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
boundary_star_v65536_u4096   PASS  V=65536 updates=4096 final_edges=69632 supersteps=2
boundary_spread_v65536_u4096 PASS  V=65536 updates=4096 final_edges=69632 supersteps=16
```

Evidence hashes:

```text
bd534ae7a921263233611146cef9ff0f5e1220f78cfae5a1a051ad836751f141  README.md
5af426c6651d87bc89088d75c268ff399ccca7a0ea45739ccc986878c2b40944  scripts/audit_pure_pipeline_status.py
8904d075df9f23fcc370481b636738ec38d1fa8991da3dfae223dce75c52849f  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_after_da31403.env
43e7deae79cde4009f68e72e6013b591916f09e9172b10370f7439570f216ee2  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_da31403.txt
9265b68c288a43df89ff016177c5656af551d2424cf2a02abe4f1f3fc35b3610  /tmp/pure_target_flow_after_da31403_dryrun.log
2958bfda8096571a651fd8394756c54784e0d9a1e3679fdf98fe6ac2f14ed8a7  results/pure_pipeline_prepare_boundary_after_da31403/summary.tsv
d102d8b5d165af32a3fb2a2f5d01dc6dc7edc1f2c3b173060360ba4e45707873  results/pure_pipeline_prepare_boundary_after_da31403/run.env
6ed78a476294ed5c0ee5120b230d59b63fc88aa262de9e2e7811853e7b196981  results/pure_pipeline_requirement_audit_after_da31403_boundary/audit.json
995214ab740654d6d0815e2e933ef9d4b90a83fca36c3af40aa9c11f1fdee7a1  results/pure_pipeline_requirement_audit_after_da31403_boundary/audit.md
```

The monitor found no matching pure-pipeline build process and no pure
`hw_emu` xclbin. It did find active external Spine `hw` and `hw_emu`
Vitis/Vivado jobs, so the pure `hw_emu` target flow should continue to wait for
idle before starting the long build.

## Build Readiness Gate

Before launching a long pure `hw_emu` or `hw` build, run:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_pure_pipeline_build_readiness.sh \
  --target hw_emu \
  --label readiness_strict_3e23632
```

The readiness gate does not start Vitis. It checks the generated manifest,
compile script, link script, Vitis settings file, build-root disk headroom,
`/tmp` headroom, expected xclbin path, and active Vitis/Vivado builders. A
strict run exits `0` only when the target is safe to start; it exits `3` when an
external or related builder is active.

Strict probe result on 2026-07-14 22:34 Asia/Shanghai:

```text
ready=no
blocking_count=1
active_builders=FAIL related=0 external=17
manifest=PASS
compile_commands=PASS
link_command=PASS
vitis_settings=PASS
out_xclbin=MISSING
build_root_fs=PASS free_gb=217.6 minimum_gb=100
tmp_fs=PASS free_gb=2.2 minimum_gb=1
```

This means the pure-pipeline build commands and local resources are ready, but
the machine is still occupied by unrelated Spine Vitis/Vivado jobs. The right
next action is still the wait-idle target flow, not a manual immediate Vitis
launch.

Evidence:

```text
21cffdceef9d4b2e7886e3769929fe572331d9d06a87c67fcbdd9c7486585aeb  scripts/check_pure_pipeline_build_readiness.sh
0a4304dc1a43c7d81ec3a05f0a6ac9f6bfd13a08945e6085b8211d25b89d5e24  scripts/audit_pure_pipeline_status.py
0252cf997b313657f15f017c28c9b91665ecc54edea95733a6d2df4b1d89787d  README.md
f6bf7f437351ff3ff4267d823830568e976c8c87c364704ea5d45d661959b057  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_readiness_strict_3e23632.txt
dc1d829282a96a68e51a0aa03e86d63bf0487263f692119bef5a027a032503cc  /tmp/pure_readiness_strict.log
e75533b9c0419ebda617fab8bd7052397d42ce1fe9ef03126ea6b9b26a01357f  results/pure_pipeline_requirement_audit_readiness_strict_audit_3e23632/audit.md
```

## Evidence Bundle Export

Use the bundle exporter to create a compact report directory from the latest
audit and the smoke comparison:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_after_08845bf_both_readiness/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_after_08845bf
```

The output directory contains:

```text
requirement_matrix.tsv
target_matrix.tsv
artifact_matrix.tsv
case_matrix.tsv
summary.md
bundle_manifest.json
```

Current bundle interpretation:

- `sw_emu` pure pipeline correctness is present.
- `hw_emu` and `hw` pure xclbins are absent.
- `hw_emu` and `hw` readiness reports both show generated command scripts and
  resources are ready, but active external Vitis/Vivado builders block launch.
- Host baseline, zero-cost handoff baseline, and Spine smoke comparison remain
  included on the same input cases.

Evidence:

```text
8598d516f8df3945cc39ff96919b2b2afbe080cb224238ab3fa5c1e59f105f94  scripts/export_pure_pipeline_evidence_bundle.py
f4c1e1a4c1b598057d2a94e9330ff2ffb931457f9355596381f7c828a0d03f57  results/pure_pipeline_evidence_bundle_after_08845bf/summary.md
fb6047ba69a9bf0608186f0f58c1545df38f5f25b26a049bab9ef36cb8176955  results/pure_pipeline_evidence_bundle_after_08845bf/bundle_manifest.json
dd0755dcea3fe44fffd66882f0e172d74b7d647f553792ce8aaeee522787018d  results/pure_pipeline_evidence_bundle_after_08845bf/target_matrix.tsv
ce453d8cbecadeb1b7b1bbe7b749317117b74077ef7122f1d267da8263b6f846  results/pure_pipeline_evidence_bundle_after_08845bf/case_matrix.tsv
```

The exporter now also parses readiness reports into `target_matrix.tsv`, so the
bundle directly exposes `readiness_ready`, `readiness_blocking_count`,
`readiness_external_builders`, and disk headroom without opening the raw
readiness log. Regression command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_after_517b398_both_readiness/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_readiness_fields_517b398
```

Regression evidence:

```text
5c9d2d5a475cb12706427fb7c098a7c0d70de507a72aa37e98d65ef58ee44628  scripts/export_pure_pipeline_evidence_bundle.py
5f86c3c0258e09cdc31d5f779bf769ecf0e7f63d9d0cc1d1b89245281c72c612  results/pure_pipeline_evidence_bundle_readiness_fields_517b398/summary.md
34773e8aa4db1f5b250c26403aeff81472a188d526fb1968749c9741a8cd0b91  results/pure_pipeline_evidence_bundle_readiness_fields_517b398/target_matrix.tsv
8f5db9f77bfc32d7fe32e9cb2c73390a6aa774575a896f76b1e1f58365e8844f  results/pure_pipeline_evidence_bundle_readiness_fields_517b398/bundle_manifest.json
```

## Not Yet True

The current baseline still has these gaps:

- `hw_emu` and `hw` command scripts are generated, but the pure-pipeline
  xclbins have not been produced or validated yet.
- The timing above is `sw_emu` timing and is useful for control-flow evidence,
  not performance claims.
- Spine has been run on the same smoke edge files. Larger review/capacity
  workloads still need the same strict input alignment before broad performance
  claims are claim-ready.

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
  -> pma_completion_barrier
  -> profiled barrier_event
  -> step-0 host enqueue dependency
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

- Integration-owned HLS kernel:
  `kernels/pma_to_regraph_adapter/pma_to_regraph_adapter.cpp`.
- Inputs:
  - four PMA `m_axi` ports, same device buffers as GraSU's `data_device_1..4`
  - `row_offset` device buffer
  - `node_count`, `pma_slot_count`, `max_cache_segment`
- Output:
  - AXI4-Stream edge bursts carrying 8 edges/burst
- HLS semantics:
  - use `#pragma HLS PIPELINE II=1` on the burst emission loop
  - use fixed 512-bit stream payload compatible with `edge_burst_dt`
  - pack unit weight as `1`
  - mark dummy lanes with bit 31 in src or encoded dst

PMA completion barrier:

- Integration-owned HLS kernel:
  `kernels/pma_completion_barrier/pma_completion_barrier.cpp`.
- Inputs:
  - four AXI4-Stream completion-token inputs, one from each GraSU PMA writer
- HLS semantics:
  - blocking-read all four writer tokens
  - return only after all four have arrived
  - expose an independent XRT event so host timing can record `barrier_ms`

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

- Add stream connections from each PMA writer to `pma_completion_barrier`.
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

## Readiness Bundle Refresh

While external Vitis/Vivado jobs are still active, the pure `hw_emu`/`hw`
target flow should not be launched immediately. The refresh wrapper records the
current build readiness for both targets, then emits the requirement audit and
compact evidence bundle without starting Vitis:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_after_$(git rev-parse --short HEAD)
```

Default behavior is strict: active unrelated builders are recorded as blockers
and the script exits non-zero after producing the audit and bundle. Use
`--allow-active-builders` only when the goal is to archive a warning-state
snapshot rather than a conservative go/no-go decision.

Live strict refresh on 2026-07-14 23:10 CST:

```bash
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_after_74a25be_live
```

The command exited `3` after producing the audit and bundle. This is expected:
both `hw_emu` and `hw` pass core generated-file and disk-space checks, but
active unrelated Vitis/Vivado builders are still present.

```text
target  xclbin  smoke  readiness  blocking  related  external  build_gb  tmp_gb
hw      no      no     no         1         0        17        217.6     2.2
hw_emu  no      no     no         1         0        17        217.6     2.2
sw_emu  yes     yes    n/a        n/a       n/a      n/a       n/a       n/a
```

Evidence hashes from that refresh:

```text
5ebd831e7b60c71b396caf5612b17c823b7c0677748a025eec793a649743a27c  scripts/refresh_pure_pipeline_readiness_bundle.sh
329d6764c0dd1dd0cc3509bf69d318e38ac491be63e5a7c162c47a6432e38f17  results/pure_pipeline_evidence_bundle_refresh_after_74a25be_live/summary.md
43a2fda72262d4e4fdc0928b8335cb860e706f9f0566fc077beb69e282f6d276  results/pure_pipeline_evidence_bundle_refresh_after_74a25be_live/target_matrix.tsv
becd57c1fffb43a0fe422c41fc84df304fd6332fac505dbfa2137ff99fdf3faa  results/pure_pipeline_requirement_audit_refresh_after_74a25be_live/audit.md
00f7de4713781e8ffda8533ff792bc7c642d047d9d776b0ab91543dbea998fd2  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_after_74a25be_live.txt
e03d520313f43d48fab8548cd6467cfc411d51b215c65c3f2d9896e32e39afdc  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_after_74a25be_live.txt
```

Follow-up detection fix: the active-builder scan now also treats Vivado/XSim
front-end processes as blockers: `xelab`, `xsim`, `xsc`, `xvlog`, and `xvhdl`.
This matters for `hw_emu`, where `xelab` can consume significant CPU before an
`xsimk` process exists.

Refresh after that fix:

```bash
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_after_d9a27f0_xsimdet
```

The command again exited `3` after writing the audit and bundle. The strict
readiness matrix now counts `19` external builders for both pending targets,
including the active `xelab` processes:

```text
target  xclbin  smoke  readiness  blocking  related  external  build_gb  tmp_gb
hw      no      no     no         1         0        19        217.6     2.2
hw_emu  no      no     no         1         0        19        217.6     2.2
sw_emu  yes     yes    n/a        n/a       n/a      n/a       n/a       n/a
```

```text
5dea61b63caf55d7f0639f4da4416f14289b53cecb7692393e6369b230590914  scripts/check_pure_pipeline_build_readiness.sh
1ba80cc19f5725b00fa3f81c548df74dc857114c6ac6c348ef2c6e6547bd6bc4  results/pure_pipeline_evidence_bundle_refresh_after_d9a27f0_xsimdet/summary.md
dc69273dd308b9e0726ea7a569e13893229a61c63c5fd6747bc2bdfeba8ef488  results/pure_pipeline_evidence_bundle_refresh_after_d9a27f0_xsimdet/target_matrix.tsv
471b8b1c5099777a731c11de1935cd163d1a1841085876499b5a94946d1eb8fb  results/pure_pipeline_requirement_audit_refresh_after_d9a27f0_xsimdet/audit.md
6d39b35c43183a24911d155f0d8fd34f66bcafab8af1396dc211bd9d8d048208  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_after_d9a27f0_xsimdet.txt
ca842e695a318f4399e862a1fff172fd85f6750844380e00769c63cf2b7c99bb  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_after_d9a27f0_xsimdet.txt
```

Clean post-commit refresh for code HEAD `c25d7f9`:

```bash
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_after_c25d7f9
```

The audit reports:

```text
branch=codex/pure-hw-pipeline
head=c25d7f972c1991e28f730275652c89d4688e671a
dirty=false
```

The readiness conclusion is unchanged: both pending targets are blocked only by
active external builders, with `19` unrelated Vitis/Vivado/XSim processes
counted.

```text
target  xclbin  smoke  readiness  blocking  related  external  build_gb  tmp_gb
hw      no      no     no         1         0        19        217.6     2.2
hw_emu  no      no     no         1         0        19        217.6     2.2
sw_emu  yes     yes    n/a        n/a       n/a      n/a       n/a       n/a
```

```text
a6cab633efa287b2df48020cad042408dc61f2b778a01bb3e5a9daae4280a845  results/pure_pipeline_evidence_bundle_refresh_after_c25d7f9/summary.md
32c3fc11fe3528a7f05c1b2f893b968f192e93c2250a9bd18e51082dd1461998  results/pure_pipeline_evidence_bundle_refresh_after_c25d7f9/target_matrix.tsv
72357f76a9b8eb46eaaed2324fb56e984a51e9f161069188615b421b5673b7bc  results/pure_pipeline_requirement_audit_refresh_after_c25d7f9/audit.md
d789eb02f596772f11445100b7d58ab1e564703f0b9ca98dbae69955057584cd  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_after_c25d7f9.txt
c05521f32553bcb81c3c053d5e5860db30fa64950086b5671d1f3d8c5d05df1e  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_after_c25d7f9.txt
```

## Idle Gate Alignment

The readiness scan, actual build wait-idle gate, and build monitor now use the
same Vitis/Vivado/XSim process family:

```text
v++ vpl vivado vrs xocc xelab xsim xsimk xsc xvlog xvhdl genericpcie*
```

This closes the gap where `check_pure_pipeline_build_readiness.sh` could detect
`xelab`, but `run_pure_pipeline_build.sh --wait-idle` and
`monitor_pure_pipeline_build.sh` would not count it.

Clean-code regression at HEAD `5953922`:

```bash
bash -n \
  scripts/run_pure_pipeline_build.sh \
  scripts/monitor_pure_pipeline_build.sh \
  scripts/check_pure_pipeline_build_readiness.sh \
  scripts/refresh_pure_pipeline_readiness_bundle.sh

./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label idle_gate_after_5953922 \
  --wait-idle 1 \
  --idle-poll 1 \
  --dry-run

./scripts/monitor_pure_pipeline_build.sh \
  --target hw_emu \
  --tail-lines 5 \
  --out-file .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_5953922.txt

./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_after_5953922
```

The idle gate exited `3`, as expected, before launching any Vitis work. The
post-fix audit reports:

```text
branch=codex/pure-hw-pipeline
head=5953922f97992d06cd81f619796988be1f6c907f
dirty=false
```

Current strict readiness after the fix:

```text
target  xclbin  smoke  readiness  blocking  related  external  build_gb  tmp_gb
hw      no      no     no         1         0        10        217.6     2.2
hw_emu  no      no     no         1         0        10        217.6     2.2
sw_emu  yes     yes    n/a        n/a       n/a      n/a       n/a       n/a
```

Evidence hashes:

```text
c19eb67a294b7a0a79c34d88967891c1b8d67c48036481786f2c805d96702068  scripts/run_pure_pipeline_build.sh
aca47369fb5c7161ec113184afaf2fb323f4b95b5b845f1b996a3fec6c069b76  scripts/monitor_pure_pipeline_build.sh
d579a5f0d94131aaa7c0e93224f01fce865ac139924c83d0f0206248716502fc  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/idle_check_idle_gate_after_5953922.txt
86cd59a90fa24f931a10af4fa6d2f75b6cda04aef7d7367b797790cea62c86ba  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_5953922.txt
73d200de23e809902c35b55b644d85db5955dc5fc73645f926a1c661f94068c2  results/pure_pipeline_evidence_bundle_refresh_after_5953922/summary.md
7455ff2464de04067b9ce353230f2f13ffe2ae328c18ca95ba1f8d8878290d31  results/pure_pipeline_evidence_bundle_refresh_after_5953922/target_matrix.tsv
064199050db42ff7ac013403212e8f0e2d1707d0155ce6e1099d5770f03b23e0  results/pure_pipeline_requirement_audit_refresh_after_5953922/audit.md
ae620a950698139188fc1948bb7743492c95546bd6b780916656562f0e809a0b  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_after_5953922.txt
dc0570a42cdb8ff850e5efd8df8df613d9573f468b0d265045cdd535f3f7578e  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_after_5953922.txt
```

## Builder Breakdown Evidence

The readiness report and compact evidence bundle now include a process-type
breakdown for active builders. This makes the current blocker easier to read
without opening the full process list.

Clean-code refresh at HEAD `2b4a85b`:

```bash
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_after_2b4a85b
```

The audit reports:

```text
branch=codex/pure-hw-pipeline
head=2b4a85b2631839b3c9ea510b5bbdbcbcfde150a6
dirty=false
```

Current strict readiness:

```text
target  xclbin  smoke  readiness  blocking  related  external  external_breakdown
hw      no      no     no         1         0        10        total=10 v++=2 vivado=4 vpl=2 vrs=2
hw_emu  no      no     no         1         0        10        total=10 v++=2 vivado=4 vpl=2 vrs=2
sw_emu  yes     yes    n/a        n/a       n/a      n/a       n/a
```

This means the pure GraSU -> ReGraph `hw_emu` and `hw` build inputs are ready,
but the machine is still occupied by unrelated Vitis/Vivado builders. No pure
pipeline `hw_emu` or `hw` xclbin has been produced yet.

Evidence hashes:

```text
7bc40d534eea9d89d4795209470fcee4eae17352cb7e815e3ba4f0e75acc817e  scripts/check_pure_pipeline_build_readiness.sh
afcfea16f53bccddaad730e9993efb3d0a1f8c30a71f55f5ab0744fa160b9030  scripts/export_pure_pipeline_evidence_bundle.py
21dbd7f6e183800ac9d6dada3e67d5bfbafff7dd50dbb89df4baf3c117b965b7  results/pure_pipeline_evidence_bundle_refresh_after_2b4a85b/summary.md
b49cfb2b0eadb4de4f858ad2cd0fc48308a8bd8a00ce49c2c09a37961c38e7d4  results/pure_pipeline_evidence_bundle_refresh_after_2b4a85b/target_matrix.tsv
329ee42f47721b754d9b8d30a3d94754281cfed8894ac70f74f9ac2c77d5d6f1  results/pure_pipeline_requirement_audit_refresh_after_2b4a85b/audit.md
d61a1ccbfdae96ea0881eb08082d3821ec248af6c2c4460e464c2a8b13b37d11  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_after_2b4a85b.txt
13357c0a9a4d12f43fc3f27db91e9d71d2d3702221dcf96702f56398df30456d  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_after_2b4a85b.txt
```

## 2026-07-15 Progress Snapshot

Source code HEAD used for this refresh:

```text
8f60fcf2ba253aecd5057ee22fd5eb8c0c162ab9
```

The pure GraSU -> ReGraph pipeline still has only the `sw_emu` correctness
xclbin. There is no successful pure-pipeline `hw_emu` or `hw` xclbin yet:

```text
.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin  exists
.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin  missing
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin          missing
```

An external Spine hardware build did complete and produced this separate
baseline artifact:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_tiny_active_hw_exact_20260714_0740/link_150_exact_final/xclbin/spine_partitioned_split_e2e.hw.xclbin
mtime:  2026-07-15 00:15:17.459973395 +0800
size:   53289602
sha256: 76b0f144ad85492776090753fdf9dce263c0a15e73436e736ff6bd40ebb00d11
```

That Spine xclbin is useful comparison evidence, but it is not the GraSU ->
ReGraph pure hardware pipeline xclbin.

Fresh strict readiness refresh:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_20260715_001926_external_spine_hw_active_after_8f60fcf
```

The command exited `3` after writing evidence. This is the expected blocked
state while another unrelated Spine/Vitis hardware link is active. The
readiness matrix is:

```text
target  xclbin  smoke  readiness  blocking  related  external  external_breakdown
hw      no      no     no         1         0        7         total=7 v++=2 vivado=2 vpl=2 vrs=1
hw_emu  no      no     no         1         0        7         total=7 v++=2 vivado=2 vpl=2 vrs=1
sw_emu  yes     yes    n/a        n/a       n/a      n/a       n/a
```

The active external build is another Spine hardware link under:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0018
```

As of this snapshot it had not produced:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0018/xclbin/spine_partitioned_split_e2e.hw.xclbin
```

Evidence hashes:

```text
a7d16f057d5376906ef45347154377e8e3df3c7b4206312d235efcfc57a7868e  results/pure_pipeline_evidence_bundle_refresh_20260715_001926_external_spine_hw_active_after_8f60fcf/summary.md
a7dd99530b47458a2e785ba2c4cffdf00f9cff7abc26cc840463e2f591573eb9  results/pure_pipeline_evidence_bundle_refresh_20260715_001926_external_spine_hw_active_after_8f60fcf/target_matrix.tsv
74a839cf83656b37284907556f5e33491e61e33618e607e376215e72af2a3361  results/pure_pipeline_requirement_audit_refresh_20260715_001926_external_spine_hw_active_after_8f60fcf/audit.md
14db30ac2bfa7c537455c1908555ae3a781bff594dccf883fdad76627a32e530  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_20260715_001926_external_spine_hw_active_after_8f60fcf.txt
4642a5558fb257beffedfd390ee7b42baf1b9c861aa322392db9806b5609e95e  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_20260715_001926_external_spine_hw_active_after_8f60fcf.txt
```

When the external Spine build is gone, the next strict gate is:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_pure_pipeline_build_readiness.sh \
  --target hw_emu \
  --label post_external_spine_idle_after_8f60fcf
```

If that reports `ready=yes`, the next build command is:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_8f60fcf \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

## 2026-07-15 Idle-Settle Guard

After the external Spine builders went idle, strict readiness passed for both
pending pure-pipeline targets:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_pure_pipeline_build_readiness.sh \
  --target hw_emu \
  --label post_external_spine_idle_after_5174168

./scripts/check_pure_pipeline_build_readiness.sh \
  --target hw \
  --label post_external_spine_idle_after_5174168
```

Both reports showed:

```text
ready=yes
blocking_count=0
active_builders=PASS related=0 external=0
active_builder_breakdown=PASS related="total=0" external="total=0"
```

The first `hw_emu` target-flow attempt was then started:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_5174168 \
  --wait-idle 7200 \
  --idle-poll 60 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

It reached the first `hw_emu` compile and successfully produced:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/build/bin_search.hw_emu.xo
sha256: a5b0991d116600587a473cd94794a302d62c1bb7af82f11659070369171a2884
size:   206779
mtime:  2026-07-15 00:24:27.667169030 +0800
```

During that run, another unrelated Spine hardware link started under:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024
```

The pure-pipeline attempt was intentionally interrupted to avoid competing
with the external hardware implementation. This attempt did not produce:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin
```

Post-interrupt checks showed:

```text
related_hwemu_processes=0
builders total=20 runme.sh=2 vrs=2 v++=4 vivado=4 loader=4 vpl=4
```

This exposed a launch race: a one-shot idle check can pass, and an unrelated
hardware build can still start immediately afterward. To make the launch more
reproducible, the build wrapper now supports a continuous idle settle window:

```bash
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label after_<commit> \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120
```

`run_pure_pipeline_target_flow.sh` forwards the same option. The readiness
script's recommended next command now also includes `--idle-settle 120`.

Regression checks:

```bash
bash -n \
  scripts/run_pure_pipeline_build.sh \
  scripts/run_pure_pipeline_target_flow.sh \
  scripts/check_pure_pipeline_build_readiness.sh

set +e
./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label idle_settle_guard_after_5174168 \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 2 \
  --dry-run \
  --skip-compile \
  --skip-link
echo "idle_settle_guard_rc=$?"
```

The guard regression returned `idle_settle_guard_rc=3`, as expected while
external Spine builders were active, and did not launch a pure-pipeline Vitis
compile.

Updated next command once external builders are gone:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_$(git rev-parse --short HEAD) \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Evidence hashes:

```text
50f40fa98a2f1b124ea6f1d929be96209b92a0ffac1885f4e794b14b140c6c1c  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_post_external_spine_idle_after_5174168.txt
00d794e5814c4d2daf8f3d2df83115686acac21cc5b4020fc9a5d9144ea74c66  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_post_external_spine_idle_after_5174168.txt
2cb5a5f59a85988df34c0908de9a5436e9b26c1f14b6ca30317afd69201f66c4  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/compile_after_5174168.log
a749093fcefbb54e379c29d3387d17d56c15c41b8e65a19b453db4cb5c3249a0  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_after_5174168_evidence.tsv
a5b0991d116600587a473cd94794a302d62c1bb7af82f11659070369171a2884  .tmp_build/pure_pipeline_hw_emu_stage0/build/bin_search.hw_emu.xo
a92c69dfe77d93e05beb1989647acce48723243cd0710ad274ddf70d4054b7da  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/idle_check_idle_settle_guard_after_5174168.txt
67f44795fe90d65e2ccb4e7fd328d4b25b6e41809904f8fef6abe010339af31d  scripts/run_pure_pipeline_build.sh
d3db08cd613e041e80985bbd73288fe094709355fd81cd440b60f5d61755f0e3  scripts/run_pure_pipeline_target_flow.sh
56b164f31664008deb80c6473247960013d65faa5d3ccbc9ff33f0c438f94d74  scripts/check_pure_pipeline_build_readiness.sh
```

## 2026-07-15 E9ffca3 Refresh

After committing the idle-settle guard, the current code HEAD is:

```text
e9ffca3a3392d658e6dc669e653c06342f0d4855
```

The pure-pipeline xclbin status is unchanged:

```text
.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin  exists
.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin  missing
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin          missing
```

Current refresh command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_20260715_003109_external_spine_active_after_e9ffca3
```

The command exited `3` after writing evidence. The only readiness blocker is
the active external Spine hardware link; no pure-pipeline builder was running:

```text
target  xclbin  smoke  readiness  blocking  related  external  external_breakdown
hw      no      no     no         1         0        10        total=10 v++=2 vivado=4 vpl=2 vrs=2
hw_emu  no      no     no         1         0        10        total=10 v++=2 vivado=4 vpl=2 vrs=2
sw_emu  yes     yes    n/a        n/a       n/a      n/a       n/a
```

The active external build path is:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024
```

At the time of this snapshot, this external build still had not produced:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024/xclbin/spine_partitioned_split_e2e.hw.xclbin
```

During this refresh, `scripts/audit_pure_pipeline_status.py` was updated so
its exported `next_commands` include the same `--idle-settle 120` launch guard
as the readiness report and README. The refreshed bundle now recommends:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_e9ffca3 \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Regeneration after the audit-script fix:

```bash
./scripts/audit_pure_pipeline_status.py \
  --label refresh_20260715_003109_external_spine_active_after_e9ffca3 \
  --out-dir results/pure_pipeline_requirement_audit_refresh_20260715_003109_external_spine_active_after_e9ffca3

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_refresh_20260715_003109_external_spine_active_after_e9ffca3/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_refresh_20260715_003109_external_spine_active_after_e9ffca3
```

Evidence hashes:

```text
40eefe7e5673191957d4a21a8002e2e69729cf224783ad73fc083b745061ea1b  scripts/audit_pure_pipeline_status.py
4baa841136690ca33ef1fa0d2619ebd3b0089f54a5d9f80a12757afda6580b0c  results/pure_pipeline_evidence_bundle_refresh_20260715_003109_external_spine_active_after_e9ffca3/summary.md
7533a3bfb1f4329b81dcc32eeff958a550c34fd7a3bd571cbb9df42695bd7752  results/pure_pipeline_evidence_bundle_refresh_20260715_003109_external_spine_active_after_e9ffca3/target_matrix.tsv
710113f22884e965d5c81ae7c80d8dbe0007d3ae54560d8d1a0942cd48d55ada  results/pure_pipeline_requirement_audit_refresh_20260715_003109_external_spine_active_after_e9ffca3/audit.md
17f19682d72d9223395f49b3fa87c6a15cc3f27f689225d8d57381673a195150  results/pure_pipeline_requirement_audit_refresh_20260715_003109_external_spine_active_after_e9ffca3/audit.json
372a43e0a72659d944cb43766177b22d1510da4fb3c5fe8441ebaa4bdfd67bd5  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_20260715_003109_external_spine_active_after_e9ffca3.txt
713141bb20759edb9426e9cea2edc936c946d56deb8026f571da5fb8dd38cd1c  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_20260715_003109_external_spine_active_after_e9ffca3.txt
```

## 2026-07-15 Boundary Prepare Refresh

While the external Spine hardware implementation continued to occupy
Vitis/Vivado, the current HEAD `7025789` was used to refresh the non-Vitis
boundary prepare evidence. This does not build or load an xclbin; it validates
host graph ingest, GraSU PMA packing, CPU oracle generation, unit-weight
constraints, and the `V <= 65536` bound for large first-stage inputs.

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_prepare_check.sh \
  --preset boundary \
  --out-dir results/pure_pipeline_prepare_boundary_after_7025789
```

Result:

```text
summary: results/pure_pipeline_prepare_boundary_after_7025789/summary.tsv
status:  passed
git_head=7025789f6da251ce290dd6ce323506c555db7eb9
```

Cases:

```text
boundary_star_v65536_u4096
  family: hot-source
  vertices: 65536
  update_edges: 4096
  final_edges: 69632
  supersteps: 2
  prep: PASS
  pma_slots: 1052672
  reachable_vertices: 4099
  max_distance: 2
  unit_weight: 1

boundary_spread_v65536_u4096
  family: spread
  vertices: 65536
  update_edges: 4096
  final_edges: 69632
  supersteps: 16
  prep: PASS
  pma_slots: 1048576
  reachable_vertices: 33
  max_distance: 16
  unit_weight: 1
```

The refreshed audit and evidence bundle were regenerated with the boundary
prepare result as the newest boundary artifact:

```bash
./scripts/audit_pure_pipeline_status.py \
  --label boundary_after_7025789 \
  --out-dir results/pure_pipeline_requirement_audit_boundary_after_7025789

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_boundary_after_7025789/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_boundary_after_7025789
```

The overall requirement status remains unchanged because `hw_emu` and `hw`
xclbins are still missing, but requirement 6 now has fresh current-HEAD
prepare-only evidence.

Evidence hashes:

```text
6afb10a8424d3f517e894a326a7a4394f0864079d348bcf20277d1425f4c4267  results/pure_pipeline_prepare_boundary_after_7025789/summary.tsv
4a4d43be7e43cd2b56fb98dcf49de4e6e5f1122ec78d5aecacfa6edc0e463e35  results/pure_pipeline_prepare_boundary_after_7025789/run.env
dc7683ae08220f55f0fce317da7f0244ec162b94f6aaf15f46e75cd44cf18426  results/pure_pipeline_prepare_boundary_after_7025789/generate_workloads.log
9b4ee3ef9ac5fa8a5f5ba9fd9784da8c60be79132de23d661804ad007603e24e  results/pure_pipeline_prepare_boundary_after_7025789/boundary_star_v65536_u4096.log
71293db21d733e62eeb5680b5aaf67e2e01aaccf6fb4233ab5c298d040e8d84d  results/pure_pipeline_prepare_boundary_after_7025789/boundary_spread_v65536_u4096.log
e8110d3b222ab35f3ca27a646128e4b864d6dbfd5450dacc79e0ee6f23170a62  workloads/sssp_benchmark_boundary/manifest.tsv
cb40efbffe3a091be8a8bffe03c2ee364c794a2cddb315a0571601b38c2cad5d  .tmp_build/pure_pipeline_host_stage0/pure_pipeline_host
6441a6abdd0b1e2c90c3c96187de057eb64c42061416abed7da1ec87617bbea2  results/pure_pipeline_requirement_audit_boundary_after_7025789/audit.json
b84333fbc2d1f76ffabf17003ea5b32ec0fef988a9391149241de8d26bcf8a6c  results/pure_pipeline_requirement_audit_boundary_after_7025789/audit.md
8d93158e7b336541922b75ee161af060509ca3efb559084e6bb50989bb3674f9  results/pure_pipeline_evidence_bundle_boundary_after_7025789/summary.md
7533a3bfb1f4329b81dcc32eeff958a550c34fd7a3bd571cbb9df42695bd7752  results/pure_pipeline_evidence_bundle_boundary_after_7025789/target_matrix.tsv
```

## 2026-07-15 Current-Head Readiness Refresh

After the boundary prepare documentation commit, the current code/documentation
HEAD is:

```text
346fa5926ce66bc94c91eddf43ee5ea8f0f913c8
```

The current pure-pipeline hardware status is still:

```text
.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin  exists
.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin  missing
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin          missing
```

Refresh command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_20260715_010014_external_spine_active_after_346fa59
```

The command exited `3` after writing readiness, audit, and bundle evidence.
The only readiness blocker is still the external Spine hardware build; no
pure-pipeline Vitis/Vivado process was active.

```text
target  xclbin  smoke  readiness  blocking  related  external  external_breakdown
hw      no      no     no         1         0        10        total=10 v++=2 vivado=4 vpl=2 vrs=2
hw_emu  no      no     no         1         0        10        total=10 v++=2 vivado=4 vpl=2 vrs=2
sw_emu  yes     yes    n/a        n/a       n/a      n/a       n/a
```

The external Spine link is still under:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024
```

It has not yet produced:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024/xclbin/spine_partitioned_split_e2e.hw.xclbin
```

The link is not stuck: the Vitis log advanced through synthesis and logic
optimization into placement:

```text
[00:29:37] Run vpl: Step synth: Completed
[00:41:43] Finished 2nd of 6 tasks (FPGA linking synthesized kernels to platform).
[00:44:44] Finished 3rd of 6 tasks (FPGA logic optimization).
[00:44:44] Starting logic placement..
[00:56:20] Phase 2.5 Global Placement Core
```

Next command once external builders are gone:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_346fa59 \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Evidence hashes:

```text
3c5cac69d4d145697707fccd8dd2a8faa94f5b2ce87d05fb3b6e51410e43117b  results/pure_pipeline_evidence_bundle_refresh_20260715_010014_external_spine_active_after_346fa59/summary.md
2dbdf3ef04700fdb61eb0f0d62b6a40eeea5035ed8e7100b06fad0bf2c8f65c3  results/pure_pipeline_evidence_bundle_refresh_20260715_010014_external_spine_active_after_346fa59/target_matrix.tsv
783212db8ed7d6e7101b89d990a0b0a770a4da152918a056b4a4c9d6285111d9  results/pure_pipeline_requirement_audit_refresh_20260715_010014_external_spine_active_after_346fa59/audit.md
41f5ec28d791e0fb94a7c774e18054a4240f66daec67d25135bd697f0839428c  results/pure_pipeline_requirement_audit_refresh_20260715_010014_external_spine_active_after_346fa59/audit.json
776a01e29573e63abddcf0fd07f2b5ac5deb38eacf3584ec3bcdd23d2c6c130f  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_20260715_010014_external_spine_active_after_346fa59.txt
ee3205ef6141afb514506d0770abdc8eaafbd5d0a7a722d623d54e0d848f1122  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_20260715_010014_external_spine_active_after_346fa59.txt
```

## 2026-07-15 Stale HW_EMU Artifact Guard

The interrupted `hw_emu` launch from `2026-07-15T00:23` left partial build
artifacts in the pure-pipeline target directory. The important observation is
that `bin_search` completed, but `dispatch` did not produce its final `.xo`:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/build/bin_search.hw_emu.xo                  exists
.tmp_build/pure_pipeline_hw_emu_stage0/build/dispatch.hw_emu.xo                    missing
.tmp_build/pure_pipeline_hw_emu_stage0/build/dispatch.hw_emu.xo.compile_summary    exists
.tmp_build/pure_pipeline_hw_emu_stage0/build/dispatch.mdb                          exists
```

To make the next long run deterministic, `run_pure_pipeline_build.sh` now
supports:

```bash
--clean-build-artifacts
```

The option only removes children under the standard target build directory:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_<target>_stage0/build/
```

It refuses non-standard build roots, records `cleanup_<label>.txt`, and leaves
the manifest, generated config files, compile/link command scripts, and run
logs in place. `run_pure_pipeline_target_flow.sh` forwards the same option, and
the readiness/audit next-command hints now include it.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration

bash -n \
  scripts/run_pure_pipeline_build.sh \
  scripts/run_pure_pipeline_target_flow.sh \
  scripts/check_pure_pipeline_build_readiness.sh

./scripts/run_pure_pipeline_build.sh \
  --target hw_emu \
  --label stale_cleanup_probe_after_5d5cdff \
  --dry-run \
  --clean-build-artifacts \
  --status-only

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label stale_cleanup_flow_probe_after_5d5cdff \
  --dry-run \
  --clean-build-artifacts \
  --skip-finalize \
  --skip-audit \
  --no-readiness \
  --monitor-tail 5
```

The cleanup probe returned `0` and did not delete any files because
`--dry-run` was set. Its cleanup log listed the stale children before and after
unchanged:

```text
action=dry_run_no_delete
bin_search.hw_emu.xo
bin_search.hw_emu.xo.compile_summary
bin_search.mdb
bin_search/
dispatch.hw_emu.xo.compile_summary
dispatch.mdb
dispatch/
```

A strict readiness snapshot at the same code state still blocks new
`hw_emu/hw` launch because the external Spine hardware link is active:

```text
ready=no
blocking_count=1
active_builders=FAIL related=0 external=10
external_breakdown="total=10 v++=2 vivado=4 vpl=2 vrs=2"
```

The external Spine link still has not produced:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024/xclbin/spine_partitioned_split_e2e.hw.xclbin
```

It is still making progress in placement; the latest inspected log tail reached:

```text
[01:35:46] Phase 4.2 Post Placement Cleanup
[01:35:46] Phase 4.3 Placer Reporting
[01:35:46] Phase 4.3.1 Print Estimated Congestion
[01:35:46] Phase 4.4 Final Placement Cleanup
```

Next command once external builders are gone:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_5d5cdff \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Evidence hashes:

```text
f9cceb1f3d24ef9948afdbb58f4c14f6bedd909ed15a6a241909507929583fa4  scripts/run_pure_pipeline_build.sh
5c384ac7bcdc0b5f8f6ac9f9463b1294812a41faa6dd50e143dcd78f9fcf3c51  scripts/run_pure_pipeline_target_flow.sh
a6863e2539695477cf4f45f482a8490b5333f45cc6cef311d3924a7b3e7d9a71  scripts/check_pure_pipeline_build_readiness.sh
5b2caa3c347f294261de276ec28350c07ad45d9bea00c3fed8850a2d9d7dec26  scripts/audit_pure_pipeline_status.py
55f34e9a8f3ab3ac8714c09451cea5b739d019b9ca046d01918fadfd09e9b8db  README.md
08eba9ff1d68375ffe8e4fd4e20f5639507b201832d8f7c5ae964720f7ecfabf  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/cleanup_stale_cleanup_probe_after_5d5cdff.txt
816e9c0d86f1542f2a80bf5e474da3adf0b6550b632aa275e64fd1a5d0c78ef9  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_stale_cleanup_probe_after_5d5cdff.env
a749093fcefbb54e379c29d3387d17d56c15c41b8e65a19b453db4cb5c3249a0  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/build_stale_cleanup_probe_after_5d5cdff_evidence.tsv
a51b07fe73ea953477a0d1d796ecdd8b5c21c03a4a126e31b6b590a5511bb087  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_stale_cleanup_strict_after_5d5cdff.txt
```

## 2026-07-15 Readiness Stale-Artifact Warning

After adding the cleanup switch, the readiness preflight was tightened so that
it records whether the target `build/` directory already contains children
while the target xclbin is still missing. This state is not a hard blocker, but
it is a reproducibility warning and should be paired with
`--clean-build-artifacts` for the next long build.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration

bash -n scripts/check_pure_pipeline_build_readiness.sh

./scripts/check_pure_pipeline_build_readiness.sh \
  --target hw_emu \
  --label stale_artifact_warn_after_2e0ca4a \
  --allow-active-builders

./scripts/check_pure_pipeline_build_readiness.sh \
  --target hw \
  --label stale_artifact_warn_hw_after_2e0ca4a \
  --allow-active-builders \
  --out-file .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_stale_artifact_warn_hw_after_2e0ca4a.txt
```

Observed `hw_emu` report:

```text
ready=yes
warning_count=2
build_artifacts  WARN  children=7 clean_recommended=yes names=bin_search,bin_search.hw_emu.xo,bin_search.hw_emu.xo.compile_summary,bin_search.mdb,dispatch,dispatch.hw_emu.xo.compile_summary,dispatch.mdb
active_builders  FAIL  related=0 external=10
```

Observed `hw` report:

```text
ready=yes
warning_count=1
build_artifacts  PASS  children=0 clean_recommended=no names=none
active_builders  FAIL  related=0 external=10
```

With strict active-builder handling, `hw_emu` still exits `3` because the
external Spine hardware link is active:

```text
ready=no
blocking_count=1
warning_count=1
build_artifacts  WARN  children=7 clean_recommended=yes
active_builders  FAIL  related=0 external=10
```

Evidence hashes:

```text
787fa4624d8bb8f4e93259dbf2277109982ec944358d8359b30bfc8b59e641a3  scripts/check_pure_pipeline_build_readiness.sh
f262467082fee91d895ba3ccb502afcad80a217824417c757d140e0953193d10  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_stale_artifact_warn_after_2e0ca4a.txt
c2b98434ba117258d7327502a60ea026fe8291588ea7165d99ef88398012cd0b  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_stale_artifact_strict_after_2e0ca4a.txt
d940130339c82f5c8615fc30ab65a09f9a71a3ab208368ff6e8851c77a8cb41e  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_stale_artifact_warn_hw_after_2e0ca4a.txt
```

## 2026-07-15 Current-Head SW_EMU Refresh

While the external Spine hardware link was still occupying Vitis/Vivado, the
current integration HEAD was used to refresh the pure-pipeline `sw_emu`
correctness and comparison evidence. This does not prove hardware timing, but
it does re-prove the same GraSU completion barrier, real-PMA adapter, stream
little-GS path, apply stage, and CPU-oracle comparison for the four required
small graph families.

Current HEAD:

```text
8f5fdffd4f8e6f9ab6f2c29806ef269096a734b7
```

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/finalize_pure_pipeline_build.sh \
  --target sw_emu \
  --label swemu_refresh_after_8f5fdff \
  --build-host \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 180 \
  --timeout 600
```

The gate case and the full four-family smoke both passed. Full smoke summary:

```text
tiny_chain_v16       chain       PASS  mismatches=0 final_edges=15 supersteps=16 event_e2e_ms=6120.978722
tiny_star_v16_u12    hot-source  PASS  mismatches=0 final_edges=28 supersteps=2  event_e2e_ms=692.524587
tiny_spread_v16_u8   spread      PASS  mismatches=0 final_edges=24 supersteps=16 event_e2e_ms=5888.241440
tiny_hotdst_v64_u32  hot-dest    PASS  mismatches=0 final_edges=95 supersteps=16 event_e2e_ms=5750.386851
```

The generated comparison uses the existing host zero-cost baseline and Spine
same-input baseline, and continues to label pure timing as `sw_emu` rather than
hardware performance:

```text
tiny_chain_v16       host_zero_cost_ms=6.127929 spine_kernel_e2e_ms=1.58718 pure_target=sw_emu pure_event_e2e_ms=6120.978722
tiny_star_v16_u12    host_zero_cost_ms=2.526626 spine_kernel_e2e_ms=1.57177 pure_target=sw_emu pure_event_e2e_ms=692.524587
tiny_spread_v16_u8   host_zero_cost_ms=5.743649 spine_kernel_e2e_ms=1.59870 pure_target=sw_emu pure_event_e2e_ms=5888.241440
tiny_hotdst_v64_u32  host_zero_cost_ms=6.202223 spine_kernel_e2e_ms=2.26057 pure_target=sw_emu pure_event_e2e_ms=5750.386851
```

After the smoke refresh, the requirement audit and evidence bundle were
regenerated:

```bash
./scripts/audit_pure_pipeline_status.py \
  --label swemu_refresh_after_8f5fdff \
  --out-dir results/pure_pipeline_requirement_audit_swemu_refresh_after_8f5fdff

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_swemu_refresh_after_8f5fdff/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_swemu_refresh_after_8f5fdff
```

The bundle exporter was also fixed to prefer the comparison matching the
current audit's newest `sw_emu` smoke summary. Before this fix, a newly exported
bundle could have a fresh target matrix but an older default smoke comparison
table.

Current bundle target state:

```text
sw_emu  xclbin=yes  smoke=yes  xclbin_sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
hw_emu  xclbin=no   smoke=no   readiness=no blocking=1 warnings=1 external_builders=10
hw      xclbin=no   smoke=no   readiness=no blocking=1 warnings=0 external_builders=10
```

The external Spine link still had not produced its target xclbin during this
refresh, but its log had advanced from placement into routing:

```text
[01:55:59] Finished 4th of 6 tasks (FPGA logic placement).
[01:55:59] Starting logic routing..
[01:56:29] Phase 1 Build RT Design
```

Evidence hashes:

```text
b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862  .tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
cb40efbffe3a091be8a8bffe03c2ee364c794a2cddb315a0571601b38c2cad5d  .tmp_build/pure_pipeline_host_stage0/pure_pipeline_host
e57db6e5166e218b2f838474e54df93f84832425a4b4fbafcb93c3678366fb3c  results/pure_pipeline_sw_emu_smoke_gate_swemu_refresh_after_8f5fdff/summary.tsv
38914a937b6a7ed1a2b72edf75e67c88caff586ca1f9c43e1b70bdcbc0a189c1  results/pure_pipeline_sw_emu_smoke_swemu_refresh_after_8f5fdff/summary.tsv
09e527ae167fc2f275ae3840f3c594991a16cec380d1ecf278d4d857b5f37246  results/pure_pipeline_sw_emu_smoke_swemu_refresh_after_8f5fdff/run.env
9f44017b060e780f4de5856100e1b23847077edbec9afee7c76d0b224534a170  results/pure_pipeline_sw_emu_compare_swemu_refresh_after_8f5fdff/comparison.tsv
339d5d2636481d5f0296804149416e95ccc1bcaee5c6c9b90de32098a6de5c1f  results/pure_pipeline_sw_emu_compare_swemu_refresh_after_8f5fdff/comparison.md
1caae190b523c7598b644def75e39e9ad0e124c330d93e56e0409940b258061c  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_swemu_refresh_after_8f5fdff.env
27de9e292c425fa5268b741fb49a7920c0c7caa2f96df2e8a7397a9991c365a6  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_swemu_refresh_after_8f5fdff_evidence.tsv
28d70a8d6a3d3a285906ad08acfc1217558d87b7c81613ca55c4ec7a3d13fef2  results/pure_pipeline_requirement_audit_swemu_refresh_after_8f5fdff/audit.json
fbd079236a34228931c284a55aeb71af03acb662c4862fa824c094b4bfcfefb6  results/pure_pipeline_requirement_audit_swemu_refresh_after_8f5fdff/audit.md
22044b08222694ae7420e0b5c54f4fe8b97dccfd77cbbd592f3c51070bddb7cd  results/pure_pipeline_evidence_bundle_swemu_refresh_after_8f5fdff/summary.md
71c36ec6d1bfe4515ef03a7fc4ce97f20c2b9e83a878d838f2ff11e7a9f4ec97  results/pure_pipeline_evidence_bundle_swemu_refresh_after_8f5fdff/case_matrix.tsv
65c915d5e55c6e690b55568bc45168fd23a855321cdfa9edaa7463c5102d5820  results/pure_pipeline_evidence_bundle_swemu_refresh_after_8f5fdff/target_matrix.tsv
bcbbfd750dfe5a5e5a7669c73821b1d63d5d936da153e1297901c0cd734ada15  results/pure_pipeline_evidence_bundle_swemu_refresh_after_8f5fdff/bundle_manifest.json
cbf16deca443a0ab0c88337016d230a2f2a8dd5944956bd0e4ce4852377d4b57  scripts/export_pure_pipeline_evidence_bundle.py
```

## 2026-07-15 Bundle Stale-Artifact Matrix

The evidence bundle exporter now preserves the readiness report's
`build_artifacts` row in `target_matrix.tsv` and in the compact markdown target
table. This makes the stale partial `hw_emu` build state visible from the
bundle itself, without reopening the raw readiness report.

Validation command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_swemu_refresh_after_8f5fdff/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_swemu_refresh_after_e493833
```

Observed target matrix rows:

```text
hw_emu  xclbin=no  smoke=no  readiness=no  external_builders=10  build_artifacts=WARN  clean_recommended=yes  children=7
hw      xclbin=no  smoke=no  readiness=no  external_builders=10  build_artifacts=<empty>
sw_emu  xclbin=yes smoke=yes
```

The detailed `hw_emu` artifact list is:

```text
bin_search,bin_search.hw_emu.xo,bin_search.hw_emu.xo.compile_summary,bin_search.mdb,dispatch,dispatch.hw_emu.xo.compile_summary,dispatch.mdb
```

This is still only a reporting improvement. The next actual build command
should keep using `--clean-build-artifacts` before launching `hw_emu`.

Evidence hashes:

```text
51d1225f5f95f9e0215a64a499967f9dd7d282d7418b738db31fb558935d8ca4  scripts/export_pure_pipeline_evidence_bundle.py
f503d1895bf874deefadc5b6fea1731060b2278370e30b2d39fdf94fe0686585  results/pure_pipeline_evidence_bundle_swemu_refresh_after_e493833/summary.md
bbd50df93b4e43fb458ca5e069eab698542bf3d5379fc35f97aca6aa3232b74d  results/pure_pipeline_evidence_bundle_swemu_refresh_after_e493833/target_matrix.tsv
aceea952b9ba5f6b4ac166fc386911dbbdea76d592823b55a12fe238b81aa307  results/pure_pipeline_evidence_bundle_swemu_refresh_after_e493833/bundle_manifest.json
```

## 2026-07-15 Current-Head Readiness During Spine Routing

At current integration HEAD:

```text
59c8f561023148574c4529f02d65c810c95d1228
```

the external Spine 133 MHz hardware link is still active, now in routing. The
pure-pipeline `hw_emu` and `hw` targets were refreshed without launching Vitis:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_20260715_0204_external_spine_routing_after_59c8f56
```

The wrapper exited `3`, which is expected while strict readiness sees active
external Vitis/Vivado builders. It still wrote the readiness reports, audit,
and evidence bundle.

Current target matrix:

```text
hw      xclbin=no  smoke=no  readiness=no  blocking=1 warning=0 external_builders=10 build_artifacts=PASS clean_recommended=no
hw_emu  xclbin=no  smoke=no  readiness=no  blocking=1 warning=1 external_builders=10 build_artifacts=WARN clean_recommended=yes children=7
sw_emu  xclbin=yes smoke=yes xclbin_sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
```

The `hw_emu` stale artifact list is still:

```text
bin_search,bin_search.hw_emu.xo,bin_search.hw_emu.xo.compile_summary,bin_search.mdb,dispatch,dispatch.hw_emu.xo.compile_summary,dispatch.mdb
```

The next launch command remains:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_59c8f56 \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

External Spine xclbin was still missing:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024/xclbin/spine_partitioned_split_e2e.hw.xclbin
```

Latest inspected Spine log tail:

```text
[01:55:59] Finished 4th of 6 tasks (FPGA logic placement).
[01:55:59] Starting logic routing..
[02:02:33] Phase 3 Global Routing
[02:02:33] Phase 4 Initial Routing
[02:02:33] Phase 4.1 Initial Net Routing Pass
[02:04:04] Phase 5 Rip-up And Reroute
[02:04:04] Phase 5.1 Global Iteration 0
```

Evidence hashes:

```text
b0bd8d17d71c992a0e1a7f619edc1e847c8798d42dc86b6e7e21b9a2ee9925ee  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_20260715_0204_external_spine_routing_after_59c8f56.txt
a42629dff3eb937165037fb7aa85385fba123c2ed6241065908372186afbe560  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_20260715_0204_external_spine_routing_after_59c8f56.txt
b7eba2eef3696ea993126618f5e1b4c06e3fd1acfcb3f2633aeabe5422bf23cc  results/pure_pipeline_requirement_audit_refresh_20260715_0204_external_spine_routing_after_59c8f56/audit.json
f438681ff6549272a68919092fd6827b9f41d9a9ed6798717f148e81c8c8213a  results/pure_pipeline_requirement_audit_refresh_20260715_0204_external_spine_routing_after_59c8f56/audit.md
55cffa89bdb58ecd9220c9d889fde76dd08858357f3fb042f5fe1b2e2aedc25e  results/pure_pipeline_evidence_bundle_refresh_20260715_0204_external_spine_routing_after_59c8f56/summary.md
9f53bb119f3e979699e19aa5f373a612bcd0608fe65224517c63a91899929823  results/pure_pipeline_evidence_bundle_refresh_20260715_0204_external_spine_routing_after_59c8f56/target_matrix.tsv
aafc3f4d6c260387d2a12db56ff7bde2c78e627531e92fbc90f2e06b0e8f40b8  results/pure_pipeline_evidence_bundle_refresh_20260715_0204_external_spine_routing_after_59c8f56/bundle_manifest.json
```

## 2026-07-15 Prepare-Aware Target Flow

The reproducible target flow now accepts:

```bash
--prepare
```

When enabled, the wrapper regenerates the pure-pipeline compile/link/config
scripts before the readiness preflight, and also forwards `--prepare` into the
build wrapper so the build evidence records that the generated scripts were
refreshed. This keeps the next long `hw_emu` launch tied to the current source
tree instead of relying on old generated files in `.tmp_build`.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration

bash -n \
  scripts/run_pure_pipeline_target_flow.sh \
  scripts/check_pure_pipeline_build_readiness.sh

python3 -m py_compile scripts/audit_pure_pipeline_status.py

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prepare_build_cmd_dryrun_after_9e1f28c \
  --prepare \
  --dry-run \
  --skip-finalize \
  --skip-audit \
  --no-readiness \
  --monitor-tail 5

./scripts/check_pure_pipeline_build_readiness.sh \
  --target hw_emu \
  --label prepare_recommend_after_9e1f28c \
  --allow-active-builders

./scripts/audit_pure_pipeline_status.py \
  --label prepare_command_check_after_9e1f28c \
  --out-dir results/pure_pipeline_requirement_audit_prepare_command_check_after_9e1f28c
```

Dry-run output showed the expected command order without launching Vitis:

```text
prepare_pure_hw_pipeline_build.sh --target hw_emu --build-root ...
run_pure_pipeline_build.sh --target hw_emu --label prepare_build_cmd_dryrun_after_9e1f28c --wait-idle 7200 --idle-poll 60 --idle-settle 0 --prepare
monitor_pure_pipeline_build.sh --target hw_emu ...
```

The dry-run flow environment records:

```text
prepare=1
skip_build=0
dry_run=1
```

The readiness and audit next commands now recommend:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_9e1f28c \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Evidence hashes:

```text
ba70e2150878d16f558bfe326720d1e2b8302f0ef0bd610e2765a585dbc5125b  scripts/run_pure_pipeline_target_flow.sh
8079bbcc6d1ea78133886def8dabe5233aee1884286e410293e603b53acf732b  scripts/check_pure_pipeline_build_readiness.sh
3ee6f030e87740e52721296db1a4ca7afa2f34b9f3b494e005f4742896b104ca  scripts/audit_pure_pipeline_status.py
d7d0485257accd5ef394b327e5468ac62310bb0d918fadae0ba70d221971629a  README.md
718daa54131e3f94598e857cfdeb893eb91f235f430644f4314598769f37dd7d  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prepare_build_cmd_dryrun_after_9e1f28c.env
134a28fde2cd79ea56ac4372820139f8c0cef5bff45f10678aaf47a36c3a9a12  results/pure_pipeline_requirement_audit_prepare_command_check_after_9e1f28c/audit.json
ce460ce9c2fff18e024f3131e630a342734a5d80d5be532d3dea0f879b549b73  results/pure_pipeline_requirement_audit_prepare_command_check_after_9e1f28c/audit.md
```

## 2026-07-15 HW Status Refresh

Question answered at this checkpoint: there is not yet a successful pure
GraSU-ReGraph `hw` build artifact. The only pure-pipeline xclbin currently
present is the correctness-tested `sw_emu` artifact.

Current source state:

```text
branch: codex/pure-hw-pipeline
commit: 963d0e018fd75c636d7ab16cb94ba196adfd6c90
```

Current pure-pipeline xclbins:

```text
present:
  .tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
  sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
  size=6541774 bytes

missing:
  .tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin
  .tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin
```

The current generated `hw_emu` and `hw` build roots have been prepared from the
current source, but the long Vitis builds have not produced xclbins yet:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/prepare_pure_hw_pipeline_build.sh \
  --target hw_emu \
  --build-root .tmp_build/pure_pipeline_hw_emu_stage0
./scripts/prepare_pure_hw_pipeline_build.sh \
  --target hw \
  --build-root .tmp_build/pure_pipeline_hw_stage0
```

Readiness/evidence refresh command:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +e
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing
echo "refresh_rc=$?"
```

The refresh returned `3`, which means the reports were written successfully but
the targets are not ready to claim as built. The blocking facts are:

```text
hw:
  xclbin_exists=no
  readiness_ready=no
  readiness_blocking_count=1
  readiness_external_builders=10
  build_artifacts=PASS count=0 clean_recommended=no

hw_emu:
  xclbin_exists=no
  readiness_ready=no
  readiness_blocking_count=1
  readiness_warning_count=1
  readiness_external_builders=10
  build_artifacts=WARN count=7 clean_recommended=yes
```

The `hw_emu` warning is stale partial build-output under the build root:

```text
bin_search
bin_search.hw_emu.xo
bin_search.hw_emu.xo.compile_summary
bin_search.mdb
dispatch
dispatch.hw_emu.xo.compile_summary
dispatch.mdb
```

Because the next target-flow command uses `--clean-build-artifacts`, these
stale partial artifacts should not be reused by the next real `hw_emu` launch.

Current refresh artifacts:

```text
results/pure_pipeline_evidence_bundle_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/summary.md
results/pure_pipeline_evidence_bundle_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/target_matrix.tsv
results/pure_pipeline_evidence_bundle_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/bundle_manifest.json
results/pure_pipeline_requirement_audit_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/audit.md
results/pure_pipeline_requirement_audit_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/audit.json
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing.txt
.tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing.txt
```

Evidence hashes:

```text
8c8a1065d85e329b8a8a3c8a54c467f48f2101f5be423aa91543d31ec63959f9  results/pure_pipeline_evidence_bundle_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/summary.md
48d2d4cbc9605ff06cd37e6a3e112c5ffa815826cf2e8ff46a086f933abc2606  results/pure_pipeline_evidence_bundle_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/target_matrix.tsv
3f43f01592da469d8011fb8c8837b04472dc2af1b5b2fe13067f2d6bb067a0f6  results/pure_pipeline_evidence_bundle_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/bundle_manifest.json
0c85c46870047d65d1490d7e0859441fd5a66f747845b448ddaa355dc268cff0  results/pure_pipeline_requirement_audit_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/audit.md
3a3bd18cb4ca4fcafab88c35c52fc2cb2c3c23741a2812d005aadf024c569543  results/pure_pipeline_requirement_audit_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing/audit.json
e2c49f27ed266811f5005b1b00ab35ec30edc7569bff4d039bb3476329fb113a  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing.txt
fd13f2b3d479374b9246b2b83ae717c7c0fc4c99e3ca324a8232888b9bd15962  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_20260715_0217_hw_status_no_xclbin_external_spine_routing.txt
```

The active external builder is still the Spine hardware link:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024
```

At this checkpoint the target Spine xclbin was also still missing from that
active directory:

```text
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024/xclbin/spine_partitioned_split_e2e.hw.xclbin
```

The last inspected Vitis log was in routing:

```text
[01:55:59] Finished 4th of 6 tasks (FPGA logic placement).
[01:55:59] Starting logic routing..
[02:04:04] Phase 5 Rip-up And Reroute
[02:04:04] Phase 5.1 Global Iteration 0
```

Next command once the machine is idle enough for a new long build:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_963d0e0 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Only after `hw_emu` links and passes the gate/full smoke should the real `hw`
flow be launched with the same `--prepare`, `--wait-idle`, and
`--clean-build-artifacts` discipline.

## 2026-07-15 Evidence Bundle Builder Hints

The evidence-bundle exporter now carries the first active related/external
builder process from each readiness report into `target_matrix.tsv`. This makes
the compact bundle sufficient to answer not only "how many builders are active"
but also "which process is currently blocking the launch" without reopening the
raw readiness report.

New target-matrix columns:

```text
readiness_related_process_pid
readiness_related_process_elapsed
readiness_related_process_command
readiness_related_process_args_hint
readiness_external_process_pid
readiness_external_process_elapsed
readiness_external_process_command
readiness_external_process_args_hint
```

Source commit:

```text
d5a58f10d3c3c4f3ee568ac622f2e74aee70c5c6
```

Lightweight validation:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile scripts/export_pure_pipeline_evidence_bundle.py
```

Clean evidence refresh:

```bash
cd /home/chuxiao/grasu-regraph-integration
set +e
./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_after_d5a58f1_process_hints
echo "refresh_rc=$?"
```

The command exited `3` after writing readiness, audit, and bundle evidence.
The failure is still the expected launch blocker, not a script crash:

```text
hw:
  xclbin_exists=no
  readiness_ready=no
  readiness_blocking_count=1
  readiness_external_builders=10
  readiness_external_process_pid=3836537
  readiness_external_process_elapsed=01:59:08
  readiness_external_process_command=v++

hw_emu:
  xclbin_exists=no
  readiness_ready=no
  readiness_blocking_count=1
  readiness_warning_count=1
  readiness_external_builders=10
  readiness_external_process_pid=3836537
  readiness_external_process_elapsed=01:59:08
  readiness_external_process_command=v++
  build_artifacts=WARN count=7 clean_recommended=yes

sw_emu:
  xclbin_exists=yes
  xclbin_sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
  smoke_pass=yes
```

The external process hint points at the active Spine hardware link command:

```text
/data/yxx/tools/xilinx/Vitis/2024.1/bin/v++ -l -t hw ...
/data/feiyang/spine-dynamic-graph-builds/restore_split_tiny_20260713_1118/hw_link_133_extratiming_vitis_20260715_0024
```

Current evidence artifacts:

```text
results/pure_pipeline_evidence_bundle_refresh_after_d5a58f1_process_hints/summary.md
results/pure_pipeline_evidence_bundle_refresh_after_d5a58f1_process_hints/target_matrix.tsv
results/pure_pipeline_evidence_bundle_refresh_after_d5a58f1_process_hints/bundle_manifest.json
results/pure_pipeline_requirement_audit_refresh_after_d5a58f1_process_hints/audit.md
results/pure_pipeline_requirement_audit_refresh_after_d5a58f1_process_hints/audit.json
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_after_d5a58f1_process_hints.txt
.tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_after_d5a58f1_process_hints.txt
```

Evidence hashes:

```text
26054c984c7a24a0de22dc0451c7fcedf6c2ac94807964d7bc472fb136e2d27f  scripts/export_pure_pipeline_evidence_bundle.py
46566a39e444ec4d79de641d0e4921494abb93ed07450e4051569a8caa29e49f  results/pure_pipeline_evidence_bundle_refresh_after_d5a58f1_process_hints/summary.md
debbc3a8f8790f67fd2de63274112d3d75df54c1b0f2f5ebcbd977927a62fe02  results/pure_pipeline_evidence_bundle_refresh_after_d5a58f1_process_hints/target_matrix.tsv
13367ed8a5713d144a4f30b3e801b1462542ad9350239aadd47ce5c8fc6abfc8  results/pure_pipeline_evidence_bundle_refresh_after_d5a58f1_process_hints/bundle_manifest.json
624abb3074fa63ba952b5d61382490192cf741ff9b1ba84a0aa649646492613d  results/pure_pipeline_requirement_audit_refresh_after_d5a58f1_process_hints/audit.md
1259cccda360c08c304848563ca44f231f9b4f5754bbab1414e41722001349f1  results/pure_pipeline_requirement_audit_refresh_after_d5a58f1_process_hints/audit.json
bc0a90281cacd2a4dcbf286b2f4a5bc5dad44ca0e8acefe040e17551c02236cf  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_after_d5a58f1_process_hints.txt
70f330f8db7a9dde316630c1ec36d1e13b72e72a3c5461f085165264258eb845  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_after_d5a58f1_process_hints.txt
```

Next command once external Vitis/Vivado builders are gone:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_d5a58f1 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

## 2026-07-15 Source Contract Audit

The requirement audit now records explicit source-level contracts for two
important parts of the pure pipeline:

- GraSU row-offset handoff contract:
  host packs `row_offset[src]` as `begin[63:32], end[31:0]`; the adapter
  decodes the same fields before reading real PMA slots.
- Adapter/ReGraph stream-width contract:
  the stream packet is `ap_axiu<512>`, each edge record is 64 bits
  `(src[31:0], dst[31:0])`, so the steady burst contains 8 edge lanes.

The compact evidence bundle now also exports:

```text
source_proof_matrix.tsv
```

Source commit:

```text
184a90b1bf05e20ef4acdc2e11e7e71fb7b9761b
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py

./scripts/audit_pure_pipeline_status.py \
  --label source_contracts_after_184a90b \
  --out-dir results/pure_pipeline_requirement_audit_source_contracts_after_184a90b

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_source_contracts_after_184a90b/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_source_contracts_after_184a90b
```

Audit status is still intentionally conservative:

```text
blocked_by_missing_artifact: 1
partial: 8
proven: 1
```

The new source-proof matrix says the static contracts are present:

```text
adapter_receives_actual_pma_buffers      yes
adapter_to_regraph_stream                yes
completion_token_barrier                 yes
pma_row_offset_begin_end_contract        yes
prepare_only_boundary_mode               yes
single_context_program                   yes
stream_burst_8_edge_contract             yes
timing_fields                            yes
unit_weight_sssp_packing                 yes
```

The two most relevant new proof contracts are:

```text
pma_row_offset_begin_end_contract:
  host packs row_offset[src] as begin[63:32], end[31:0]; adapter decodes the same fields

stream_burst_8_edge_contract:
  512-bit AXI packet, 64 bits per edge record, 8 edge lanes per burst
```

Evidence artifacts:

```text
results/pure_pipeline_requirement_audit_source_contracts_after_184a90b/audit.json
results/pure_pipeline_requirement_audit_source_contracts_after_184a90b/audit.md
results/pure_pipeline_evidence_bundle_source_contracts_after_184a90b/summary.md
results/pure_pipeline_evidence_bundle_source_contracts_after_184a90b/source_proof_matrix.tsv
results/pure_pipeline_evidence_bundle_source_contracts_after_184a90b/bundle_manifest.json
```

Evidence hashes:

```text
d17e45c4fd3dc5cc04c5829861ec73cbad0ea1bc4d429756851e59008b0e70a3  scripts/audit_pure_pipeline_status.py
3db83b87ec10c7f304c739fa5ac6c2199d07f60ecc44cafbfa4ba765c5d73b35  scripts/export_pure_pipeline_evidence_bundle.py
858adb95f9a61adb0208f7bd9470b9b3780ab03be3d129de3e7c58956469d638  results/pure_pipeline_requirement_audit_source_contracts_after_184a90b/audit.json
0f279f81ba1d7bcc5309163b9bdc092c2b5ef408007a50c1baa1e31ee5f13e29  results/pure_pipeline_requirement_audit_source_contracts_after_184a90b/audit.md
245ad9f57f6d69d45d0edd7b016778cd6d14ddda0d8b58c35228ec653ba11a39  results/pure_pipeline_evidence_bundle_source_contracts_after_184a90b/summary.md
eff8ac53e119cb56210c40a1b3add23f6847b9296ef136d17dd0d4b38c4268b9  results/pure_pipeline_evidence_bundle_source_contracts_after_184a90b/source_proof_matrix.tsv
791a98ddbfd589bbe6684236ad4704638b0f5e89757ed641fb73f085b19eb670  results/pure_pipeline_evidence_bundle_source_contracts_after_184a90b/bundle_manifest.json
```

This does not replace the required `hw_emu`/`hw` validation. It makes the
pre-hardware claim sharper: the current source expresses the intended
PMA-to-stream contract, and the remaining gap is still producing and validating
the actual pure-pipeline `hw_emu` and `hw` xclbins.

## 2026-07-15 Source Contract Launch Gate

The target-flow wrapper now runs a fast source-contract preflight before the
readiness/build phases. This prevents spending hours on `hw_emu` or `hw` if the
source no longer satisfies the PMA handoff, completion-barrier, stream-width,
unit-weight, timing, or boundary-preparation contracts.

New script:

```text
scripts/check_pure_pipeline_source_contracts.py
```

Target-flow behavior:

```text
run_pure_pipeline_target_flow.sh
  -> check_pure_pipeline_source_contracts.py
  -> check_pure_pipeline_build_readiness.sh
  -> run_pure_pipeline_build.sh
  -> monitor/finalize/audit
```

The gate is enabled by default. Use `--no-source-contracts` only for debugging a
broken local tree; normal `hw_emu/hw` launches should keep the gate enabled.

Source commit:

```text
767644433338463d2bcb3b9797146d2712a301f3
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/check_pure_pipeline_source_contracts.py \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py
bash -n scripts/run_pure_pipeline_target_flow.sh

./scripts/check_pure_pipeline_source_contracts.py \
  --label source_contract_gate_after_7676444 \
  --out-file .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_contracts_after_7676444.tsv

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label source_contract_gate_flow_after_7676444 \
  --skip-build \
  --skip-finalize \
  --skip-audit \
  --no-readiness \
  --monitor-tail 5
```

The standalone and target-flow source-contract gates both passed all nine
required proofs:

```text
adapter_receives_actual_pma_buffers      yes
adapter_to_regraph_stream                yes
completion_token_barrier                 yes
pma_row_offset_begin_end_contract        yes
prepare_only_boundary_mode               yes
single_context_program                   yes
stream_burst_8_edge_contract             yes
timing_fields                            yes
unit_weight_sssp_packing                 yes
```

The metadata-only target flow also confirmed:

```text
source_contract_check=1
skip_build=1
skip_finalize=1
skip_audit=1
```

It did not start Vitis. The monitor still reports no pure-pipeline
`hw_emu.xclbin` and shows the unrelated Spine hardware link as an external
Vitis/Vivado process.

Evidence artifacts:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_contracts_after_7676444.tsv
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_contracts_target_flow_source_contract_gate_flow_after_7676444.tsv
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_source_contract_gate_flow_after_7676444.env
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_source_contract_gate_flow_after_7676444.txt
```

Evidence hashes:

```text
15f77140fd4aa873a3bb5f189ef5fed640a0d890381a6cb6b5bf3eeab4c646f8  scripts/check_pure_pipeline_source_contracts.py
79862c9e6dedbd4f9556e817bf80e028988c315f467b6237abae3c36a5408898  scripts/run_pure_pipeline_target_flow.sh
23899c69e5665beb9e624a9ecb4901444c286dd716fb77d3ac9d80f084a312fa  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_contracts_after_7676444.tsv
23899c69e5665beb9e624a9ecb4901444c286dd716fb77d3ac9d80f084a312fa  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_contracts_target_flow_source_contract_gate_flow_after_7676444.tsv
92eb2a2b6c04a4413a36b25285b2f1caa8a66f83dd774884f71d3a389fc56e4c  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_source_contract_gate_flow_after_7676444.env
a5ff8d310f2ff8c906b53307372a6359c65d3fce31f630212dc15e4ca4ad3a41  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_source_contract_gate_flow_after_7676444.txt
```

The next real launch command is unchanged except that it now automatically runs
the source-contract gate first:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_7676444 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

## 2026-07-15 Readiness Bundle Source Contracts

The readiness refresh command now records the source-contract gate before it
runs build-readiness checks and exports the requirement audit/evidence bundle.
This makes every status bundle include a durable proof that the current source
still satisfies the pure-pipeline PMA handoff, completion-token barrier,
512-bit AXI stream, unit-weight SSSP packing, timing, and boundary-preparation
contracts.

Source commit:

```text
3efa568b3f9388c721f87192c65792f084c3b5d3
```

Changed files:

```text
README.md
scripts/audit_pure_pipeline_status.py
scripts/refresh_pure_pipeline_readiness_bundle.sh
```

Behavior added:

```text
refresh_pure_pipeline_readiness_bundle.sh
  -> check_pure_pipeline_source_contracts.py
  -> check_pure_pipeline_build_readiness.sh for hw_emu/hw
  -> audit_pure_pipeline_status.py
  -> export_pure_pipeline_evidence_bundle.py
```

The refresh script still never starts Vitis. A nonzero refresh exit remains a
status signal from readiness checks, not a failed build launch.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/check_pure_pipeline_source_contracts.py \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py
bash -n \
  scripts/refresh_pure_pipeline_readiness_bundle.sh \
  scripts/run_pure_pipeline_target_flow.sh

./scripts/refresh_pure_pipeline_readiness_bundle.sh \
  --label refresh_source_contracts_after_3efa568
```

Result:

```text
source_contracts: PASS, 9/9 required proofs
hw_emu readiness: ready=no, out_xclbin=MISSING, active_builders external=10
hw readiness: ready=no, out_xclbin=MISSING, active_builders external=10
audit status counts: {"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
refresh exit code: 3
```

The exit code is expected for this snapshot because an unrelated Spine hardware
link is still active. No pure-pipeline `hw_emu` or `hw` xclbin exists yet:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/build/grasu_regraph_pure_pipeline.hw_emu.xclbin  MISSING
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin          MISSING
```

Evidence artifacts:

```text
.tmp_build/pure_pipeline_source_contracts/source_contracts_refresh_source_contracts_after_3efa568.tsv
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_source_contracts_after_3efa568.txt
.tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_source_contracts_after_3efa568.txt
results/pure_pipeline_requirement_audit_refresh_source_contracts_after_3efa568/audit.json
results/pure_pipeline_requirement_audit_refresh_source_contracts_after_3efa568/audit.md
results/pure_pipeline_evidence_bundle_refresh_source_contracts_after_3efa568/summary.md
results/pure_pipeline_evidence_bundle_refresh_source_contracts_after_3efa568/bundle_manifest.json
results/pure_pipeline_evidence_bundle_refresh_source_contracts_after_3efa568/source_proof_matrix.tsv
```

Evidence hashes:

```text
4824723560ff71e349b1e3ace8b6a038fe05bcd2e827421bebbea6c394c90f4b  scripts/refresh_pure_pipeline_readiness_bundle.sh
5cee7bc96c2450f01b9d1f0578156f2c3f33e6b3c6cdc0ca7eceb6062806243f  scripts/audit_pure_pipeline_status.py
13799040cd4de3b958802e34524bd3714785515ae1cfac97ba2ff62a689209b7  README.md
23899c69e5665beb9e624a9ecb4901444c286dd716fb77d3ac9d80f084a312fa  .tmp_build/pure_pipeline_source_contracts/source_contracts_refresh_source_contracts_after_3efa568.tsv
b758646733b7864feb4e8c451b788bbe5cfce803fe6a4b26b638cc9582a7ebd0  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_refresh_source_contracts_after_3efa568.txt
61c600965196a14f4648a0e56175ca369ec4b88046a2887b55ef59122eecf710  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_refresh_source_contracts_after_3efa568.txt
dc13070845eefe3ea5f1a392ef29443cce971e38143c7cea4250b21907ecd4b9  results/pure_pipeline_requirement_audit_refresh_source_contracts_after_3efa568/audit.json
675030c86db61c5a0d1d89d3263b0eac04154abbb5e0992516447d324a0b72e7  results/pure_pipeline_requirement_audit_refresh_source_contracts_after_3efa568/audit.md
b8143dad4d39f334b054adb505dc81f773ea7d1d363e69e6d23d1d034933f4da  results/pure_pipeline_evidence_bundle_refresh_source_contracts_after_3efa568/summary.md
8f24586468831bf691ca1cb6e580369759a9b1329b8d028bd245427da4f98d34  results/pure_pipeline_evidence_bundle_refresh_source_contracts_after_3efa568/bundle_manifest.json
eff8ac53e119cb56210c40a1b3add23f6847b9296ef136d17dd0d4b38c4268b9  results/pure_pipeline_evidence_bundle_refresh_source_contracts_after_3efa568/source_proof_matrix.tsv
```

Next real launch command after external Vitis/Vivado builders are idle:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_3efa568 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

## 2026-07-15 Current HEAD SW_EMU Evidence

After committing the readiness-bundle source-contract integration, the existing
pure-pipeline `sw_emu` xclbin was re-finalized against the current integration
HEAD. This did not rebuild hardware or start Vitis linking; it rebuilt only the
host binary, ran the `sw_emu` smoke suite, and regenerated the same-input
comparison against the current host/zero-cost and Spine baselines.

Source commit:

```text
d2ae29825e1b37e32a59f1756bdcb717bc2c687a
```

Validation command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/finalize_pure_pipeline_build.sh \
  --target sw_emu \
  --label swemu_refresh_after_d2ae298 \
  --build-host \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 180 \
  --timeout 600
```

Smoke result:

```text
tiny_chain_v16       chain       PASS  mismatches=0 final_edges=15 supersteps=16 event_e2e_ms=5844.559499
tiny_star_v16_u12    hot-source  PASS  mismatches=0 final_edges=28 supersteps=2  event_e2e_ms=730.792989
tiny_spread_v16_u8   spread      PASS  mismatches=0 final_edges=24 supersteps=16 event_e2e_ms=5660.896028
tiny_hotdst_v64_u32  hot-dest    PASS  mismatches=0 final_edges=95 supersteps=16 event_e2e_ms=6053.124932
```

Same-input comparison remains a correctness/control-flow comparison for the
pure pipeline because the pure timing is still `sw_emu`, not hardware
performance:

```text
tiny_chain_v16       host_zero_cost_ms=6.127929 spine_kernel_e2e_ms=1.58718 pure_target=sw_emu pure_event_e2e_ms=5844.559499
tiny_star_v16_u12    host_zero_cost_ms=2.526626 spine_kernel_e2e_ms=1.57177 pure_target=sw_emu pure_event_e2e_ms=730.792989
tiny_spread_v16_u8   host_zero_cost_ms=5.743649 spine_kernel_e2e_ms=1.59870 pure_target=sw_emu pure_event_e2e_ms=5660.896028
tiny_hotdst_v64_u32  host_zero_cost_ms=6.202223 spine_kernel_e2e_ms=2.26057 pure_target=sw_emu pure_event_e2e_ms=6053.124932
```

Audit refresh:

```bash
./scripts/audit_pure_pipeline_status.py \
  --label swemu_refresh_after_d2ae298 \
  --out-dir results/pure_pipeline_requirement_audit_swemu_refresh_after_d2ae298
./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_swemu_refresh_after_d2ae298/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_swemu_refresh_after_d2ae298
```

Audit result:

```text
status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
sw_emu: xclbin=yes smoke=yes
hw_emu: xclbin=no smoke=no
hw: xclbin=no smoke=no
```

Evidence artifacts:

```text
results/pure_pipeline_sw_emu_smoke_gate_swemu_refresh_after_d2ae298/summary.tsv
results/pure_pipeline_sw_emu_smoke_swemu_refresh_after_d2ae298/summary.tsv
results/pure_pipeline_sw_emu_smoke_swemu_refresh_after_d2ae298/run.env
results/pure_pipeline_sw_emu_compare_swemu_refresh_after_d2ae298/comparison.tsv
results/pure_pipeline_sw_emu_compare_swemu_refresh_after_d2ae298/comparison.md
.tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_swemu_refresh_after_d2ae298.env
.tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_swemu_refresh_after_d2ae298_evidence.tsv
results/pure_pipeline_requirement_audit_swemu_refresh_after_d2ae298/audit.json
results/pure_pipeline_evidence_bundle_swemu_refresh_after_d2ae298/summary.md
results/pure_pipeline_evidence_bundle_swemu_refresh_after_d2ae298/target_matrix.tsv
```

Evidence hashes:

```text
b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862  .tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
cb40efbffe3a091be8a8bffe03c2ee364c794a2cddb315a0571601b38c2cad5d  .tmp_build/pure_pipeline_host_stage0/pure_pipeline_host
7e9952a65d79f878c5b42272fcba30fb7217adb07ca4ac9260e2f924e2e59418  results/pure_pipeline_sw_emu_smoke_gate_swemu_refresh_after_d2ae298/summary.tsv
aa32da7edf105e965cae4da8d2ebb227397ff0450158bdfa8178944b0fdb6747  results/pure_pipeline_sw_emu_smoke_swemu_refresh_after_d2ae298/summary.tsv
6cb743f7e987784638d1b89ad99d697c161c60ca8d32457137c55d35ac7cf635  results/pure_pipeline_sw_emu_smoke_swemu_refresh_after_d2ae298/run.env
eee46991cf11ec216ea5aacba49cf7719b440e775af1b2f5b230b3f4daf9941c  results/pure_pipeline_sw_emu_compare_swemu_refresh_after_d2ae298/comparison.tsv
4caf3ffcdebb423c06c345edfcf4a12f23bb7e858e4c818eb55ebaadd707c05a  results/pure_pipeline_sw_emu_compare_swemu_refresh_after_d2ae298/comparison.md
5c4a59d580f4909f6d39d0ebf8310bd2eb0b01be7496ada8f739c40f654c03ff  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_swemu_refresh_after_d2ae298.env
21472a3221db71de46d589f4a631de2ba0a79454e8929915cc63de973dd935c3  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_swemu_refresh_after_d2ae298_evidence.tsv
16c9d7de156eae03d6dd3833bf50c0917a909f45406a4404ba31bf32bc7ca89d  results/pure_pipeline_requirement_audit_swemu_refresh_after_d2ae298/audit.json
c6df361e2ee6f3f612f6a5b36c69313d882ae6bd7ae122459ad0e5b4c2fd2a66  results/pure_pipeline_evidence_bundle_swemu_refresh_after_d2ae298/summary.md
c1b53a11937264bc39ff0572a1fb06e55732728a388c7da55bd313217b33116b  results/pure_pipeline_evidence_bundle_swemu_refresh_after_d2ae298/target_matrix.tsv
```

## 2026-07-15 HW_EMU Launch Packet

A launch-packet helper was added so the next long `hw_emu` or `hw` attempt can
start from a single reproducible preflight bundle. The helper does not start
Vitis. It records source-contract status, build-readiness status, current
artifact hashes, audit/evidence bundle paths, and the exact target-flow command
to run after the machine is idle.

Source commit:

```text
f6ccd4d3dfd7ae17d391f6441f0cb52bc6c1145c
```

Changed files:

```text
README.md
scripts/create_pure_pipeline_launch_packet.sh
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n \
  scripts/create_pure_pipeline_launch_packet.sh \
  scripts/refresh_pure_pipeline_readiness_bundle.sh \
  scripts/run_pure_pipeline_target_flow.sh
python3 -m py_compile \
  scripts/check_pure_pipeline_source_contracts.py \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --label launch_packet_hwemu_after_f6ccd4d \
  --flow-label after_f6ccd4d
```

Result:

```text
source_contract_status=0
readiness_status=3
audit_status=0
bundle_status=0
hw_emu xclbin=MISSING
active_builders external=10
launch_packet_exit=3
```

The nonzero launch-packet exit is expected in this snapshot: strict readiness
still sees the unrelated Spine hardware link as active Vitis/Vivado work. The
packet still produced all metadata and the exact launch command.

Launch command captured in the packet:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_f6ccd4d \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Launch-packet artifacts:

```text
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/README.md
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/launch_command.sh
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/launch_packet.env
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/artifact_hashes.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/source_contracts.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/readiness_hw_emu.txt
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/audit/audit.json
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/evidence_bundle/summary.md
```

Evidence hashes:

```text
c9bc116ec5f0b648e77a4c80adc7454078bc2731e0c9ef881f1700c6e28b9828  scripts/create_pure_pipeline_launch_packet.sh
83ea4a487f8ba7d335129bc293ee9d53a3bbdbecb66a23ffe032ebf03d13c63d  README.md
3dcfaf774acf45aec2a0aa80b9e05a26e9443c0fa0bd33b0b5b21170deba25d4  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/README.md
204a5889d3b429b5372b137f578b7e00e7aa837d2841ed79ea5bb9e1e3a9d6b6  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/launch_command.sh
6cba6dfd318457cd40b956466dd0e711128aa395520ec036f3d10bc03d60f46f  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/launch_packet.env
6c66e93ee2ad27c95169da4c51e73972c47fd9a01ed00163b5f30e7ceb02c833  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/artifact_hashes.tsv
23899c69e5665beb9e624a9ecb4901444c286dd716fb77d3ac9d80f084a312fa  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/source_contracts.tsv
dd10bd8729840e1a1c8a59e9c2dd59b8c156f73f7724bc7dc65daee83bcb8608  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/readiness_hw_emu.txt
fc92e105b0413af9c66ba4a26344bd012726833af3ec8aa8fcc23b5bdc10e6cf  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/audit/audit.json
fb4cfc29d58744d933a248b4146b762db364cc921abe3b127937b312637d58f8  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_f6ccd4d/evidence_bundle/summary.md
```

## 2026-07-15 Build Script Contract Audit

The source-contract gate now also checks that the generated `hw_emu` and `hw`
build scripts actually cover the intended pure pipeline. This avoids a subtle
failure mode where source files look correct, but the long Vitis build would be
launched with a stale or incomplete manifest, compile command, link command, or
connectivity config.

New required proof:

```text
target_build_scripts_cover_pure_pipeline
```

It checks both `.tmp_build/pure_pipeline_hw_emu_stage0` and
`.tmp_build/pure_pipeline_hw_stage0` for:

```text
manifest.env:
  TARGET, LINK_CFG, OUT_XCLBIN, COMPILE_COMMANDS, LINK_COMMAND
compile_commands.sh:
  GraSU process_cache/process_ddr with GRASU_ENABLE_COMPLETION_TOKEN
  pma_completion_barrier, pma_to_regraph_adapter, lksg_stream
  ReGraph kernelApply and kernelHBMWrapper
link_command.sh:
  target-specific v++ --link command
  target-specific grasu_regraph_pure_pipeline.<target>.xclbin
  all required .xo inputs
pure_pipeline_<target>.cfg:
  process_cache/process_ddr instances
  four completion_token streams into pma_completion_barrier
  pma_to_regraph_adapter -> lksg_stream AXI stream
  adapter PMA HBM bindings and ReGraph apply/HBM stream
```

Source commit:

```text
558b4ac913fb9184f3485624968a69f669ff2cd2
```

Changed files:

```text
scripts/audit_pure_pipeline_status.py
scripts/check_pure_pipeline_source_contracts.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/check_pure_pipeline_source_contracts.py \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py

./scripts/check_pure_pipeline_source_contracts.py \
  --label build_script_contract_dirty \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_build_script_contract_dirty.tsv

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --label launch_packet_build_script_contract_after_558b4ac \
  --flow-label after_558b4ac
```

Result:

```text
required_count=10
failed_count=0
target_build_scripts_cover_pure_pipeline ok=yes
launch_packet_exit=3
readiness_status=3
active_builders external=10
hw_emu xclbin=MISSING
```

The launch packet still exits nonzero because an unrelated Spine hardware link
is active. The source-contract part is now stronger and passes all ten required
proofs.

Launch-packet artifacts:

```text
.tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/source_contracts.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/readiness_hw_emu.txt
.tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/audit/audit.json
.tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/evidence_bundle/summary.md
.tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/evidence_bundle/source_proof_matrix.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/launch_command.sh
```

Evidence hashes:

```text
c40c5e3c67d49f8beef11c8e226981794bd779594e1554f7224ef5bf3a2a061f  scripts/audit_pure_pipeline_status.py
2bfb60a2fd5b013fda960bc4edc0d8cb4fa11aeb845a143e4789743df59ccf11  scripts/check_pure_pipeline_source_contracts.py
0bb424143146be4d2acb062f4c7763a4740bca09e75ab0b8e9565a4272095ea0  .tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/source_contracts.tsv
ffcea023b31696188472602142f3689b99a081d9fe26a686e313c220d53169ae  .tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/readiness_hw_emu.txt
af19b5d7437617f65aaebaac316ac3901498e217e87366712a5907647084c537  .tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/audit/audit.json
64dfc7e4819299f08f922fb08db3176128df1367db5a1a8e698ccc88f7053259  .tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/evidence_bundle/summary.md
eefc5b093642a4ad98f89ca7a950f2db993b2dbe891c753742809fd7bb50e608  .tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/evidence_bundle/source_proof_matrix.tsv
23b2fda96f2c5bc4fd1b5d7fa2d4c43b819467580aedb133fb0ff20d5cb62a11  .tmp_build/pure_pipeline_launch_packet_launch_packet_build_script_contract_after_558b4ac/launch_command.sh
```

Next launch command after external builders are idle:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_558b4ac \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

## Host runtime/config contract gate

The source-contract gate now includes one more required proof:

```text
host_runtime_matches_generated_config
```

This closes a launch-time gap left by the previous source checks. The earlier
checks proved that the adapter, barrier, stream little-GS wrapper, generated
compile scripts, and link configs existed. This new proof checks that the host
runtime actually opens the same CU names that the `hw_emu` and `hw` link
configs generate, and that it binds the key PMA, ReGraph, barrier, and timing
arguments expected by the pure pipeline.

It currently checks:

```text
tools/pure_pipeline_host.cpp:
  bin_search_1..4, dispatch_1
  process_cache_1/2, process_ddr_1/2
  pma_completion_barrier_1, pma_to_regraph_adapter_1
  lksg_stream_1, kernelApply_1, kernelHBMWrapper_1
  adapter args 0..3 are real pma_dev[0..3]
  adapter arg 4 is row_dev[0]
  adapter waits on barrier_event for step 0
  lksg/hbm/apply are launched in the same pipeline queue
  GraSU/barrier/adapter/lksg/apply/event_e2e timing fields are printed

.tmp_build/pure_pipeline_hw_emu_stage0/config/pure_pipeline_hw_emu.cfg
.tmp_build/pure_pipeline_hw_stage0/config/pure_pipeline_hw.cfg:
  matching nk= lines for all host-opened CUs
  four PMA completion_token streams into pma_completion_barrier_1
  pma_to_regraph_adapter_1.edge_burst_out -> lksg_stream_1.edge_burst_in
  adapter PMA HBM ports and ReGraph apply/HBM ports
```

Source commit:

```text
db94abdb2e04c04f3cb290cec94f355c986e5af4
```

Changed files:

```text
scripts/audit_pure_pipeline_status.py
scripts/check_pure_pipeline_source_contracts.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/check_pure_pipeline_source_contracts.py \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py

./scripts/check_pure_pipeline_source_contracts.py \
  --label host_runtime_contract_after_db94abd \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_host_runtime_contract_after_db94abd.tsv

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --label launch_packet_host_runtime_contract_after_db94abd \
  --flow-label after_db94abd
```

Result:

```text
required_count=11
failed_count=0
host_runtime_matches_generated_config ok=yes
launch_packet_exit=3
readiness_status=3
active_builders external=2
hw_emu xclbin=MISSING
```

The nonzero launch-packet exit is expected in the current machine state. It is
caused by the missing pure `hw_emu` xclbin and unrelated active Spine `v++`
processes. It does not indicate a source-contract failure.

Launch-packet artifacts:

```text
.tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/source_contracts.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/readiness_hw_emu.txt
.tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/audit/audit.json
.tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/evidence_bundle/summary.md
.tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/evidence_bundle/source_proof_matrix.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/launch_command.sh
```

Evidence hashes:

```text
40949d5498b330c84a366669bb8868928ea039eb4399c9494f79af2ab26cbf55  scripts/audit_pure_pipeline_status.py
d4faaf573970b2f7b88c31fc3bb451c88d76cd1211ea20d0fece6f5d0fef1f2e  scripts/check_pure_pipeline_source_contracts.py
572e419a9a0b213f94f43e4cc57bdc50815a4a2ad577fe2384d802a284f25123  .tmp_build/pure_pipeline_source_contracts/source_contracts_host_runtime_contract_after_db94abd.tsv
572e419a9a0b213f94f43e4cc57bdc50815a4a2ad577fe2384d802a284f25123  .tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/source_contracts.tsv
292962aa7a8b2632291c12280f39444abe0ff2789bb1eb1e981f553837b3490d  .tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/readiness_hw_emu.txt
066205d99ed27efeb804fabb3c643f7d156004e2fcb2ae72dfff1ebac440c669  .tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/audit/audit.json
bc19f5a852c4d60b23723cc61e492d0e7457b502ccaa6829df701fa7b327a968  .tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/evidence_bundle/summary.md
3d158ed0cbee9d910fc0a2faa4a28b06a114d2e0071196ae6fcefb8293844356  .tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/evidence_bundle/source_proof_matrix.tsv
618fffb76bb1e20fc97c11c86dd6aa1b7ae3e0929eadb5d4211d14e3fb296f86  .tmp_build/pure_pipeline_launch_packet_launch_packet_host_runtime_contract_after_db94abd/launch_command.sh
```

Next launch command after external builders are idle:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_db94abd \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

## Smoke input identity gate

The baseline comparison now has an explicit same-input checker:

```text
scripts/check_smoke_input_identity.py
```

The checker verifies the tracked smoke manifest against:

```text
workloads/sssp_benchmark_smoke/manifest.tsv
results/grasu_regraph_smoke_device_export_combined_hw_stage1/summary.tsv
results/spine_edge_file_smoke_hw_stage2_split_xclbin/summary.tsv
results/pure_pipeline_sw_emu_smoke_swemu_refresh_after_d2ae298/summary.tsv
```

For each case it checks:

```text
vertices
final edge count
source vertex
superstep count
host baseline status and mismatch count
Spine status and error count
pure-pipeline status and mismatch count
SHA256(manifest .sssp.edges)
SHA256(host-exported .from_grasu.sssp.edges)
SHA256(Spine --edge-file)
```

This is deliberately stricter than matching case names. It proves that the
current host baseline, zero-cost handoff baseline, Spine edge-file baseline,
and pure `sw_emu` smoke result are aligned on the same generated smoke inputs.

Source commit:

```text
8fb03ba2623e7e1ce38248c7d6d800d84edf1c34
```

Changed files:

```text
scripts/check_smoke_input_identity.py
scripts/audit_pure_pipeline_status.py
scripts/export_pure_pipeline_evidence_bundle.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/check_smoke_input_identity.py \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py

./scripts/check_smoke_input_identity.py \
  --label after_8fb03ba

./scripts/audit_pure_pipeline_status.py \
  --label after_8fb03ba \
  --out-dir results/pure_pipeline_requirement_audit_after_8fb03ba_identity

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_after_8fb03ba_identity/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_after_8fb03ba_identity
```

Result:

```text
identity case_count=4
identity failed_count=0
requirement 9 status=proven
bundle includes input_identity_matrix.tsv
```

Identity rows:

```text
tiny_chain_v16       ok=yes vertices=16 final_edges=15 source=0 supersteps=16 edge_sha256=711894d41cd1e0e07540996af0b323bfdc5702cf520ddb09de940a4eef226a1c
tiny_star_v16_u12    ok=yes vertices=16 final_edges=28 source=0 supersteps=2  edge_sha256=4faccf735da914557d790f1699de1cd11c490a5726e92e115d0a46ae6c2f5d96
tiny_spread_v16_u8   ok=yes vertices=16 final_edges=24 source=0 supersteps=16 edge_sha256=21c74c7c65edb2c5ee0c7317190f3a5c6a972d0616407a517ab0bbeba58c0a8f
tiny_hotdst_v64_u32  ok=yes vertices=64 final_edges=95 source=0 supersteps=16 edge_sha256=70e040c2e5f8da3ad51410094f8c1d99e0fadeea36c40bd147373dc0529f28a7
```

Artifacts:

```text
results/smoke_input_identity_after_8fb03ba/identity.tsv
results/smoke_input_identity_after_8fb03ba/identity.md
results/pure_pipeline_requirement_audit_after_8fb03ba_identity/audit.json
results/pure_pipeline_evidence_bundle_after_8fb03ba_identity/summary.md
results/pure_pipeline_evidence_bundle_after_8fb03ba_identity/input_identity_matrix.tsv
results/pure_pipeline_evidence_bundle_after_8fb03ba_identity/bundle_manifest.json
```

Evidence hashes:

```text
329692c8d7f1f8330b4862dd2293d0b34dbc41e3fa4c4420f1782ddc49d6ebf7  scripts/check_smoke_input_identity.py
336d66fdf694b168cbb9899263dcbdeddda1ac9af6c55b77cd7c7ee2f220621c  scripts/audit_pure_pipeline_status.py
b57a06e40524c1788696bdab1a9ba907e3e8f08fbb73efed6d8638e9fb299f01  scripts/export_pure_pipeline_evidence_bundle.py
a4bb92d0bc393fb051570aff3f3ebd2f54be825cad24592bcc4d1916b7448242  results/smoke_input_identity_after_8fb03ba/identity.tsv
d7352a68754037743b4226401969d8356c36efa264edde61c438eea4e5674f87  results/smoke_input_identity_after_8fb03ba/identity.md
d0404a5518faa86e35b988155336d1d416fb7773db46990a22ef1813ff22f44d  results/pure_pipeline_requirement_audit_after_8fb03ba_identity/audit.json
c765e2a92ec4b5f1ebd99cfdcef6d80f57908d0d4d8bbd5adc61883527e4afd4  results/pure_pipeline_evidence_bundle_after_8fb03ba_identity/summary.md
9d599a964fbb5c971a2404ee1f81d0f82494fb10f5595ffe40134d0bf36d9547  results/pure_pipeline_evidence_bundle_after_8fb03ba_identity/input_identity_matrix.tsv
d3ef74745f6bc69286ecec0523e24d0e47225a962fa768d0e6d5d091a3fbea68  results/pure_pipeline_evidence_bundle_after_8fb03ba_identity/bundle_manifest.json
```

## Boundary prepare-only refresh after 213000d

The machine is still running an unrelated Spine `hw` Vitis/Vivado build, so no
new pure `hw_emu` or `hw` build was launched in this step. Instead, the
`V <= 65536` first-stage evidence was refreshed on the current branch head.

Source commit:

```text
213000dffbaaf4b0cdbbb55569551908e8bd5e07
```

Validation command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_prepare_check.sh \
  --preset boundary \
  --out-dir results/pure_pipeline_prepare_boundary_after_213000d \
  --timeout 240

./scripts/audit_pure_pipeline_status.py \
  --label boundary_after_213000d \
  --out-dir results/pure_pipeline_requirement_audit_boundary_after_213000d

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_boundary_after_213000d/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_boundary_after_213000d
```

Result:

```text
boundary_star_v65536_u4096
  status=PASS
  vertices=65536
  updates=4096
  final_edges=69632
  pma_slots=1052672
  row_offset_words=65537
  binary_segments=65792
  partition_size=65536
  little_dst_buffer=65536
  unit_weight=1

boundary_spread_v65536_u4096
  status=PASS
  vertices=65536
  updates=4096
  final_edges=69632
  pma_slots=1048576
  row_offset_words=65537
  binary_segments=65536
  partition_size=65536
  little_dst_buffer=65536
  unit_weight=1
```

Interpretation:

```text
Requirement 6 remains partial in the audit because pure hw_emu/hw execution is
still missing. The refreshed evidence does prove that the current host
preparation path, GraSU PMA packing, row-offset metadata, CPU oracle setup, and
unit-weight SSSP boundary parameters work at V=65536.
```

Artifacts:

```text
results/pure_pipeline_prepare_boundary_after_213000d/summary.tsv
results/pure_pipeline_prepare_boundary_after_213000d/run.env
workloads/sssp_benchmark_boundary/manifest.tsv
results/pure_pipeline_requirement_audit_boundary_after_213000d/audit.json
results/pure_pipeline_evidence_bundle_boundary_after_213000d/summary.md
results/pure_pipeline_evidence_bundle_boundary_after_213000d/bundle_manifest.json
```

Evidence hashes:

```text
6fe0469e74f8ce30dc072d3c0c09c69b9c27178582428dd5d4067d9b41c312e3  results/pure_pipeline_prepare_boundary_after_213000d/summary.tsv
c6eb1a7dbd3160047524682acfcdcb7ce3b6e4254aaa2ef2e4b035660e0c2b0c  results/pure_pipeline_prepare_boundary_after_213000d/run.env
e8110d3b222ab35f3ca27a646128e4b864d6dbfd5450dacc79e0ee6f23170a62  workloads/sssp_benchmark_boundary/manifest.tsv
093a9933c6c191044fddc6dfda12d7c989e4a583f0e66c6a30e8bab30e0ebae8  results/pure_pipeline_requirement_audit_boundary_after_213000d/audit.json
5479a6be92b68a37d6db0a3c0dc0718cc9d458e1f6145d1812ae85241bc95f91  results/pure_pipeline_evidence_bundle_boundary_after_213000d/summary.md
409a4f192f6563857140840ba23b242f34967ca4a134388f7e119c203ba0a8df  results/pure_pipeline_evidence_bundle_boundary_after_213000d/bundle_manifest.json
```

## Xclbin metadata contract gate

The source/config checks now have a post-link counterpart:

```text
scripts/check_pure_pipeline_xclbin_contract.py
```

This checker reads the built `.xclbin.info` metadata and verifies that the
actual linked binary contains the required pure-pipeline kernels, CU instances,
adapter/barrier signatures, completion-token ports, and recorded link
connectivity. This is stronger than checking source files alone because it
inspects the produced xclbin metadata.

Current verified target:

```text
sw_emu
```

The `hw_emu` and `hw` xclbin contracts are still missing because those xclbins
have not been built yet.

Source commit:

```text
566dd44f9c076b4df6fa167a79e3706b33dc8900
```

Changed files:

```text
scripts/check_pure_pipeline_xclbin_contract.py
scripts/audit_pure_pipeline_status.py
scripts/export_pure_pipeline_evidence_bundle.py
```

Validation command:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/check_pure_pipeline_xclbin_contract.py \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py \
  scripts/check_pure_pipeline_source_contracts.py

./scripts/check_pure_pipeline_xclbin_contract.py \
  --target sw_emu \
  --label after_566dd44

./scripts/audit_pure_pipeline_status.py \
  --label xclbin_after_566dd44 \
  --out-dir results/pure_pipeline_requirement_audit_xclbin_after_566dd44

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_xclbin_after_566dd44/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_xclbin_after_566dd44
```

Result:

```text
target=sw_emu
check_count=9
failed_count=0
xclbin_exists=yes
xclbin_sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
info_exists=yes
info_sha256=8b0cf0c3b63ea7d623a599af4db65c4464aae8fadc93e07c089d374bbc2b0f04
required_kernels=yes
required_instances=yes
kernel_metadata_contract=yes
link_connectivity_contract=yes
```

The evidence bundle target matrix now includes:

```text
sw_emu  xclbin_exists=yes  xclbin_contract_pass=yes
hw_emu  xclbin_exists=no   xclbin_contract_pass=no
hw      xclbin_exists=no   xclbin_contract_pass=no
```

Artifacts:

```text
.tmp_build/pure_pipeline_xclbin_contracts/xclbin_contract_sw_emu_after_566dd44.tsv
.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
.tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin.info
results/pure_pipeline_requirement_audit_xclbin_after_566dd44/audit.json
results/pure_pipeline_evidence_bundle_xclbin_after_566dd44/summary.md
results/pure_pipeline_evidence_bundle_xclbin_after_566dd44/target_matrix.tsv
results/pure_pipeline_evidence_bundle_xclbin_after_566dd44/bundle_manifest.json
```

Evidence hashes:

```text
3157fa749d2d61e2417192e4f49de9596c5995367f79753d5fb33479866b5646  scripts/check_pure_pipeline_xclbin_contract.py
0250aa12c3522794b210a08dda4ad9855a712fb374e5313f7e5a1336f262320f  scripts/audit_pure_pipeline_status.py
e21f5bc00a02600e8ff3a00737a89885cc842b7819984b043747181d5fb10281  scripts/export_pure_pipeline_evidence_bundle.py
e41cce545651d7e38c6ba8c0ed559d212055e61128194f82e6c443e0075929d1  .tmp_build/pure_pipeline_xclbin_contracts/xclbin_contract_sw_emu_after_566dd44.tsv
b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862  .tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
8b0cf0c3b63ea7d623a599af4db65c4464aae8fadc93e07c089d374bbc2b0f04  .tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin.info
c424538b54d3cfb585ff356f992f8b94a684f8b6ae12d8100fd2e24db24a16ea  results/pure_pipeline_requirement_audit_xclbin_after_566dd44/audit.json
2d7e1ecf543c76a492265ef8d7b79de5e316596ed1795a64a2ae955fbbd74344  results/pure_pipeline_evidence_bundle_xclbin_after_566dd44/summary.md
73def000b79826a80b4d1598aa46fbcc7a8f676263904a36d86b9fbfd6b2bbdc  results/pure_pipeline_evidence_bundle_xclbin_after_566dd44/target_matrix.tsv
d9d2b6ca5e02bcda30fbcc5a81acac3cc6dd3737a10a3128697e2726f8b94e14  results/pure_pipeline_evidence_bundle_xclbin_after_566dd44/bundle_manifest.json
```

## Finalize auto-collects xclbin contract evidence

As of 2026-07-15 03:27 Asia/Shanghai, finalize now runs the post-link xclbin
metadata contract checker before smoke/compare. This does not create a new
hardware build; it tightens the reproducibility path so a future `hw_emu` or
`hw` xclbin automatically gets a metadata-contract TSV, and the finalize
evidence records hashes for:

```text
<xclbin>
<xclbin>.info
run_logs/xclbin_contract_<target>_<label>.tsv
manifest.env
inputs.tsv
compile_commands.sh
link_command.sh
smoke/compare outputs when they are enabled
```

Source commits:

```text
ce8fe06264b201c4f7bf4b0c3037fc2ba4fe2147  Collect xclbin contract during finalize
11f1e78bc4fb0cc721a664ce8c97a9b7f38e0401  Audit finalize xclbin contract outputs
```

Changed files:

```text
scripts/finalize_pure_pipeline_build.sh
scripts/audit_pure_pipeline_status.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/check_pure_pipeline_xclbin_contract.py

./scripts/finalize_pure_pipeline_build.sh \
  --target sw_emu \
  --label after_11f1e78 \
  --skip-smoke \
  --skip-compare \
  --build-root .tmp_build/pure_pipeline_sw_emu_stage0

./scripts/audit_pure_pipeline_status.py \
  --label after_11f1e78_finalize_contract \
  --out-dir results/pure_pipeline_requirement_audit_after_11f1e78_finalize_contract

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_after_11f1e78_finalize_contract/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_after_11f1e78_finalize_contract
```

Result:

```text
finalize xclbin contract target=sw_emu
check_count=9
failed_count=0
xclbin_sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
info_sha256=8b0cf0c3b63ea7d623a599af4db65c4464aae8fadc93e07c089d374bbc2b0f04
required_kernels=yes
required_instances=yes
kernel_metadata_contract=yes
link_connectivity_contract=yes

audit status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
sw_emu xclbin_contract=.tmp_build/pure_pipeline_sw_emu_stage0/run_logs/xclbin_contract_sw_emu_after_11f1e78.tsv
hw_emu xclbin=MISSING
hw xclbin=MISSING
```

Artifacts:

```text
.tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_after_11f1e78.env
.tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_after_11f1e78_evidence.tsv
.tmp_build/pure_pipeline_sw_emu_stage0/run_logs/xclbin_contract_sw_emu_after_11f1e78.tsv
results/pure_pipeline_requirement_audit_after_11f1e78_finalize_contract/audit.json
results/pure_pipeline_requirement_audit_after_11f1e78_finalize_contract/audit.md
results/pure_pipeline_evidence_bundle_after_11f1e78_finalize_contract/summary.md
results/pure_pipeline_evidence_bundle_after_11f1e78_finalize_contract/target_matrix.tsv
results/pure_pipeline_evidence_bundle_after_11f1e78_finalize_contract/bundle_manifest.json
```

Evidence hashes:

```text
47e35bd392c248b2e189a396999b4a8a67e6775178d1988fa49ab67a8e20e759  scripts/finalize_pure_pipeline_build.sh
55a23acf3443536b4275a2ca0b219ab3ec40374b70c9d34033fa256b645e9337  scripts/audit_pure_pipeline_status.py
adb638689b2381c030f50b5e2ef75db90852a8c957076138fbb8b9a8eae419d4  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_after_11f1e78.env
38730562485fc0e7a7a7f61efb2656d8cf08c6ce22350e3a6c96629ab6a01cca  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/finalize_after_11f1e78_evidence.tsv
e41cce545651d7e38c6ba8c0ed559d212055e61128194f82e6c443e0075929d1  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/xclbin_contract_sw_emu_after_11f1e78.tsv
5b06ee94f9e8a9ac456630e0ff698881826de9de243a506e6a7e720779032b01  results/pure_pipeline_requirement_audit_after_11f1e78_finalize_contract/audit.json
972c8ae257976e70ba8764de4eeda1669c2537485387fe47e4c7d2246091f87a  results/pure_pipeline_requirement_audit_after_11f1e78_finalize_contract/audit.md
c9ac8ffea4283d7936986044d513a742ae5b991cf6893b03309792b3a5a0d22b  results/pure_pipeline_evidence_bundle_after_11f1e78_finalize_contract/summary.md
722f8b0778350e614c3cd24f8ad953eda249cca82739aef21100d61bb3a66749  results/pure_pipeline_evidence_bundle_after_11f1e78_finalize_contract/target_matrix.tsv
9a032d7eacd4ca20b6d5dbffcefa0a0376e09e1298be9754a94ace3cbe99f0a6  results/pure_pipeline_evidence_bundle_after_11f1e78_finalize_contract/bundle_manifest.json
```

Important status note: the current pure-pipeline `hw_emu` and `hw` xclbins
still do not exist. The latest bundle also reports active external Vitis/Vivado
builders, so the next long build should be launched only after those resources
are intentionally cleared or accepted.

## Current hw_emu/hw readiness gate

As of 2026-07-15 03:30 Asia/Shanghai, the generated pure-pipeline `hw_emu`
and `hw` build scripts are present, but strict readiness says not to launch a
new long Vitis build yet. The blocker is external Vitis/Vivado activity from the
Spine hardware link, not a missing integration compile/link script.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_pure_pipeline_build_readiness.sh \
  --target hw_emu \
  --label after_d7ab02c_strict_current

./scripts/check_pure_pipeline_build_readiness.sh \
  --target hw \
  --label after_d7ab02c_strict_current

./scripts/audit_pure_pipeline_status.py \
  --label after_d7ab02c_current_readiness \
  --out-dir results/pure_pipeline_requirement_audit_after_d7ab02c_current_readiness

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_after_d7ab02c_current_readiness/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_after_d7ab02c_current_readiness
```

Result:

```text
hw_emu strict readiness: ready=no blocking_count=1 warning_count=1 rc=3
hw strict readiness:     ready=no blocking_count=1 warning_count=0 rc=3
external builders:       total=10 v++=2 vivado=4 vpl=2 vrs=2
hw_emu stale artifacts:  children=7 clean_recommended=yes
hw stale artifacts:      children=0 clean_recommended=no
build_root free:         216.0G
/tmp free:               2.2G

audit status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
sw_emu xclbin exists: yes
hw_emu xclbin exists: no
hw xclbin exists: no
```

Artifacts:

```text
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_after_d7ab02c_strict_current.txt
.tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_after_d7ab02c_strict_current.txt
results/pure_pipeline_requirement_audit_after_d7ab02c_current_readiness/audit.json
results/pure_pipeline_requirement_audit_after_d7ab02c_current_readiness/audit.md
results/pure_pipeline_evidence_bundle_after_d7ab02c_current_readiness/summary.md
results/pure_pipeline_evidence_bundle_after_d7ab02c_current_readiness/target_matrix.tsv
results/pure_pipeline_evidence_bundle_after_d7ab02c_current_readiness/bundle_manifest.json
```

Evidence hashes:

```text
22b9a30b3850788183c0ffcaa02fb6e9b4dbce7aaff1c9f344a59df1107f8896  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_after_d7ab02c_strict_current.txt
1a0b22f5653681f749b290478d2c12ae7b0c921200c4119138b961bda4b5af06  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_after_d7ab02c_strict_current.txt
3c80c02f1f30a9430d3e2e46a3303cd6b2392aa0e66e0ea730bf5193d4f00eba  results/pure_pipeline_requirement_audit_after_d7ab02c_current_readiness/audit.json
285382af36fa38bf24e34428364b66ac2eaab3dd852bc3976811cd0a24e4edbf  results/pure_pipeline_requirement_audit_after_d7ab02c_current_readiness/audit.md
d021d428d06824c5584dd5c00adccb2049d27d9b32de31f68f4b74a31106060d  results/pure_pipeline_evidence_bundle_after_d7ab02c_current_readiness/summary.md
f39fe9a2699a25f5ea54ac703ac66334dc59073faea5c7ee7929a9b4dd57df31  results/pure_pipeline_evidence_bundle_after_d7ab02c_current_readiness/target_matrix.tsv
38515df9990aa2453e603fe5d886d6a8c506f533e7296d826e04601fb0a3fa0c  results/pure_pipeline_evidence_bundle_after_d7ab02c_current_readiness/bundle_manifest.json
```

Next long command, once the external builders are allowed to clear:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_d7ab02c \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

## Launch packet readiness is audit-visible

As of 2026-07-15 03:35 Asia/Shanghai, the launch-packet helper writes its
strict readiness report to the target `run_logs` first, then copies the same
file into the packet directory. This makes the packet-local readiness and the
global audit/evidence-bundle readiness point at the same current gate result.
Before this fix, a launch packet could contain a fresh readiness file while its
embedded audit still referenced the newest older readiness under target
`run_logs`.

Source commit:

```text
0a1f163f7abf4c9319e901fe200cf01e907ef615  Sync launch packet readiness with audit
```

Changed file:

```text
scripts/create_pure_pipeline_launch_packet.sh
```

Validation command:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/create_pure_pipeline_launch_packet.sh

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --label launch_packet_hwemu_after_0a1f163 \
  --flow-label after_0a1f163
```

Result:

```text
source_contract_status=0
readiness_status=3
audit_status=0
bundle_status=0
source_contracts required_count=11 failed_count=0
hw_emu readiness ready=no blocking_count=1 warning_count=1
external builders=total=10 v++=2 vivado=4 vpl=2 vrs=2
hw_emu xclbin=MISSING
launch_packet_exit=3
```

The packet-generated audit now records:

```text
latest_hw_emu_readiness=.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_launch_packet_hwemu_after_0a1f163.txt
sha256=0965efd8bbf3a6e233d40ea8d2c558f72e23f7934acad758ab5d440259bf5534
```

Launch command captured in the packet:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_0a1f163 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Artifacts:

```text
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/README.md
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/launch_command.sh
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/launch_packet.env
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/artifact_hashes.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/source_contracts.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/readiness_hw_emu.txt
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_launch_packet_hwemu_after_0a1f163.txt
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/audit/audit.json
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/evidence_bundle/summary.md
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/evidence_bundle/target_matrix.tsv
```

Evidence hashes:

```text
6545877d8576d7c56f23dc70b429b27b3e773af80641614c6b8c21954ca3c366  scripts/create_pure_pipeline_launch_packet.sh
be7429de233ff95ddbd1230c8f3e04db7770a6215840edfe0ef1cb3b1d7666aa  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/README.md
ec0ac29d9d3eb2d0248b7125493e9420909429c3f6abef5aef3d7fb88fe93b3e  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/launch_command.sh
2966156772b8f8c14f21a6ac605b1dded394a16df8a92b06a8a56cc3fbeca55f  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/launch_packet.env
1ffb753090e16a6b5a11fa30bcb174e0ed461b01681574acf62e390cbe52bc9a  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/artifact_hashes.tsv
572e419a9a0b213f94f43e4cc57bdc50815a4a2ad577fe2384d802a284f25123  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/source_contracts.tsv
0965efd8bbf3a6e233d40ea8d2c558f72e23f7934acad758ab5d440259bf5534  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/readiness_hw_emu.txt
0965efd8bbf3a6e233d40ea8d2c558f72e23f7934acad758ab5d440259bf5534  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_launch_packet_hwemu_after_0a1f163.txt
c4163e2e8f0e8e71cf1c193fe2818e84df0a2c5c991d40b5349827ad1f0752a6  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/audit/audit.json
7dc2dab0ddeeb8dd7edb7a41de89ebab03de3c2a9d357e76e3b9901d5fe61214  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/evidence_bundle/summary.md
2f75032731d3d3f4ffcae71e79f32d657f5dfcd9976d99e08778ed205665c04b  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_0a1f163/evidence_bundle/target_matrix.tsv
```

## Launch packet prepares generated scripts by default

As of 2026-07-15 03:39 Asia/Shanghai, launch-packet creation regenerates the
target compile/link/config/manifest files before running source-contract and
readiness checks. This keeps the packet evidence aligned with the scripts that
the generated target-flow command will launch. The old behavior can still be
requested with `--no-prepare` when inspecting an existing generated build
directory.

Source commit:

```text
1f233c0a480290c952ab03a9d62934521a523077  Prepare scripts before launch packet checks
```

Changed files:

```text
README.md
scripts/create_pure_pipeline_launch_packet.sh
```

Validation command:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/create_pure_pipeline_launch_packet.sh

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --label launch_packet_hwemu_after_1f233c0 \
  --flow-label after_1f233c0
```

Result:

```text
prepare_pure_hw_pipeline_build.sh ran before checks
source_contract_status=0
readiness_status=3
audit_status=0
bundle_status=0
source_contracts required_count=11 failed_count=0
hw_emu readiness ready=no blocking_count=1 warning_count=1
external builders=total=10 v++=2 vivado=4 vpl=2 vrs=2
hw_emu xclbin=MISSING
launch_packet_exit=3
integration_tracked_dirty=clean
```

The packet-generated audit records:

```text
latest_hw_emu_readiness=.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_launch_packet_hwemu_after_1f233c0.txt
sha256=4be4fb9caae188a5ffdf1f4202b4fd978ef45e689dda7ca92734a778facd6820
```

Launch command captured in the packet:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_1f233c0 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Artifacts:

```text
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/README.md
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/launch_command.sh
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/launch_packet.env
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/artifact_hashes.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/source_contracts.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/readiness_hw_emu.txt
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_launch_packet_hwemu_after_1f233c0.txt
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/audit/audit.json
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/evidence_bundle/summary.md
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/evidence_bundle/target_matrix.tsv
```

Evidence hashes:

```text
a894aa2b099ecd7a43fa4b15c896fe3b078ed060bf3dbb8078237393470ca1fd  scripts/create_pure_pipeline_launch_packet.sh
0273ab60802618705ab6af5dc8fdbd6a43b30c8b34386430f626e608eb47310d  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/README.md
9f43d453f82ad0ebc59a0faebb82fc36528a83a9ef9c09718bf3e0454dcf2386  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/launch_command.sh
24551630033c4c977c83919cfee6b2545b506564c5f402d49ff1b8f758cf145a  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/launch_packet.env
f8639555c66c5236ae298941e75e4f5cff83b8abd2cbbf19cc24b01de077de90  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/artifact_hashes.tsv
572e419a9a0b213f94f43e4cc57bdc50815a4a2ad577fe2384d802a284f25123  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/source_contracts.tsv
4be4fb9caae188a5ffdf1f4202b4fd978ef45e689dda7ca92734a778facd6820  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/readiness_hw_emu.txt
4be4fb9caae188a5ffdf1f4202b4fd978ef45e689dda7ca92734a778facd6820  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_launch_packet_hwemu_after_1f233c0.txt
d93ceb08a06a370f7450cc93b01727b92bfd9ab81ad93d22a7173d4d02381d31  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/audit/audit.json
034d0451f121b83e2c70999702b283e91bf2aff120b77b487aea50caf66d6d5c  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/evidence_bundle/summary.md
6a21e4473c26cab0bcc8becce02eb50fec9e6246fd26da98a064dfa020485008  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_1f233c0/evidence_bundle/target_matrix.tsv
```

## HW launch packet preflight

As of 2026-07-15 03:42 Asia/Shanghai, the same launch-packet path was checked
for the final `hw` target. This still does not start Vitis. It regenerates the
`hw` compile/link/config/manifest scripts, verifies the source contracts, writes
strict readiness to the target `run_logs`, and exports a packet-local audit and
evidence bundle.

Validation command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --label launch_packet_hw_after_3f318c3 \
  --flow-label after_3f318c3
```

Result:

```text
target=hw
integration_head=3f318c37f7dce6e7c8d8e1e4564a63d90b45cd24
integration_tracked_dirty=clean
prepare_pure_hw_pipeline_build.sh ran before checks
source_contract_status=0
readiness_status=3
audit_status=0
bundle_status=0
source_contracts required_count=11 failed_count=0
hw readiness ready=no blocking_count=1 warning_count=0
external builders=total=10 v++=2 vivado=4 vpl=2 vrs=2
hw build_artifacts=PASS children=0 clean_recommended=no
hw xclbin=MISSING
launch_packet_exit=3
```

The packet-generated audit records:

```text
latest_hw_readiness=.tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_launch_packet_hw_after_3f318c3.txt
sha256=7e525b327add07b1cbe65d68a7cabeb9569ad4a3b89a342f6cefb096320b3ad4
```

Launch command captured in the packet:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label after_3f318c3 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Artifacts:

```text
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/README.md
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/launch_command.sh
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/launch_packet.env
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/artifact_hashes.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/source_contracts.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/readiness_hw.txt
.tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_launch_packet_hw_after_3f318c3.txt
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/audit/audit.json
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/evidence_bundle/summary.md
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/evidence_bundle/target_matrix.tsv
```

Evidence hashes:

```text
4398a751bc0de6ca275e61a3082b2b76ffad89f632d3583fe365ac8ab5c273e7  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/README.md
d2bb3b0c36f218d0535569fb71bfcf5dc8000dcace0d7b09a0aba36570aaf673  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/launch_command.sh
a9b53d431f498193b9439a80046df2d3fb07d5fd889beede9955f2ec5b9b2758  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/launch_packet.env
fb28765e2efcd8df9dd32562b9674ac580f4c4acfdedb7bfe8f6d1c06bc93d1f  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/artifact_hashes.tsv
572e419a9a0b213f94f43e4cc57bdc50815a4a2ad577fe2384d802a284f25123  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/source_contracts.tsv
7e525b327add07b1cbe65d68a7cabeb9569ad4a3b89a342f6cefb096320b3ad4  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/readiness_hw.txt
7e525b327add07b1cbe65d68a7cabeb9569ad4a3b89a342f6cefb096320b3ad4  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_launch_packet_hw_after_3f318c3.txt
3c7047d539caff8749053a0ada770229ef0521684971f892de0697fc668bc7c1  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/audit/audit.json
3e8ff410a5635376aed5a3bc086ce04ddfce20b63e75dd2ec254b80b9f3474df  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/evidence_bundle/summary.md
4ff50764cdb9bc9271cf46d5b2f3979c9ab4a18f162d780be7c0991c44b07439  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_3f318c3/evidence_bundle/target_matrix.tsv
```

## Launch packet source fingerprints

As of 2026-07-15 03:50 Asia/Shanghai, launch packets also record deterministic
source tree fingerprints. This closes an important reproducibility gap: the
local ReGraph tree used by the integration workspace is not a git repository,
so `regraph_head=not_git` alone is not enough to identify the source state.

Changed files:

```text
README.md
scripts/create_pure_pipeline_launch_packet.sh
```

The launch packet now writes:

```text
source_fingerprints.tsv
<role>.files
<role>.sha256s
```

The fingerprinted roles are:

```text
integration_scripts
integration_kernels
integration_tools
grasu_kernel_src
grasu_host_src
grasu_u55c_scripts
regraph_acc_template
regraph_acc_udfs
regraph_host_src
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/create_pure_pipeline_launch_packet.sh

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --label launch_packet_hwemu_after_a92b784 \
  --flow-label after_a92b784

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --label launch_packet_hw_after_a92b784 \
  --flow-label after_a92b784
```

Result:

```text
integration_head=a92b784b74bfd13e280d7cddf2be4fa8325bf9cc
integration_tracked_dirty=clean
source_contract_status=0
audit_status=0
bundle_status=0
hw_emu launch_packet_exit=3
hw launch_packet_exit=3
readiness_status=3 for both targets because unrelated Spine Vitis/Vivado builders were active
hw_emu xclbin=MISSING
hw xclbin=MISSING
```

Current source fingerprints:

```text
integration_scripts  cb819f2c3dd7f4ad7463ffdedf508d53a743002a6cab6fb30c779fed42a9eaf7
integration_kernels  d4e044aa815f07ecc308484748496db93247d29a9a872f5ec1c7eaa811b37f88
integration_tools    25acbe258816f976a0f986b7b99625a977fcacc8e2eb065dda0f2f6dcf4b7192
grasu_kernel_src     db745c5d32223c703581e386e301326bd6b15fa3a0317addcf6af81ccec9504c
grasu_host_src       183d604a583a6e6bba2988e18adb3aaa8b90817ce5f5b2f31108cb14d464ee4d
grasu_u55c_scripts   d88beea35b92b18b8fa248c9803d66dc8b12b6e95003bdd8f3ae39e5b019add4
regraph_acc_template 2b858c5b0df83a3dc8bcbad0e3ae2f168303cbaab7098259cc32e29e299d65f2
regraph_acc_udfs     da1d16656e72a3f83754208a70b657931035d22e38a04d1c35791e09c80adc71
regraph_host_src     be0d2556f07e166c5adbe91a2f48bdeab517caec6ea08f93ead1ad8202e07a1b
```

Artifacts:

```text
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_a92b784/source_fingerprints.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_a92b784/source_fingerprints.tsv
.tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_a92b784/readiness_hw_emu.txt
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_a92b784/readiness_hw.txt
.tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_launch_packet_hwemu_after_a92b784.txt
.tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_launch_packet_hw_after_a92b784.txt
```

Evidence hashes:

```text
13f76865878712545e7733ea6e49a17f6173e939a1be49f2486f0121486e9bde  scripts/create_pure_pipeline_launch_packet.sh
1c2f9851b24fc2b60f7d0ff57c99624c62dc321be8232c4883fd4c1871446d81  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_a92b784/source_fingerprints.tsv
1c2f9851b24fc2b60f7d0ff57c99624c62dc321be8232c4883fd4c1871446d81  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_a92b784/source_fingerprints.tsv
ecb1cd91bec4380fcfa1ba455e933a501abfe0a68891b0bf65e279466f9e3f0e  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_a92b784/readiness_hw_emu.txt
ecb1cd91bec4380fcfa1ba455e933a501abfe0a68891b0bf65e279466f9e3f0e  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_launch_packet_hwemu_after_a92b784.txt
982ad36984beae4749e374da8f0de953f6f755879251f341fab708fe538fbbb8  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_a92b784/readiness_hw.txt
982ad36984beae4749e374da8f0de953f6f755879251f341fab708fe538fbbb8  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_launch_packet_hw_after_a92b784.txt
d3de705fb96e8bd79986e33c8f100ed668ab941eee6a02a903f2293f129cce84  .tmp_build/pure_pipeline_launch_packet_launch_packet_hwemu_after_a92b784/audit/audit.json
491a6930f02873d4a835581e8a3c41f07031af1c953d746b138903daf8b48738  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_after_a92b784/audit/audit.json
```

## Audit-visible source fingerprints

As of 2026-07-15 03:53 Asia/Shanghai, the requirement audit also exposes the
latest launch-packet source fingerprint and the original start-state source
fingerprint in its Key Artifacts table. This means the compact audit and
evidence bundle now carry enough source-hash evidence for the non-git ReGraph
tree without requiring the reader to inspect launch packets manually.

Changed files:

```text
scripts/audit_pure_pipeline_status.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile scripts/audit_pure_pipeline_status.py

./scripts/audit_pure_pipeline_status.py \
  --label source_fp_audit_check \
  --out-dir results/pure_pipeline_requirement_audit_source_fp_check

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_source_fp_check/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_source_fp_check
```

Result:

```text
status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
latest_launch_packet_source_fingerprints=yes
start_state_source_fingerprints=yes
latest launch packet source_fingerprints sha256=1c2f9851b24fc2b60f7d0ff57c99624c62dc321be8232c4883fd4c1871446d81
start state source_fingerprints sha256=bd2880f6857bdfb446f81d0313bdc0ad453d1a6b9143a1b6ee536b678de8c0aa
```

Evidence hashes:

```text
f0b552702afee3c982bcd3ad559fc807589ecfdc3afc45701a7100c3fbd935d5  scripts/audit_pure_pipeline_status.py
1e4e5614af59128c251a327ba867956b4c9fe635906295b62d30257ac6bba9e8  results/pure_pipeline_requirement_audit_source_fp_check/audit.json
85738c0e6c4695953c50e16a902bad7deae4643ad4590f8bca93edafe8257888  results/pure_pipeline_requirement_audit_source_fp_check/audit.md
a9bc995acb3d481037a7a86e769a0f86b54dfb3796aa6fbcc220c7eb4f350808  results/pure_pipeline_evidence_bundle_source_fp_check/artifact_matrix.tsv
8afbdc468b3c62fe077e5cd0354d6f28cd6a669bb54f83b1095f2b92aa549831  results/pure_pipeline_evidence_bundle_source_fp_check/summary.md
```

## Target-flow source fingerprints

As of 2026-07-15 03:59 Asia/Shanghai, source fingerprint collection is a shared
script and is called by both launch packets and the target-flow wrapper. This
matters because the real build entry point is `run_pure_pipeline_target_flow.sh`;
the build run now writes its own `source_fingerprints_target_flow_<label>.tsv`
under the target `run_logs/` directory before any Vitis build launch.

Changed files:

```text
README.md
scripts/collect_pure_pipeline_source_fingerprints.sh
scripts/create_pure_pipeline_launch_packet.sh
scripts/run_pure_pipeline_target_flow.sh
scripts/audit_pure_pipeline_status.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/collect_pure_pipeline_source_fingerprints.sh
bash -n scripts/create_pure_pipeline_launch_packet.sh
bash -n scripts/run_pure_pipeline_target_flow.sh
python3 -m py_compile scripts/audit_pure_pipeline_status.py

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label target_flow_source_fp_after_6564f46 \
  --prepare \
  --skip-build \
  --skip-finalize \
  --skip-audit \
  --monitor-tail 5

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --label launch_packet_source_fp_after_6564f46 \
  --flow-label source_fp_after_6564f46 \
  --wait-idle 60 \
  --idle-poll 10 \
  --idle-settle 10 \
  --no-gate

./scripts/audit_pure_pipeline_status.py \
  --label source_fp_after_6564f46 \
  --out-dir results/pure_pipeline_requirement_audit_source_fp_after_6564f46

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_source_fp_after_6564f46/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_source_fp_after_6564f46
```

Result:

```text
integration_head=6564f461cad8a08d8b18d4be30ad58e25ab0c0d7
target_flow_rc=0
launch_packet_rc=3
audit_rc=0
bundle_rc=0
target-flow fingerprint sha256=c80a18aae28b9924ff74b39866f0bb2d18731852d9d4fc7d8eb8547d69e6f47c
launch-packet fingerprint sha256=c80a18aae28b9924ff74b39866f0bb2d18731852d9d4fc7d8eb8547d69e6f47c
readiness remains blocked for strict launch packets because unrelated Spine Vitis/Vivado builders are active
hw_emu xclbin=MISSING
```

The audit and evidence bundle now expose all three source-fingerprint artifacts:

```text
latest_launch_packet_source_fingerprints
latest_target_flow_source_fingerprints
start_state_source_fingerprints
```

Current source fingerprints:

```text
integration_scripts  4d6830cc87a8d1a82ae79e1d93333ec756875fe4df7fa37c75fc51501aae086e
integration_kernels  d4e044aa815f07ecc308484748496db93247d29a9a872f5ec1c7eaa811b37f88
integration_tools    25acbe258816f976a0f986b7b99625a977fcacc8e2eb065dda0f2f6dcf4b7192
grasu_kernel_src     db745c5d32223c703581e386e301326bd6b15fa3a0317addcf6af81ccec9504c
grasu_host_src       183d604a583a6e6bba2988e18adb3aaa8b90817ce5f5b2f31108cb14d464ee4d
grasu_u55c_scripts   d88beea35b92b18b8fa248c9803d66dc8b12b6e95003bdd8f3ae39e5b019add4
regraph_acc_template 2b858c5b0df83a3dc8bcbad0e3ae2f168303cbaab7098259cc32e29e299d65f2
regraph_acc_udfs     da1d16656e72a3f83754208a70b657931035d22e38a04d1c35791e09c80adc71
regraph_host_src     be0d2556f07e166c5adbe91a2f48bdeab517caec6ea08f93ead1ad8202e07a1b
```

Evidence hashes:

```text
66abd6a07660664a26a2dbdd2e63a39cfcc1c2f93d77a977e7ca9d551198facd  scripts/collect_pure_pipeline_source_fingerprints.sh
a6c453598a0534eee8f573fda6213b4248f9b3284891510d4b5d958691b526ef  scripts/create_pure_pipeline_launch_packet.sh
e7a028265fd429b9c2b4b63013349bc6ebdac691beacbb9bac1fa9b04b7bd092  scripts/run_pure_pipeline_target_flow.sh
7b5b00b9fb95c388ce925a434d847fe2a35f6dbd3e0e938582107c41ad4f7d20  scripts/audit_pure_pipeline_status.py
c80a18aae28b9924ff74b39866f0bb2d18731852d9d4fc7d8eb8547d69e6f47c  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_fingerprints_target_flow_target_flow_source_fp_after_6564f46.tsv
c80a18aae28b9924ff74b39866f0bb2d18731852d9d4fc7d8eb8547d69e6f47c  .tmp_build/pure_pipeline_launch_packet_launch_packet_source_fp_after_6564f46/source_fingerprints.tsv
4ce437f2d3e541f56790bada6e14e6e1f69764e80b1a7f08282293d98646def4  results/pure_pipeline_requirement_audit_source_fp_after_6564f46/audit.md
f0a0242868eaafb6459df462e771fce03ccf6459526917c6d7fde8b92ca42b5a  results/pure_pipeline_requirement_audit_source_fp_after_6564f46/audit.json
84a198e8238e2ef888797d1700cdeea8068d012c446d1bdc963cb5e0864ace94  results/pure_pipeline_evidence_bundle_source_fp_after_6564f46/artifact_matrix.tsv
20d7bf71ef57482cd8043c6ae04938428b75a689455d3fb2a59fc4a3a8b9d9f8  results/pure_pipeline_evidence_bundle_source_fp_after_6564f46/summary.md
```

## Source proof for no host graph handoff

As of 2026-07-15 04:02 Asia/Shanghai, the source-contract gate explicitly
checks the requirement that the pure pipeline does not perform graph D2H, host
conversion, or graph H2D between GraSU and ReGraph. The CPU oracle still builds
`final_edges` on the host for correctness checking, but the checked runtime
segment from GraSU launch to adapter enqueue contains no host-side graph
migration, readback, conversion, or buffer rebuild. The adapter consumes the
GraSU PMA buffers and streams directly into ReGraph.

Changed files:

```text
scripts/audit_pure_pipeline_status.py
scripts/check_pure_pipeline_source_contracts.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/check_pure_pipeline_source_contracts.py

./scripts/check_pure_pipeline_source_contracts.py \
  --label no_host_handoff_check \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_no_host_handoff_check.tsv

./scripts/audit_pure_pipeline_status.py \
  --label no_host_handoff_check \
  --out-dir results/pure_pipeline_requirement_audit_no_host_handoff_check

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_no_host_handoff_check/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_no_host_handoff_check
```

Result:

```text
required_count=12
failed_count=0
proof=no_host_graph_handoff_between_grasu_and_regraph ok=yes
status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
requirement_5_status=partial
```

The new proof remains partial at the requirement level because `hw_emu` and
`hw` xclbins/smoke results are still missing, but the source-level preflight now
guards against accidentally reintroducing a GraSU -> host -> ReGraph graph
handoff in the pure pipeline.

Evidence hashes:

```text
1c1938ec343779a804c48030bc9fefece10429bb260990a25d854c2baf66c6b7  scripts/audit_pure_pipeline_status.py
744485f730fbe1a7e5210dd635fac00264d166fc0c53a31518cffaa0ee7161f6  scripts/check_pure_pipeline_source_contracts.py
a0f3a6b28152ebf40a2818ddd87607742f866c4b397b30315c4ea5eaf6349d4e  .tmp_build/pure_pipeline_source_contracts/source_contracts_no_host_handoff_check.tsv
c7fef7d742e4594d0d08e45c398e7755ef699411cacfee003fef7e14f7ea890c  results/pure_pipeline_requirement_audit_no_host_handoff_check/audit.md
4451484aa74f4d4db241d2dc35a4af7dfb69e8ed12c975f8e39ad4df80d25a7c  results/pure_pipeline_requirement_audit_no_host_handoff_check/audit.json
71f3ad5ab6fc832a0cde2dca5cee07caba789dedff5feab8e074e102f1e6b5d0  results/pure_pipeline_evidence_bundle_no_host_handoff_check/source_proof_matrix.tsv
e7981da5154cc8970bdcbf005e1afd0d7e01d74651581a7760a1a9187db314e1  results/pure_pipeline_evidence_bundle_no_host_handoff_check/requirement_matrix.tsv
cf28102ad34bb361209fc1d2dccc17a134ed2054de983eac99490d071cbac121  results/pure_pipeline_evidence_bundle_no_host_handoff_check/summary.md
```

## Source proof for GraSU writer completion tokens

As of 2026-07-15 04:04 Asia/Shanghai, the source-contract gate also verifies
that the GraSU PMA writer kernels themselves emit completion tokens. This makes
requirement 2 stronger than a connectivity-only check: the audit now checks the
token type/helper, the `process_cache` and `process_ddr` token ports, the token
write calls, the compile-time `-DGRASU_ENABLE_COMPLETION_TOKEN`, and the four
stream connections into the barrier.

Changed files:

```text
scripts/audit_pure_pipeline_status.py
scripts/check_pure_pipeline_source_contracts.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/check_pure_pipeline_source_contracts.py

./scripts/check_pure_pipeline_source_contracts.py \
  --label writer_token_check \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_writer_token_check.tsv

./scripts/audit_pure_pipeline_status.py \
  --label writer_token_check \
  --out-dir results/pure_pipeline_requirement_audit_writer_token_check

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_writer_token_check/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_writer_token_check
```

Result:

```text
required_count=13
failed_count=0
proof=grasu_writers_emit_completion_tokens ok=yes
status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
requirement_2_status=partial
```

The requirement remains partial until `hw_emu` and `hw` xclbins/smoke results
exist, but the source-level gate now verifies both sides of the barrier
contract: writers emit done packets and the barrier consumes all four before the
adapter runs.

Evidence hashes:

```text
2df30887a3819ad30f062ae3a7d8995331f8751ac2b5e94bb8cf9a24f284afa5  scripts/audit_pure_pipeline_status.py
2e1d63774d10f6f6fc583296c4da05c9dba6159a58564a6a6498d769aef13d78  scripts/check_pure_pipeline_source_contracts.py
091e206e6471fdf8a59a93b6a69ad4f3dff5033d08019bcfb63976aaeb928955  .tmp_build/pure_pipeline_source_contracts/source_contracts_writer_token_check.tsv
8ad69742f4c2b96a49b0a67c0b5d914df417718561d458fd188f602f2581e7c0  results/pure_pipeline_requirement_audit_writer_token_check/audit.md
350132d3347d2c9a2604721358c5d0bc9c7e6fc240887fae129e1fc4a8a95523  results/pure_pipeline_requirement_audit_writer_token_check/audit.json
dff462d464cdf33efa6089ee0cd6c810bb6a4f3f579232605833159b1ab6b633  results/pure_pipeline_evidence_bundle_writer_token_check/source_proof_matrix.tsv
911c92fa363f8b4eed2b1dcb1d7c4dfe01e4420ac67596616170b968d2c33645  results/pure_pipeline_evidence_bundle_writer_token_check/requirement_matrix.tsv
b5b1d26d5a4c38875ae34f1a678ee6a787a94d7ebb6caa701f84535d4328dc87  results/pure_pipeline_evidence_bundle_writer_token_check/summary.md
```

Clean commit recheck after commit `bf1d566`:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/check_pure_pipeline_source_contracts.py \
  --label writer_token_after_bf1d566 \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_writer_token_after_bf1d566.tsv
./scripts/audit_pure_pipeline_status.py \
  --label writer_token_after_bf1d566 \
  --out-dir results/pure_pipeline_requirement_audit_writer_token_after_bf1d566
./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_writer_token_after_bf1d566/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_writer_token_after_bf1d566
```

Clean result:

```text
Dirty: False
required_count=13
failed_count=0
proof=grasu_writers_emit_completion_tokens ok=yes
contract_rc=0
audit_rc=0
bundle_rc=0
```

Clean evidence hashes:

```text
091e206e6471fdf8a59a93b6a69ad4f3dff5033d08019bcfb63976aaeb928955  .tmp_build/pure_pipeline_source_contracts/source_contracts_writer_token_after_bf1d566.tsv
2dda78ac20b13ef1f58351e5b12d5695761805d5e037b697a29bedaff4f06622  results/pure_pipeline_requirement_audit_writer_token_after_bf1d566/audit.md
90b3d11329c1064a97ef51279ad08d99a29fa9d905fe3c66a62fe9b1709afa71  results/pure_pipeline_requirement_audit_writer_token_after_bf1d566/audit.json
dff462d464cdf33efa6089ee0cd6c810bb6a4f3f579232605833159b1ab6b633  results/pure_pipeline_evidence_bundle_writer_token_after_bf1d566/source_proof_matrix.tsv
d8182a33e71ed861a977c546f0c1317dd7ddaad42febda36e7c57291c896067c  results/pure_pipeline_evidence_bundle_writer_token_after_bf1d566/requirement_matrix.tsv
815f3697de1ffe331b05448cdb805e9f59c1d95bd5fe905b437f53a968b5c2c8  results/pure_pipeline_evidence_bundle_writer_token_after_bf1d566/summary.md
```

## Case-target coverage audit

As of 2026-07-15 04:14 Asia/Shanghai, the audit also exports an explicit
case-by-target coverage matrix for requirement 7. This expands the previous
target-level smoke status into the full `sw_emu/hw_emu/hw` x
`chain/hot-source/spread/hot-destination` matrix. Each row records whether the
case is present, whether it passed, whether CPU-oracle mismatches are zero, and
whether all required timing fields are present.

The same change also makes requirement 9's machine check stricter: the
zero-cost handoff comparison file is now part of the `baseline_ok` predicate,
not only a displayed artifact.

Changed files:

```text
scripts/audit_pure_pipeline_status.py
scripts/export_pure_pipeline_evidence_bundle.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py

./scripts/check_pure_pipeline_source_contracts.py \
  --label case_target_coverage_precommit \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_case_target_coverage_precommit.tsv

./scripts/check_smoke_input_identity.py \
  --label case_target_coverage_precommit

./scripts/audit_pure_pipeline_status.py \
  --label case_target_coverage_precommit \
  --out-dir results/pure_pipeline_requirement_audit_case_target_coverage_precommit

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_case_target_coverage_precommit/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_case_target_coverage_precommit
```

Result:

```text
required_count=13
failed_count=0
case_count=4
identity_failed_count=0
case_target_rows=12
requirement_7_status=blocked_by_missing_artifact
requirement_9_status=proven
zero_vs_spine_ok=True
status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

Current case-target matrix:

```text
sw_emu  tiny_chain_v16       chain            PASS  mismatches=0 timing=yes ok=yes
sw_emu  tiny_star_v16_u12    hot-source       PASS  mismatches=0 timing=yes ok=yes
sw_emu  tiny_spread_v16_u8   spread           PASS  mismatches=0 timing=yes ok=yes
sw_emu  tiny_hotdst_v64_u32  hot-destination  PASS  mismatches=0 timing=yes ok=yes
hw_emu  tiny_chain_v16       chain            MISSING
hw_emu  tiny_star_v16_u12    hot-source       MISSING
hw_emu  tiny_spread_v16_u8   spread           MISSING
hw_emu  tiny_hotdst_v64_u32  hot-destination  MISSING
hw      tiny_chain_v16       chain            MISSING
hw      tiny_star_v16_u12    hot-source       MISSING
hw      tiny_spread_v16_u8   spread           MISSING
hw      tiny_hotdst_v64_u32  hot-destination  MISSING
```

Evidence hashes:

```text
06935f07e61febe30e0d579ebc6285b6e2c5652fe11af80c9ddcfe79697b0a95  scripts/audit_pure_pipeline_status.py
76cc126b0f5765b30445102eec6cfa7d45a7e720180c675ab339c5ba59a9d148  scripts/export_pure_pipeline_evidence_bundle.py
091e206e6471fdf8a59a93b6a69ad4f3dff5033d08019bcfb63976aaeb928955  .tmp_build/pure_pipeline_source_contracts/source_contracts_case_target_coverage_precommit.tsv
a4bb92d0bc393fb051570aff3f3ebd2f54be825cad24592bcc4d1916b7448242  results/smoke_input_identity_case_target_coverage_precommit/identity.tsv
a4278ed2a7d603bfb3226d8d2374be3431360f249def597a6a07e0566e496c7d  results/pure_pipeline_requirement_audit_case_target_coverage_precommit/audit.md
2ebb3d5b4d0d391a5bfae533ecc2753d19b612345e58fbe19c55645c53ac6b26  results/pure_pipeline_requirement_audit_case_target_coverage_precommit/audit.json
e297c02d8ad59dcddbde9e4c97a4b76bad54a6a0704eeed57f98e3f8881457da  results/pure_pipeline_evidence_bundle_case_target_coverage_precommit/case_target_matrix.tsv
ca917f5f9335c874e0f52e082065307b3e18cbd2e36628448d86942637492611  results/pure_pipeline_evidence_bundle_case_target_coverage_precommit/requirement_matrix.tsv
5c6b92c695e45c8ad63965b5d6bb1572003b72ed78792ebd0d05532baf050795  results/pure_pipeline_evidence_bundle_case_target_coverage_precommit/summary.md
```

No Vitis build was launched in this step. The next hardware action remains the
`hw_emu` target flow after the external Spine link releases build resources.

## Launch packet matrix hashes

As of 2026-07-15 04:19 Asia/Shanghai, the launch-packet script records the
new evidence-bundle matrices directly in `artifact_hashes.tsv` and the packet
README. This makes a packet self-contained for handoff: the person launching
`hw_emu` or `hw` can inspect the requirement matrix, target matrix,
case-target matrix, input-identity matrix, source-proof matrix, and artifact
matrix without first opening the bundle manifest.

Changed file:

```text
scripts/create_pure_pipeline_launch_packet.sh
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/create_pure_pipeline_launch_packet.sh

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --label launch_packet_matrix_precommit \
  --flow-label matrix_precommit \
  --no-prepare \
  --allow-active-builders

rg -n \
  "case_target_matrix|requirement_matrix|input_identity_matrix|source_proof_matrix|artifact_matrix" \
  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_precommit/artifact_hashes.tsv \
  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_precommit/README.md
```

Result:

```text
source_contract_status=0
readiness_status=0
audit_status=0
bundle_status=0
integration_tracked_dirty=dirty
case_target_matrix_listed_in_readme=yes
case_target_matrix_listed_in_artifact_hashes=yes
```

This validation used `--allow-active-builders`, so the packet records the
external Spine `hw` link as a readiness warning and does not launch Vitis. The
actual generated command remains:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label matrix_precommit \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Evidence hashes:

```text
75416c6320464c43d5796594c2489d5bc5f40ad30ee6f4b6f761f00d9c1f84a6  scripts/create_pure_pipeline_launch_packet.sh
6418816e89f3acc65d5f6ae41955d48e029179d7e2a5e9105eb4f34b01c0d068  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_precommit/README.md
0f98db1ab88480c8470a20f0b7e8766de18fd41531ecc5ec0d757e36c1eeb607  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_precommit/artifact_hashes.tsv
e297c02d8ad59dcddbde9e4c97a4b76bad54a6a0704eeed57f98e3f8881457da  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_precommit/evidence_bundle/case_target_matrix.tsv
e0cc6bd2a40fc5179776b93066db862e7c56365fb75393c73a5303b2861897b3  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_precommit/evidence_bundle/bundle_manifest.json
```

Clean commit recheck after commit `ed30b1a`:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --label launch_packet_matrix_after_ed30b1a \
  --flow-label matrix_after_ed30b1a \
  --no-prepare \
  --allow-active-builders
```

Clean result:

```text
integration_head=ed30b1a6c82bc314988271f87778b4e0d5bd91a3
integration_tracked_dirty=clean
source_contract_status=0
readiness_status=0
audit_status=0
bundle_status=0
case_target_matrix_listed_in_readme=yes
case_target_matrix_listed_in_artifact_hashes=yes
```

Clean evidence hashes:

```text
3cb952e75633446cef704797817057f357051064585cd6a368c420e7d5abb7d1  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_after_ed30b1a/README.md
0342059751e40164b2101b47c8868cc41bf614c0aac0095ceeb5bf7e45bf50d5  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_after_ed30b1a/artifact_hashes.tsv
e297c02d8ad59dcddbde9e4c97a4b76bad54a6a0704eeed57f98e3f8881457da  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_after_ed30b1a/evidence_bundle/case_target_matrix.tsv
672c17977b3d7af235a35ab95cdee2159b57a2cca08a9806fc70d509844cde19  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_after_ed30b1a/evidence_bundle/bundle_manifest.json
091e206e6471fdf8a59a93b6a69ad4f3dff5033d08019bcfb63976aaeb928955  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_after_ed30b1a/source_contracts.tsv
249664fcdef3ee113b12a5788501df077b466fc89f83947253fa833631d80d08  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_after_ed30b1a/source_fingerprints.tsv
fa574c10a56cdd5481531df2465fd66a72a5eba7967c694fee038bfbf2c293cf  .tmp_build/pure_pipeline_launch_packet_launch_packet_matrix_after_ed30b1a/readiness_hw_emu.txt
```

## Target flow bundle export

As of 2026-07-15 04:25 Asia/Shanghai, the target-flow wrapper exports the
compact evidence bundle automatically after the requirement audit. This matters
for the eventual `hw_emu` and `hw` runs: the same command that builds, finalizes,
and audits will now leave the report matrices under
`results/pure_pipeline_evidence_bundle_<label>/`. The wrapper also records the
bundle path in `target_flow_<label>.env` and prints `DONE bundle_out=...`.

`--skip-bundle` remains available for debugging, and `--skip-audit` now
explicitly suppresses bundle export because the bundle needs an audit JSON.

Changed files:

```text
scripts/run_pure_pipeline_target_flow.sh
README.md
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/run_pure_pipeline_target_flow.sh

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label target_flow_skip_audit_final_dryrun \
  --skip-build \
  --skip-finalize \
  --no-readiness \
  --skip-audit \
  --dry-run

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label target_flow_bundle_final_check \
  --skip-build \
  --skip-finalize \
  --no-readiness
```

Result:

```text
skip_audit_dryrun_bundle_out=SKIPPED
target_flow_bundle_final_check_source_contracts=PASS required_count=13 failed_count=0
target_flow_bundle_final_check_audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
target_flow_bundle_final_check_bundle_out=results/pure_pipeline_evidence_bundle_target_flow_bundle_final_check
target_flow_bundle_final_check_case_target_matrix_sha256=e297c02d8ad59dcddbde9e4c97a4b76bad54a6a0704eeed57f98e3f8881457da
```

This validation did not launch Vitis: it used `--skip-build --skip-finalize`
and only refreshed source fingerprints, source contracts, monitor output,
audit, and bundle export.

Evidence hashes:

```text
2405e9a780b3416b92d6f660741e989011a5d641b5fce996db462325e5faea8c  scripts/run_pure_pipeline_target_flow.sh
97925ae28f9a70ac0e22ca3ab1bebfa5ee8bc4b8e072a4b14d97ba60178d230f  README.md
bfe0627cc2a8fc8508a5508e819813008ec5f325524850c987a2148d2c779f73  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_target_flow_bundle_final_check.env
091e206e6471fdf8a59a93b6a69ad4f3dff5033d08019bcfb63976aaeb928955  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_contracts_target_flow_target_flow_bundle_final_check.tsv
224acd721d036a5a7b84a081af050f86f17145d412043b0e04f8093a5489e4ce  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_fingerprints_target_flow_target_flow_bundle_final_check.tsv
a98f43814e5fe1c99a0b9016fb5bf1c55cf0e1b85d4a4ae1d95af70ee2454784  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_target_flow_bundle_final_check.txt
c5981b4b492278c6805872d3233823c55858cf525be392bea3150ba170c85773  results/pure_pipeline_requirement_audit_target_flow_bundle_final_check/audit.json
28cbc0cf3a2a7468b97a043ba283a68e65b76f24c06b83e68b97caa93b7bc30a  results/pure_pipeline_requirement_audit_target_flow_bundle_final_check/audit.md
90bbf5f53f0135b2c8f5d0c68f6ae733a05c922f0fdec994abc2dd81a6efa068  results/pure_pipeline_evidence_bundle_target_flow_bundle_final_check/summary.md
e297c02d8ad59dcddbde9e4c97a4b76bad54a6a0704eeed57f98e3f8881457da  results/pure_pipeline_evidence_bundle_target_flow_bundle_final_check/case_target_matrix.tsv
04b72490368e173a7615f17104d5ebd5fb143690b3138ecea6f702ea9ffc0316  results/pure_pipeline_evidence_bundle_target_flow_bundle_final_check/bundle_manifest.json
```

## Source proof for target-flow bundle export

As of 2026-07-15 04:30 Asia/Shanghai, the source-contract gate also verifies
that the target-flow wrapper records `bundle_out` and exports the compact
evidence bundle after audit. This makes requirement 10's result-path
reproducibility stronger: a long `hw_emu` or `hw` target-flow run is now gated
on leaving both the audit and evidence-bundle paths in a predictable place.

Changed files:

```text
scripts/audit_pure_pipeline_status.py
scripts/check_pure_pipeline_source_contracts.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/check_pure_pipeline_source_contracts.py \
  scripts/export_pure_pipeline_evidence_bundle.py

./scripts/check_pure_pipeline_source_contracts.py \
  --label target_flow_bundle_proof_check \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_target_flow_bundle_proof_check.tsv

./scripts/audit_pure_pipeline_status.py \
  --label target_flow_bundle_proof_check \
  --out-dir results/pure_pipeline_requirement_audit_target_flow_bundle_proof_check

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_target_flow_bundle_proof_check/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_target_flow_bundle_proof_check
```

Result:

```text
required_count=14
failed_count=0
proof=target_flow_exports_evidence_bundle ok=yes
requirement_10_status=partial
status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

Requirement 10 remains partial only because `hw_emu` and `hw` xclbin hashes,
full build logs, and final smoke results are still missing.

Evidence hashes:

```text
8eab5ea86fdb57aab5554135a43ee8b736689042d3ac9fc19ccbffd276caf98e  scripts/audit_pure_pipeline_status.py
f54c7b529dbe4c9f2d95860b8d1fd12fb5ec4497d16bd51a0fec4ee0e13851dd  scripts/check_pure_pipeline_source_contracts.py
e56ee7c8735a81058d4854034e5c0e4967f2c8632cece952e893b47df2d0f967  .tmp_build/pure_pipeline_source_contracts/source_contracts_target_flow_bundle_proof_check.tsv
56a393865dd5c8663c2616d72be226e3c444f7553599e3b5ba3a4a92e07993dc  results/pure_pipeline_requirement_audit_target_flow_bundle_proof_check/audit.json
0c37af14a51134b4fcf80320c5b46d47e96b549bcb1c18c0c1499864c73363d6  results/pure_pipeline_requirement_audit_target_flow_bundle_proof_check/audit.md
2f4e301e501a475a61805914d86fc3b36e7a43a3bfe6eb573998af4252834ae5  results/pure_pipeline_evidence_bundle_target_flow_bundle_proof_check/source_proof_matrix.tsv
f4a951160a9759ea968089704fff35dc4b84b52ea4456bab2f78b7774000dba7  results/pure_pipeline_evidence_bundle_target_flow_bundle_proof_check/requirement_matrix.tsv
9560d0e929d8e692b97e482599d6bd01183bb697dab5f19b45494753d0bee6da  results/pure_pipeline_evidence_bundle_target_flow_bundle_proof_check/summary.md
```

## Launch Packet Acceptance Gates

As of 2026-07-15 04:38 Asia/Shanghai, the pure-pipeline launch packet also
emits a machine-readable acceptance checklist:

```text
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_gates_recheck/acceptance_gates.tsv
```

This file does not start Vitis. It records what a later `hw_emu` or `hw`
target-flow run must leave behind before we treat that target as accepted:
source fingerprints, source contracts, readiness, compile/link logs, target
xclbin, xclbin metadata contract, gate smoke, full four-case smoke,
same-input comparison, requirement audit, and compact evidence bundle.

Changed files:

```text
scripts/create_pure_pipeline_launch_packet.sh
scripts/audit_pure_pipeline_status.py
scripts/check_pure_pipeline_source_contracts.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/create_pure_pipeline_launch_packet.sh

python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/check_pure_pipeline_source_contracts.py

./scripts/check_pure_pipeline_source_contracts.py \
  --label acceptance_gates_recheck \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_acceptance_gates_recheck.tsv

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label acceptance_gates_recheck \
  --label launch_packet_hw_emu_acceptance_gates_recheck \
  --allow-active-builders
```

Result:

```text
source_contracts_required_count=15
source_contracts_failed_count=0
proof=launch_packet_records_acceptance_gates ok=yes
launch_packet_acceptance_gates=.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_gates_recheck/acceptance_gates.tsv
launch_packet_readiness=ready=yes allow_active_builders=1 warning_count=2
launch_packet_audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

The readiness packet intentionally used `--allow-active-builders` so it could be
generated while the unrelated Spine `hw` link was still running. The actual
target-flow launch should still use the idle-waiting command generated in the
packet.

Evidence hashes:

```text
ee15511b2eec4a45c80a8eee892a41fed54e29b820b3ee8bfa50387e561a6275  scripts/create_pure_pipeline_launch_packet.sh
e31f3609ccd81bac7c1ca70a896931e264319cc6dff8751cfcf45106033ab79c  scripts/audit_pure_pipeline_status.py
d42746b9045bbd02136b4a40501a1f1ace776142d0eb0c77e84786e6154e3db0  scripts/check_pure_pipeline_source_contracts.py
a7faa029abd07f7db783fd23f18e3caf127eaa2c4145f85c99102b6a2366990d  .tmp_build/pure_pipeline_source_contracts/source_contracts_acceptance_gates_recheck.tsv
3fa1d9d723865d25bf386967fbd83e2bd712f4753032bc248b328b7adba233e9  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_gates_recheck/acceptance_gates.tsv
e5e8df3b6bfe1dc19012649c7e6cd66461e43727755475c0003ca9049be209d0  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_gates_recheck/artifact_hashes.tsv
576387b85636bd40ebd52089f8a7e38caff40b4175095ee4da2cf86cff525d19  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_gates_recheck/README.md
01176dc5e173255a41638b30bdb434443398e397ce889bef3cef05fd54c8480d  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_gates_recheck/evidence_bundle/source_proof_matrix.tsv
```

## Automated Acceptance-Gate Checker

As of commit `3d6c442b82c461708771fb6e2c994c9ceef2cf86`, the launch packet
acceptance checklist has an executable verifier:

```text
scripts/check_pure_pipeline_acceptance_gates.py
```

The checker has two modes:

```text
prelaunch: checks source fingerprints, source contracts, readiness, and launch command
postrun:   checks all required gates, including logs, xclbin, smoke, comparison, audit, and bundle
```

Changed files:

```text
scripts/check_pure_pipeline_acceptance_gates.py
scripts/create_pure_pipeline_launch_packet.sh
scripts/audit_pure_pipeline_status.py
scripts/check_pure_pipeline_source_contracts.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n \
  scripts/create_pure_pipeline_launch_packet.sh \
  scripts/run_pure_pipeline_target_flow.sh \
  scripts/check_pure_pipeline_build_readiness.sh

python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/check_pure_pipeline_source_contracts.py \
  scripts/check_pure_pipeline_acceptance_gates.py

./scripts/check_pure_pipeline_source_contracts.py \
  --label acceptance_checker_after_3d6c442 \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_acceptance_checker_after_3d6c442.tsv

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label acceptance_checker_after_3d6c442 \
  --label launch_packet_hw_emu_acceptance_checker_after_3d6c442 \
  --allow-active-builders
```

Result:

```text
source_contracts_required_count=16
source_contracts_failed_count=0
proof=acceptance_gate_checker_covers_required_outputs ok=yes
launch_packet_integration_head=3d6c442b82c461708771fb6e2c994c9ceef2cf86
launch_packet_integration_tracked_dirty=clean
prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
launch_packet_audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

The generated packet is:

```text
.tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_checker_after_3d6c442
```

The packet was generated with `--allow-active-builders` only to record evidence
while the unrelated Spine `hw` link was still active. A real target-flow launch
should still wait for idle builders.

The postrun checker is expected to fail until the target flow has produced the
`hw_emu` compile/link logs, xclbin, xclbin contract, smoke summaries,
comparison, audit, and evidence bundle:

```bash
python3 scripts/check_pure_pipeline_acceptance_gates.py \
  --acceptance-gates .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_checker_after_3d6c442/acceptance_gates.tsv \
  --mode postrun \
  --out-file .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_checker_after_3d6c442/acceptance_check_postrun.tsv
```

Expected current postrun blockers:

```text
compile_log
link_log
target_xclbin
xclbin_contract
gate_smoke
full_smoke
same_input_compare
requirement_audit
evidence_bundle
```

Evidence hashes:

```text
17d58c5f6a367f22d6910fc04ec9f255b262f021fd53241e537613650d83265a  scripts/check_pure_pipeline_acceptance_gates.py
e58850b2e4e051d07ab5391a89fbdc0015cdc658694451b76d5fb4e01e16b222  scripts/create_pure_pipeline_launch_packet.sh
559203e93ce7bb89e191bdccdc00c2117a84aaf79e142fece60a4ce8065c5cd7  scripts/audit_pure_pipeline_status.py
6570794981c181ca4cf3a1e93923b4411f0317289e16b2fb46786f3bb19f7fd3  scripts/check_pure_pipeline_source_contracts.py
b582dbb00593d03b226628aba9603caf11145eb5d9074daf869290215850b87a  .tmp_build/pure_pipeline_source_contracts/source_contracts_acceptance_checker_after_3d6c442.tsv
13129e28a61c12e43a3b85df42d3d55b438f83e583a7cf5b2ada24184bad6a21  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_checker_after_3d6c442/acceptance_gates.tsv
cc6f608fe7b5b039494c4cc0216d9cd3fd303d154ca74cd5dfc03da38426a181  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_checker_after_3d6c442/acceptance_check_prelaunch.tsv
7a6f31965651955080837737b054d72109c7980090a3a569b5b290d85cb7bdc5  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_checker_after_3d6c442/artifact_hashes.tsv
d0e4088d1e915fb328c6e32db343550d8b71e4b9829b9ac3837b77ff39a0398a  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_checker_after_3d6c442/README.md
f78423d85869b9ebd9cddec7883019840ef58024d280b30eb8c31b6a2f08568f  .tmp_build/pure_pipeline_launch_packet_launch_packet_hw_emu_acceptance_checker_after_3d6c442/evidence_bundle/source_proof_matrix.tsv
```

## Target-Flow Acceptance Gates

As of commit `07c9f3afa5e0155f07c798fba80030e454177b76`, the target-flow
wrapper itself writes replayable acceptance gates and runs automated
acceptance checks:

```text
scripts/run_pure_pipeline_target_flow.sh
```

This means a full `hw_emu` or `hw` invocation now records:

```text
target_flow_<label>.env
target_flow_<label>_replay.sh
acceptance_gates_target_flow_<label>.tsv
acceptance_check_prelaunch_target_flow_<label>.tsv
acceptance_check_postrun_target_flow_<label>.tsv
```

The target flow always runs the prelaunch check unless `--skip-acceptance` is
set. It runs the postrun check only after a complete build + finalize + audit +
bundle flow; `--skip-build`, `--skip-finalize`, `--skip-audit`, or
`--skip-bundle` intentionally suppresses postrun acceptance.

Changed files:

```text
scripts/run_pure_pipeline_target_flow.sh
scripts/audit_pure_pipeline_status.py
scripts/check_pure_pipeline_source_contracts.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n \
  scripts/run_pure_pipeline_target_flow.sh \
  scripts/create_pure_pipeline_launch_packet.sh

python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/check_pure_pipeline_source_contracts.py \
  scripts/check_pure_pipeline_acceptance_gates.py

./scripts/check_pure_pipeline_source_contracts.py \
  --label target_flow_acceptance_after_07c9f3a \
  --out-file .tmp_build/pure_pipeline_source_contracts/source_contracts_target_flow_acceptance_after_07c9f3a.tsv

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label target_flow_acceptance_after_07c9f3a \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900
```

Result:

```text
source_contracts_required_count=17
source_contracts_failed_count=0
proof=target_flow_runs_acceptance_gates ok=yes
target_flow_git_head=07c9f3afa5e0155f07c798fba80030e454177b76
prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

Current postrun check is expected to fail because this validation intentionally
used `--skip-build --skip-finalize` and the `hw_emu` xclbin is not present:

```bash
./scripts/check_pure_pipeline_acceptance_gates.py \
  --acceptance-gates .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_gates_target_flow_target_flow_acceptance_after_07c9f3a.tsv \
  --mode postrun \
  --out-file .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_postrun_target_flow_target_flow_acceptance_after_07c9f3a_expected_missing.tsv
```

Expected current postrun result:

```text
status_counts={"FAIL": 7, "PASS": 6}
failed_gates=compile_log,link_log,target_xclbin,xclbin_contract,gate_smoke,full_smoke,same_input_compare
```

The audit and evidence bundle gates pass in that postrun check because this
no-build validation still refreshed them. The missing gates are exactly the
ones requiring a real target build and smoke run.

Evidence hashes:

```text
7c453ceef425d06d7180e4855f1bfdb7580cf89d4407ea02f9a2ff69d808ebde  scripts/run_pure_pipeline_target_flow.sh
16177408730b62245d462f973a18a2e269156a8053e26a55252f2f7fbcc2ee56  scripts/audit_pure_pipeline_status.py
d91cf6756585f6d0e8a9f55e4e0716209a3b68fc4862362cb8e496946ce4f06b  scripts/check_pure_pipeline_source_contracts.py
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_source_contracts/source_contracts_target_flow_acceptance_after_07c9f3a.tsv
6b0cd119fc0445d3017fe3ac47ab7f2ba5b1d7f795566d848256e028e0683b1d  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_target_flow_acceptance_after_07c9f3a.env
404a98c1f388a68be1420197bea1d83734a60c371417ff98c63f5aa26d93b96c  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_gates_target_flow_target_flow_acceptance_after_07c9f3a.tsv
9e3fb8eb7bc203d31172350db96ea0be4b80e2c9566e7ddfd9ca39fe177761b9  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_prelaunch_target_flow_target_flow_acceptance_after_07c9f3a.tsv
03886e5aaf38e94ce2e9e133398591ab49e3a3dd7d1e4a9da43cd703c7256a64  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_postrun_target_flow_target_flow_acceptance_after_07c9f3a_expected_missing.tsv
289495fffc0a31547ecec01d74c400a297b3aca96d399e5551468f163e6a72c4  results/pure_pipeline_requirement_audit_target_flow_acceptance_after_07c9f3a/audit.json
88d1a17e7cf5bb09f75dff0f6bfc0aaa6c5e1434a74a6d7c20d706bbe6335bee  results/pure_pipeline_evidence_bundle_target_flow_acceptance_after_07c9f3a/summary.md
80ba8b7c537566f684760cafa55e764dfb7c3306f746760dca80b57be4b78ca8  results/pure_pipeline_evidence_bundle_target_flow_acceptance_after_07c9f3a/source_proof_matrix.tsv
```

## HW Target Prelaunch Snapshot

As of commit `b759c5c8efe508ac07ac90057409a3d4b0c32cae`, the real `hw`
target has a refreshed no-build launch snapshot. This does not claim a
successful hardware build; it proves that the target-flow wrapper can generate
the `hw` compile/link/config scripts, source fingerprints, source contracts,
readiness report, replay command, acceptance gates, audit, and compact evidence
bundle before the long Vitis run is launched.

Validation command:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label target_flow_acceptance_hw_status_sync_b759c5c \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Result:

```text
source_contracts_required_count=17
source_contracts_failed_count=0
readiness_ready=yes
prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
acceptance_check_postrun=SKIPPED
```

The readiness report was run with the target-flow wrapper's
`--allow-active-builders` behavior, so it records the external Spine
`v++/vpl/vivado` jobs as active but does not fail the no-build launch snapshot.
The real long build should still wait for those jobs to finish.

The postrun checker is expected to fail until the real `hw` build and smoke
tests exist:

```bash
./scripts/check_pure_pipeline_acceptance_gates.py \
  --acceptance-gates .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_gates_target_flow_target_flow_acceptance_hw_status_sync_b759c5c.tsv \
  --mode postrun \
  --out-file .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_postrun_target_flow_target_flow_acceptance_hw_status_sync_b759c5c_expected_missing.tsv
```

Expected current postrun result:

```text
status_counts={"FAIL": 7, "PASS": 6}
failed_gates=compile_log,link_log,target_xclbin,xclbin_contract,gate_smoke,full_smoke,same_input_compare
```

Evidence hashes:

```text
7bab4ebac62662fd54d5143d71ce4ac109981bd519f4b1c6a33bf10a8d6f36a4  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_target_flow_acceptance_hw_status_sync_b759c5c.env
5792d49b05c086545a8ed948371069653c217d1b9022aa48e2f53d85cd5d2711  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_target_flow_acceptance_hw_status_sync_b759c5c_replay.sh
5150a193aa75897ad2e87c5dc358b7b6f0544bfa8ea0b748c8c283c660b28dfa  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_gates_target_flow_target_flow_acceptance_hw_status_sync_b759c5c.tsv
a38928d064811673dc1f2abc2d9755ea1a1a1560c6b20925dc2e7b21d994ffa2  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_prelaunch_target_flow_target_flow_acceptance_hw_status_sync_b759c5c.tsv
6a0916a1fc28cec4a861ec3c6d984b60419c1358e336f39edb33388c5a9c79bf  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_postrun_target_flow_target_flow_acceptance_hw_status_sync_b759c5c_expected_missing.tsv
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_contracts_target_flow_target_flow_acceptance_hw_status_sync_b759c5c.tsv
6184216dfa8d38fd291ce5f48beffbc1e60b16fd24a5b0767446c6fc986fad75  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_fingerprints_target_flow_target_flow_acceptance_hw_status_sync_b759c5c.tsv
c043171f8cc99ccca457b093946232f2c86fc4dd6549809a0c825c6adc10f0ec  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_target_flow_target_flow_acceptance_hw_status_sync_b759c5c.txt
036fc32d5c13efca20f9f4ecd91675f12a5577d214cb23d96e85dd01655127a8  .tmp_build/pure_pipeline_hw_stage0/run_logs/monitor_after_target_flow_acceptance_hw_status_sync_b759c5c.txt
0bcc9781d4059f7259a19fbf4a560803722d6d217876878ea2ed197d453c5e86  results/pure_pipeline_requirement_audit_target_flow_acceptance_hw_status_sync_b759c5c/audit.json
7dbdc520f560f0f2b773f875fa5eca769d9f45c9b8038d668824cf21e01d54c0  results/pure_pipeline_evidence_bundle_target_flow_acceptance_hw_status_sync_b759c5c/summary.md
80ba8b7c537566f684760cafa55e764dfb7c3306f746760dca80b57be4b78ca8  results/pure_pipeline_evidence_bundle_target_flow_acceptance_hw_status_sync_b759c5c/source_proof_matrix.tsv
```

## Current-Commit Target Prelaunch Refresh

As of commit `f823169a3443463c6d8945813a5cc43f2ed32ac7`, both target
prelaunch snapshots have been refreshed from the current integration commit.
This is still a no-build refresh: it intentionally does not launch Vitis
compile/link and does not claim `hw_emu` or `hw` xclbin success.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_f823169 \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_f823169 \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Result:

```text
hw_emu_git_head=f823169a3443463c6d8945813a5cc43f2ed32ac7
hw_git_head=f823169a3443463c6d8945813a5cc43f2ed32ac7
source_contracts_required_count=17
source_contracts_failed_count=0
hw_emu_readiness_ready=yes
hw_readiness_ready=yes
hw_emu_prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw_prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

The read-only status helper now reports current target-flow evidence for both
missing hardware targets:

```bash
./scripts/report_pure_pipeline_next_steps.py
```

Observed status:

```text
hw_emu flow_current=yes xclbin=no
hw flow_current=yes xclbin=no
next_target=hw_emu
```

Postrun acceptance checks are expected to fail until the real target build and
smoke runs exist:

```text
status_counts={"FAIL": 7, "PASS": 6}
failed_gates=compile_log,link_log,target_xclbin,xclbin_contract,gate_smoke,full_smoke,same_input_compare
```

Evidence hashes:

```text
d689f468a5c4035592105a633bf46a9f90be3c592a2bc1c264b473f405f5af7f  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_f823169.env
c09741a9365b8e48f418db71721f0377926bcde1eec715edda41187ab00b034e  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_f823169_replay.sh
31f7821176a34fcbf38e082355b8054803ede05c47d7983592ba9a063a0de401  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_gates_target_flow_prelaunch_after_f823169.tsv
b0196ac27853b051a46468ba5164284cf58ad8a622d82883a56ad56b168c6384  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_f823169.tsv
4a1e037d800952bf9a59c2328d98425e90315970b3b20410bcea86d85c90023d  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_postrun_target_flow_prelaunch_after_f823169_expected_missing.tsv
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_contracts_target_flow_prelaunch_after_f823169.tsv
e010594277d0bdd627f2770e92f0b0a93c33b22afcce4a045abcc80315d6f86a  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_f823169.tsv
02cd6159cc076a622197d899313a410bf8694e7c5a68e7bc0b40231cb0aa8a25  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_target_flow_prelaunch_after_f823169.txt
185349f10c39df48ec3bcb59931095240726159df25556225264ef4c110c6537  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_prelaunch_after_f823169.txt
c2f53afe1258f5ec4fe586654ba2c1f22c3912966ec6993f925157a5cef74d6d  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_f823169.env
957ea48dc774dcd3f49a43f2a04f3cb269c6da6e951a4c931cba1e6124afa8eb  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_f823169_replay.sh
181310522f9e995c17e9703ffa6a63c2ea06ab55dbdfdfd8809a479ad2dd6015  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_gates_target_flow_prelaunch_after_f823169.tsv
ab896eee4b18db812b5ebaf84a9e81d18febb259a7b00e1389d355cc2095a785  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_f823169.tsv
c1e27dcd290b9754c148943bd4e037ae729c8d3149fe0647563e4d7a0c55589a  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_postrun_target_flow_prelaunch_after_f823169_expected_missing.tsv
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_contracts_target_flow_prelaunch_after_f823169.tsv
e010594277d0bdd627f2770e92f0b0a93c33b22afcce4a045abcc80315d6f86a  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_f823169.tsv
955543253abfa764e12a5aba027f47487e74bac3700382f4b69e98901c18a79f  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_target_flow_prelaunch_after_f823169.txt
17fce607a3175d591328a24b032005d2a66ba90cf2b8207fc9ab309deb045a8f  .tmp_build/pure_pipeline_hw_stage0/run_logs/monitor_after_prelaunch_after_f823169.txt
5b418a7decd9148c26f8936cbe187ef04c3cf6980a7b36b4f9f4171a67e3b04e  results/pure_pipeline_requirement_audit_prelaunch_after_f823169/audit.json
79aa99a2473b89819cfd74ccde7af71ba6b59e31f250412b8afee7ef6478c69e  results/pure_pipeline_evidence_bundle_prelaunch_after_f823169/summary.md
80ba8b7c537566f684760cafa55e764dfb7c3306f746760dca80b57be4b78ca8  results/pure_pipeline_evidence_bundle_prelaunch_after_f823169/source_proof_matrix.tsv
```

## Source-Fingerprint Target Freshness

After the `7d227b7` documentation refresh, the target-flow status helper was
updated to avoid a false stale signal from documentation-only commits. The old
check compared the latest target-flow `git_head` to the current commit. That was
too strict because target-flow evidence is about build-relevant source state,
not about experiment notes.

`scripts/report_pure_pipeline_next_steps.py` now compares the recorded
`source_fingerprints.tsv` from the latest target-flow run with the current
build-relevant source tree. It falls back to the recorded `git_head` only when a
target-flow run does not include source fingerprints.

This does not change the hardware status: the current pure pipeline still has a
successful `sw_emu` xclbin only. The current `hw_emu` and `hw` targets are
prelaunch-ready but do not yet have target xclbins.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile scripts/report_pure_pipeline_next_steps.py
./scripts/report_pure_pipeline_next_steps.py

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_7d227b7_sourcefp \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_7d227b7_sourcefp \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Observed status after the no-build refresh:

```text
branch=codex/pure-hw-pipeline
head=7d227b740da1e52dc24b1bdcaf60cf8db5d535e5
sw_emu xclbin=yes sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
hw_emu xclbin=no readiness_ready=yes flow_current=yes
hw xclbin=no readiness_ready=yes flow_current=yes
next_target=hw_emu
```

Prelaunch checks:

```text
source_contracts_required_count=17
source_contracts_failed_count=0
hw_emu_prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw_prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

Postrun checks are still expected to fail until real target xclbins and smoke
runs exist:

```text
status_counts={"FAIL": 7, "PASS": 6}
failed_gates=compile_log,link_log,target_xclbin,xclbin_contract,gate_smoke,full_smoke,same_input_compare
```

Evidence hashes:

```text
b35a91111d4f9fe24aa94ed786774202ebbe0b01f83eb1fc101e4aea87126a9f  scripts/report_pure_pipeline_next_steps.py
c91bbe703460d75493d16d1cd9d275ee0d65d8af6da6643bbe3956cc5cb40f9e  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_7d227b7_sourcefp.env
dcdc07dcfefe198f67a13563fb7de6bff04e0b9e9486eff1c9887871405993f5  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_7d227b7_sourcefp_replay.sh
c025fd530cd63762a226d1e1c8f98d808e0a03fd4d60510d6fcdf87435e1638f  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_gates_target_flow_prelaunch_after_7d227b7_sourcefp.tsv
b898f7e9653310d1ba26f745ec975917ece8b9eb8f3a5718713c3bc5d5c85d40  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_7d227b7_sourcefp.tsv
d4f2fb57a51ee24ade566789b3849807a417699193f7b8412925836dbdb967ec  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_postrun_target_flow_prelaunch_after_7d227b7_sourcefp_expected_missing.tsv
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_contracts_target_flow_prelaunch_after_7d227b7_sourcefp.tsv
f6ce92f699bf37cfcc6db5237e561ef506fe7bf685348b7f746b783180f64533  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_7d227b7_sourcefp.tsv
9977f81edd5af32ce8ef8a214538a89b3f7146b110f99ba2ce05efc836898580  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/readiness_target_flow_prelaunch_after_7d227b7_sourcefp.txt
49be0ecbcc555aa0851227b7016ff2155484ab32e81210437a581eb50d8d5015  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/monitor_after_prelaunch_after_7d227b7_sourcefp.txt
43521159ddc1ae1325a7c0262c9058bc9dba2d605f4165c818b89f4688b58e71  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_7d227b7_sourcefp.env
6c8c8ce58e103b95c77023f079a25390a833dc9056a7f3913e14dd7cacd276af  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_7d227b7_sourcefp_replay.sh
c7133687740f249743b71b86474bb7fe8b52ad17ed4d5ba922d60241a68ef0cf  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_gates_target_flow_prelaunch_after_7d227b7_sourcefp.tsv
24d45554297d3c3264132dd93ac6b5fd737d033c251f0f0b23445a4af53d1b83  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_7d227b7_sourcefp.tsv
6827125655dfeb9f0e220d6f5cb92da814ce294e95108ee2954052e437416702  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_postrun_target_flow_prelaunch_after_7d227b7_sourcefp_expected_missing.tsv
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_contracts_target_flow_prelaunch_after_7d227b7_sourcefp.tsv
f6ce92f699bf37cfcc6db5237e561ef506fe7bf685348b7f746b783180f64533  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_7d227b7_sourcefp.tsv
be6ad039a73de293894314e93d7297cafa7df069a1cf637106283d1cf7d40e57  .tmp_build/pure_pipeline_hw_stage0/run_logs/readiness_target_flow_prelaunch_after_7d227b7_sourcefp.txt
bacd1ad697cfee4a7e37c8fb60a57fcbd8f42743a72b8c3a0fba5e0987086a4e  .tmp_build/pure_pipeline_hw_stage0/run_logs/monitor_after_prelaunch_after_7d227b7_sourcefp.txt
8302cfebebc59ee35a7ce6d2d3ec645b93aceac425816ea5ab0df51a1e583433  results/pure_pipeline_requirement_audit_prelaunch_after_7d227b7_sourcefp/audit.json
0942c78c94a6470662c0ce85ab7e67be4459b9587362865edb47d2d047e3632d  results/pure_pipeline_evidence_bundle_prelaunch_after_7d227b7_sourcefp/summary.md
80ba8b7c537566f684760cafa55e764dfb7c3306f746760dca80b57be4b78ca8  results/pure_pipeline_evidence_bundle_prelaunch_after_7d227b7_sourcefp/source_proof_matrix.tsv
```

## Current Commit Launch Packets

As of commit `55803b333f086a8901a954c54c30145fa9c793ed`, launch packets were
generated for both remaining hardware targets. These packets do not start
Vitis. They record the exact target-flow commands, source fingerprints, source
contracts, readiness reports, acceptance gates, and evidence bundle paths.

The machine still has an unrelated Spine hardware link in progress. Strict
readiness therefore fails on `active_builders`; the launch packets below were
created with `--allow-active-builders` so the prelaunch packet can be recorded
without pretending that a new long build should start immediately. The generated
target-flow command still waits for idle Vitis/Vivado resources before launching
the real build.

Packet creation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_55803b3 \
  --label hw_emu_after_55803b3_allow_active \
  --allow-active-builders

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_55803b3 \
  --label hw_after_55803b3_allow_active \
  --allow-active-builders
```

Generated launch commands:

```bash
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/launch_command.sh
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/launch_command.sh
```

Equivalent command lines:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_55803b3 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label after_55803b3 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Prelaunch result:

```text
hw_emu source_contract_status=0
hw_emu readiness_status=0
hw_emu acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw_emu readiness_warnings=2

hw source_contract_status=0
hw readiness_status=0
hw acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw readiness_warnings=1
```

Current xclbin state is unchanged:

```text
sw_emu xclbin=yes sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
hw_emu xclbin=no
hw xclbin=no
```

Readiness still records unrelated external builders:

```text
active_builder_breakdown=external total=10 v++=2 vivado=4 vpl=2 vrs=2
external build path=/data/feiyang/spine-dynamic-graph-builds/restore_tiny_active_hw_exact_20260714_0740/link_133_exact_final_retry
```

Evidence hashes:

```text
ddd0ce95e5a12c07258408a62f778c0a15e7c6dad743cb1490034b3ef9ea8c3f  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/README.md
56c76e08fd00c5401967640cd553719767cda1b2230c2015da3cffa3d6097e7a  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/launch_command.sh
a198b983e18d2ee77620bff1813eebf8dff0079c6d4dc082ccc394a380b19a80  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/launch_packet.env
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/source_contracts.tsv
f6ce92f699bf37cfcc6db5237e561ef506fe7bf685348b7f746b783180f64533  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/source_fingerprints.tsv
e12aaa1dfd651ba4a37615ef536c3fe3f3a7b3a5c018b69952608d299caa1649  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/readiness_hw_emu.txt
364f5056e08add413962019449a9daea0cf418094872636e125488d698fe4752  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/acceptance_gates.tsv
1dc7db5adbfe68eaab02fe64d34347d6d0e7cb001c0ee33d66c204d39a4e3c3c  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/acceptance_check_prelaunch.tsv
98a76e2c02c810bf57c755362a0f1fc368cec51e4a773ad868e524c38a2073ad  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/audit/audit.json
9ef40a32419f8be49fd8e7a57559591a82ae9be13e57bd467f450a8bee273534  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/evidence_bundle/summary.md
80ba8b7c537566f684760cafa55e764dfb7c3306f746760dca80b57be4b78ca8  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_55803b3_allow_active/evidence_bundle/source_proof_matrix.tsv
1621a78e23b4602633e3a88463f2ed048da78313051bb3e48543b0015dbcdfee  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/README.md
e2930bffc0458de91be4a6d12bb3731855d23f25894172a55df04ebc08cb4995  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/launch_command.sh
f82cca20c829e558409c6bc21ea8ce4143e5f4a136b5cc7c1fba8aa274e4c5a6  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/launch_packet.env
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/source_contracts.tsv
f6ce92f699bf37cfcc6db5237e561ef506fe7bf685348b7f746b783180f64533  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/source_fingerprints.tsv
710a1fded9deb884833dfa49ae9a465440113ab5aed750e66669758ba663edff  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/readiness_hw.txt
c920a575455d4f8cc5fd04bd037d485b9804c6a146b210a36d0492368a756fea  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/acceptance_gates.tsv
92feff7379c1bb23af218fdaf96f2ae1faa9b00d40b486788b971aaf202946a1  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/acceptance_check_prelaunch.tsv
ea71cb126f3abe0b9673a6c8c4f0672747030f6bb2207cb99017bab8da1f724a  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/audit/audit.json
97de6eb3dee8837587473c5f884a9569ab38d304068735759dd918e44b00dde7  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/evidence_bundle/summary.md
80ba8b7c537566f684760cafa55e764dfb7c3306f746760dca80b57be4b78ca8  .tmp_build/pure_pipeline_launch_packet_hw_after_55803b3_allow_active/evidence_bundle/source_proof_matrix.tsv
```

## Readiness Mode Split

The audit and evidence-bundle scripts now distinguish two readiness meanings:

- `latest_*_readiness`: the newest readiness report, which may be an
  `--allow-active-builders` launch/readiness packet.
- `latest_*_readiness_strict`: the newest strict readiness report with
  `allow_active_builders=0`, used to show whether another Vitis/Vivado job is a
  real launch blocker.
- `latest_*_readiness_allow_active`: the newest readiness report with
  `allow_active_builders=1`, used to show whether the pure pipeline scripts and
  generated target build files are otherwise ready.

This avoids mixing two different statements:

```text
allow-active readiness: ready=yes, blocking_count=0
strict readiness: ready=no, blocking_count=1 because external Vitis/Vivado builders are active
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/audit_pure_pipeline_status.py \
  scripts/export_pure_pipeline_evidence_bundle.py

./scripts/audit_pure_pipeline_status.py \
  --label continuation_07efd70_readiness_modes \
  --out-dir results/pure_pipeline_requirement_audit_continuation_07efd70_readiness_modes

./scripts/export_pure_pipeline_evidence_bundle.py \
  --audit results/pure_pipeline_requirement_audit_continuation_07efd70_readiness_modes/audit.json \
  --out-dir results/pure_pipeline_evidence_bundle_continuation_07efd70_readiness_modes
```

Observed bundle target rows now show both modes. For `hw_emu` and `hw`:

```text
readiness_allow_active_builders=1
readiness_ready=yes
readiness_blocking_count=0
strict_readiness_ready=no
strict_readiness_blocking_count=1
strict_readiness_external_builders=10
strict_readiness_external_builder_breakdown=total=10 v++=2 vivado=4 vpl=2 vrs=2
```

After changing the scripts, the no-build target-flow snapshots were refreshed
so source fingerprints match the current build-relevant source tree:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_07efd70_readiness_modes \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_07efd70_readiness_modes \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Prelaunch acceptance remains:

```text
hw_emu status_counts={"PASS": 4, "PENDING": 9}
hw status_counts={"PASS": 4, "PENDING": 9}
```

The hardware status is unchanged: `sw_emu` has an xclbin, while `hw_emu` and
`hw` still do not.

Evidence hashes:

```text
20d2d8b96087fdff1b8df7993e73a0fb0a2058d3f4b9b371814c6090fb822840  scripts/audit_pure_pipeline_status.py
76154f9e6bbdb462793d30958b6e3f3f29d568fb7cea61ee7798433206a3cf99  scripts/export_pure_pipeline_evidence_bundle.py
4266378565dad01b0d2f129260c39e287ed7ba0a2724d831e065ea2dd2fc526d  results/pure_pipeline_requirement_audit_continuation_07efd70_readiness_modes/audit.json
afa6f8babff0387ed78e731daa2bb39c811b3100b500c2c1a146005c9d2ca8fe  results/pure_pipeline_evidence_bundle_continuation_07efd70_readiness_modes/summary.md
0c656471e22114fe2f4ac9641888ea0ce9b761473d5d1625d591a55dd935e410  results/pure_pipeline_evidence_bundle_continuation_07efd70_readiness_modes/target_matrix.tsv
83fa1df8c7713303658b0df11087b41a0b6bfd86bc4b98b226d8e181fb2a4903  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_07efd70_readiness_modes.env
40039248b688ba9ab6cb25badc89819de519b697af2b1088bb4703718a8c8260  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_07efd70_readiness_modes.tsv
51957117cfd9396c7dccdc8f5061a4a588ae265f02c046bb87bee1cb94ae56cc  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_07efd70_readiness_modes.tsv
afefd7ed30cb6e72f1f6dcac0120a0f2b05eaf31f5d6e2e359f618c66ed63b9d  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_07efd70_readiness_modes.env
40039248b688ba9ab6cb25badc89819de519b697af2b1088bb4703718a8c8260  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_07efd70_readiness_modes.tsv
bb60ce0b37bc7bf616b8631f5fc314ce4a9970f36fc1d17c3aba79b0afd84776  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_07efd70_readiness_modes.tsv
2ee91812618a166c0658d2dcc67c29d55081e68119b2f80250f9b558c31e44c0  results/pure_pipeline_requirement_audit_prelaunch_after_07efd70_readiness_modes/audit.json
febb1f36eb952351026e6597ee2a9d03657881486f1a58aacf752b1f9f9925b3  results/pure_pipeline_evidence_bundle_prelaunch_after_07efd70_readiness_modes/summary.md
326178e652ea40a4594802e0709cbdbd880a87cd1fb30b7d17fc3d810b55ae37  results/pure_pipeline_evidence_bundle_prelaunch_after_07efd70_readiness_modes/target_matrix.tsv
```

## Status Helper Readiness Columns

As of 2026-07-15 Asia/Shanghai, `report_pure_pipeline_next_steps.py` also
prints the strict readiness view next to the latest readiness view. This keeps
the console summary aligned with the audit and evidence-bundle split above:

- `readiness_ready`: newest readiness report, which may be an
  `allow_active_builders=1` prelaunch snapshot.
- `strict_ready`: newest strict readiness report with `allow_active_builders=0`.
- `strict_blockers`: blocker count from that strict report.
- `flow_current`: whether the latest no-build target-flow source fingerprints
  match the current build-relevant source tree.

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile scripts/report_pure_pipeline_next_steps.py
./scripts/report_pure_pipeline_next_steps.py
./scripts/report_pure_pipeline_next_steps.py --json | python3 -m json.tool \
  >/tmp/pure_pipeline_next_steps_report_modes_after_refresh.json
```

Observed summary:

```text
branch=codex/pure-hw-pipeline
head=9de8f9dba7b7c1a9480a8d96809a78bb78027cd7
dirty=true

sw_emu xclbin=yes sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
hw_emu xclbin=no readiness_ready=yes strict_ready=no strict_blockers=1 flow_current=yes
hw xclbin=no readiness_ready=yes strict_ready=no strict_blockers=1 flow_current=yes

active_builders=related:0 external:10
next_target=hw_emu
```

The hardware status is still unchanged: `sw_emu` has the only pure-pipeline
xclbin, while pure `hw_emu` and `hw` xclbins are absent. The target-flow
prelaunch evidence is current and says the generated build path is otherwise
ready, but strict launch readiness still fails because unrelated external
Vitis/Vivado builders are active.

The source-fingerprint refresh used no build and no finalize step:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_9de8f9d_report_modes \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_9de8f9d_report_modes \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Observed target-flow results:

```text
hw_emu source_contracts=PASS 17/17
hw_emu readiness_ready=yes blocking_count=0 warning_count=2 allow_active_builders=1
hw_emu prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw_emu audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}

hw source_contracts=PASS 17/17
hw readiness_ready=yes blocking_count=0 warning_count=1 allow_active_builders=1
hw prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

Evidence hashes:

```text
567b82f4bb573b0df3a1e117f7600b60c71512c60e368356413cd769a7f06785  scripts/report_pure_pipeline_next_steps.py
46341fecde264ba74882b33d4abafa3929cd9adc201e4cd518182454e80d21a7  README.md
e1332199900f676d8287987e313b4817c7b2ba7598e691b7d417c0ab8a718dd1  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_9de8f9d_report_modes.env
c3c51799cd7f33c3f5f14c5cb5c8453a0b78454afdd70464e87c5ce2a8492505  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_9de8f9d_report_modes.tsv
529cdcc9f797d488f12ff14724a5695549108b577bc8ba2935b8d759ca559c88  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_9de8f9d_report_modes.tsv
de4aa0d12cb9f13145f7c0e345fc94e413fc3f8ed7a45f3c3961185fbe7647b6  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_9de8f9d_report_modes.env
c3c51799cd7f33c3f5f14c5cb5c8453a0b78454afdd70464e87c5ce2a8492505  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_9de8f9d_report_modes.tsv
b0309ef68b26888e74cda7d7ab958e78f334ae456dbb8b2807ae20e5be2b143e  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_9de8f9d_report_modes.tsv
85c7140142eda2cc928981e1cc3be8f5a839d4f7657f8c4afdfade07700c224b  results/pure_pipeline_requirement_audit_prelaunch_after_9de8f9d_report_modes/audit.json
f3106a16d6d99b7499ab09da69ef366e5ff1f7e615d0da13af5fd1f117f1877f  results/pure_pipeline_evidence_bundle_prelaunch_after_9de8f9d_report_modes/summary.md
bbc7ddb6f7dabfaec463e0f0dfdc7e60962736268b7731b57a60e8943ca5d6bd  results/pure_pipeline_evidence_bundle_prelaunch_after_9de8f9d_report_modes/target_matrix.tsv
```

## Current Commit Launch Packets

As of commit `dfa5b19382479ef0ee8a6927a437787dfa98fda0`, fresh launch
packets exist for both remaining long builds. They were created with
`--allow-active-builders` because the unrelated Spine Vitis/Vivado process tree
is still active. The generated launch commands themselves still include the
`--wait-idle 7200 --idle-poll 60 --idle-settle 120` guard, so running the packet
waits for an idle machine before starting the long compile.

Packet creation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_dfa5b19 \
  --label hw_emu_after_dfa5b19_allow_active \
  --allow-active-builders

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_dfa5b19 \
  --label hw_after_dfa5b19_allow_active \
  --allow-active-builders
```

Generated launch packet paths:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active
```

Generated long-build commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_dfa5b19 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label after_dfa5b19 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Equivalent executable command files:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/launch_command.sh
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/launch_command.sh
```

Observed prelaunch packet status:

```text
hw_emu source_contract_status=0
hw_emu readiness_status=0
hw_emu prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw_emu audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}

hw source_contract_status=0
hw readiness_status=0
hw prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

Current xclbin state remains:

```text
sw_emu xclbin=yes sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
hw_emu xclbin=no
hw xclbin=no
```

Packet environment records:

```text
integration_branch=codex/pure-hw-pipeline
integration_head=dfa5b19382479ef0ee8a6927a437787dfa98fda0
integration_tracked_dirty=clean
grasu_head=25d1bb5e57133978ec1bd00c7fefb21b89897044
grasu_tracked_dirty=clean
regraph_head=not_git
regraph_tracked_dirty=not_git
```

Evidence hashes:

```text
48caf91c5c1250182b0f7e25b44a16ea5ad945e64c956bcc998eaf2b17f3bfca  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/README.md
f495a5ed0f2449dd2c0b38741bdc89b17387b4a5e37cf79f2540daadbbc8173d  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/launch_command.sh
ffa1d22361e18d3ce0d5b96808b826fdf37111cd8ba3034ad1f4ddd0c4b8d6f8  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/launch_packet.env
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/source_contracts.tsv
c3c51799cd7f33c3f5f14c5cb5c8453a0b78454afdd70464e87c5ce2a8492505  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/source_fingerprints.tsv
6594d0675a5072c2c9e7db867ca101434e487876ec7e71ec96b01a7aa42dd1ba  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/readiness_hw_emu.txt
d83bc268ca203869a0ff833242125556acee0a8af57eddc998ede863ee319007  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/acceptance_gates.tsv
29f62f7309aa6d1bbc604f07e3b2fa3ed9d161ed143eec16684e74f5994065fc  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/acceptance_check_prelaunch.tsv
e209caae9d244b2ef632f7fc1a21fa6d355c61bdb5279dc20ab49391e9a9ff87  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/audit/audit.json
75caee77b13685a22bd3f2a03467a89cad2b32ae6de8aa82e5d0c3f7bf9dafe7  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/evidence_bundle/summary.md
58b59bdac95e12157fb862f0e96f503f89aeec8acb452abf6f5abd34305ad362  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/evidence_bundle/target_matrix.tsv
e721e37f059d7b844c283941191b0d9ac7a1971777c83fa811edb6ff95f529b7  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/README.md
8281fa492af43edfa72293b392d003f24ea26c6042c57089b7397b1e4e185197  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/launch_command.sh
25a91b8a0b8c52701c04c36c21929179e5c92fa5dacabd08246c730d1af2417a  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/launch_packet.env
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/source_contracts.tsv
c3c51799cd7f33c3f5f14c5cb5c8453a0b78454afdd70464e87c5ce2a8492505  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/source_fingerprints.tsv
c4dfaa5d1cede4b55fb9d279b12367f95d6040d361917e315e9933b5bd88c376  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/readiness_hw.txt
951fa448611a5135aac368eb04417e0755bac91eec0a7b17b473bf2452b338dd  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/acceptance_gates.tsv
7001010f4f1beb14680aa6830deb622e2657d365799add2b563bbec3ff084500  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/acceptance_check_prelaunch.tsv
46cf40f6c13b5f2b6360441ceb7c842b85fa76c42bd05c32840df6c75cc15e03  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/audit/audit.json
7d660471e0f94540dce77d35f5b53c6cef98b5b2310576c025e4a1f152a07c4a  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/evidence_bundle/summary.md
e0608df5004c7b4ca72206f16bad5134c0e76955eeebe9cd6af154b0dfdbb111  .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/evidence_bundle/target_matrix.tsv
```

## Fingerprint Sidecar Validation

As of 2026-07-15 Asia/Shanghai, the prelaunch acceptance gate for
`source_fingerprints` verifies more than the summary TSV. For each role in
`source_fingerprints.tsv`, it now checks:

- the row status is `present`;
- `tree_sha256` is a 64-character sha256 digest;
- the sibling `<role>.files` list exists and is non-empty;
- the sibling `<role>.sha256s` list exists and is non-empty;
- `sha256(<role>.sha256s)` equals the row's `tree_sha256`.

This matters because `/home/chuxiao/ReGraph` is not currently a git repository.
The launch packet still records `regraph_head=not_git`, but the ReGraph source
used by the pure pipeline is now guarded by deterministic file-level sidecar
hashes for:

```text
regraph_acc_template
regraph_acc_udfs
regraph_host_src
```

Changed file:

```text
scripts/check_pure_pipeline_acceptance_gates.py
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile \
  scripts/check_pure_pipeline_acceptance_gates.py \
  scripts/check_pure_pipeline_source_contracts.py \
  scripts/report_pure_pipeline_next_steps.py

./scripts/check_pure_pipeline_acceptance_gates.py \
  --acceptance-gates .tmp_build/pure_pipeline_launch_packet_hw_emu_after_dfa5b19_allow_active/acceptance_gates.tsv \
  --mode prelaunch \
  --out-file /tmp/acceptance_hw_emu_fingerprint_sidecars.tsv

./scripts/check_pure_pipeline_acceptance_gates.py \
  --acceptance-gates .tmp_build/pure_pipeline_launch_packet_hw_after_dfa5b19_allow_active/acceptance_gates.tsv \
  --mode prelaunch \
  --out-file /tmp/acceptance_hw_fingerprint_sidecars.tsv

./scripts/check_pure_pipeline_source_contracts.py \
  --label fingerprint_sidecar_acceptance \
  --out-file /tmp/source_contracts_fingerprint_sidecar_acceptance.tsv
```

Observed acceptance detail for both existing launch packets:

```text
source_fingerprints PASS 9 source fingerprints present with sidecar hashes
source_contracts PASS 17 required source-contract proofs ok
readiness PASS
launch_command PASS
prelaunch status_counts={"PASS": 4, "PENDING": 9}
```

Because this changed a build-relevant script, the no-build target-flow evidence
was refreshed for both remaining targets:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_f782ca0_fingerprint_sidecars \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_f782ca0_fingerprint_sidecars \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Observed current status after the refresh:

```text
hw_emu xclbin=no readiness_ready=yes strict_ready=no strict_blockers=1 flow_current=yes
hw xclbin=no readiness_ready=yes strict_ready=no strict_blockers=1 flow_current=yes
active_builders=related:0 external:10
```

No long Vitis compile/link was started. The hardware status is unchanged:
`sw_emu` has the only pure-pipeline xclbin, and pure `hw_emu` / `hw` xclbins
are still missing.

Evidence hashes:

```text
b485169fc7b2fa12c7eee413f01915b2efe8a54f97e05a9f44804bf806cc7310  scripts/check_pure_pipeline_acceptance_gates.py
fc882c0e785c05f97c3ee8d61e60d7ca9f735f01d50481673465a845c336a4a3  /tmp/acceptance_hw_emu_fingerprint_sidecars.tsv
5ee17506974c89d0cef4e5dcf3089862d69e265282a697a4c049c058c9e4056e  /tmp/acceptance_hw_fingerprint_sidecars.tsv
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  /tmp/source_contracts_fingerprint_sidecar_acceptance.tsv
bd8a453da89c96355fb6ce85cb70420020c636cd90380a787998057c587ec3df  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_f782ca0_fingerprint_sidecars.env
953db5ee1a229b8e2e419a5db3c81780fc8d63f5cceda59861198bc8003ea643  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_f782ca0_fingerprint_sidecars.tsv
061809e1ac98b7de925b759d4de1cd835cf136151fb0c37baa2671250fb2de23  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_f782ca0_fingerprint_sidecars.tsv
aa5a9684a6def8cc1e234e78f6af35159ea8ee252d1d550e75920978f628b68f  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_f782ca0_fingerprint_sidecars.env
953db5ee1a229b8e2e419a5db3c81780fc8d63f5cceda59861198bc8003ea643  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_f782ca0_fingerprint_sidecars.tsv
132acf5b7a169bd5b7d46411be5fed6885bbdce86ceba7e17105c4d6695118b3  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_f782ca0_fingerprint_sidecars.tsv
8315c5c1fa11c697d9efbed4e23260fe491b48d8d6fdbcc4bc8800e94e888e81  results/pure_pipeline_requirement_audit_prelaunch_after_f782ca0_fingerprint_sidecars/audit.json
fdcc479b8d4be97ad944f6bc0db17439c041a86e3d8cc6b65be8efd3413a0e5a  results/pure_pipeline_evidence_bundle_prelaunch_after_f782ca0_fingerprint_sidecars/summary.md
291702bbaeae55b8506b617124492849d79b9fc50b6edd76d18d0ea8898a2e15  results/pure_pipeline_evidence_bundle_prelaunch_after_f782ca0_fingerprint_sidecars/target_matrix.tsv
```

## Launch Packets for 8c24bb1

After committing the fingerprint sidecar validation, fresh launch packets were
generated for the current integration commit:

```text
integration_head=8c24bb1831192c78427ef08bffd48a7b16809636
integration_tracked_dirty=clean
grasu_head=25d1bb5e57133978ec1bd00c7fefb21b89897044
grasu_tracked_dirty=clean
regraph_head=not_git
regraph_tracked_dirty=not_git
```

These packets were again created with `--allow-active-builders` because the
unrelated Spine Vitis/Vivado build tree was still active. No long Vitis
compile/link was started while generating these packets.

Packet creation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_8c24bb1 \
  --label hw_emu_after_8c24bb1_allow_active \
  --allow-active-builders

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_8c24bb1 \
  --label hw_after_8c24bb1_allow_active \
  --allow-active-builders
```

Generated packet paths:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active
```

Generated long-build commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label after_8c24bb1 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label after_8c24bb1 \
  --prepare \
  --wait-idle 7200 \
  --idle-poll 60 \
  --idle-settle 120 \
  --clean-build-artifacts \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Equivalent executable command files:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/launch_command.sh
/home/chuxiao/grasu-regraph-integration/.tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/launch_command.sh
```

Observed prelaunch packet status:

```text
hw_emu source_contract_status=0
hw_emu readiness_status=0
hw_emu prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw_emu source_fingerprints="9 source fingerprints present with sidecar hashes"
hw_emu audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}

hw source_contract_status=0
hw readiness_status=0
hw prelaunch_acceptance_status_counts={"PASS": 4, "PENDING": 9}
hw source_fingerprints="9 source fingerprints present with sidecar hashes"
hw audit_status_counts={"blocked_by_missing_artifact": 1, "partial": 8, "proven": 1}
```

Current status after generating these packets:

```text
sw_emu xclbin=yes sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862
hw_emu xclbin=no readiness_ready=yes strict_ready=no strict_blockers=1 flow_current=yes
hw xclbin=no readiness_ready=yes strict_ready=no strict_blockers=1 flow_current=yes
active_builders=related:0 external:10
```

Evidence hashes:

```text
6cf31910c968c43bf8fcb149d19967bdbfd6a1190c233d0c33e335507bdefd52  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/README.md
990b54135b896eb8eaeefc2ab60cce245d22ba06f0dc62fb1c2d0a977ccbfc12  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/launch_command.sh
f729797e35ef862dc61826d41277fe44ce12f75354e5e361e3ab3344fc09dd48  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/launch_packet.env
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/source_contracts.tsv
953db5ee1a229b8e2e419a5db3c81780fc8d63f5cceda59861198bc8003ea643  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/source_fingerprints.tsv
d524a31615504e53478021208e746599f7f136063b896f25fe1852cef8d9af30  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/readiness_hw_emu.txt
968a824e06540c66eed9c7bbf2a66e5a8e4935cdbdb63b22c58902679f0f00e1  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/acceptance_gates.tsv
08218246dcccbfb32d359cc9c948a12194ac0fa747b3596606bd10bd3ad6899f  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/acceptance_check_prelaunch.tsv
aad3b6dfe26fb52b96fa9cb984b454afd190f76b3b0730c5eeac2ac6efad2863  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/audit/audit.json
e85cde118e61aca1090f4bb5d5c30ba269591ae96376a0244b2d65ff7b4cc69c  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/evidence_bundle/summary.md
31f3fc4d1eb1c91f55bed7077b01b01c8c5accebf65ba827362c14888d63676e  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_8c24bb1_allow_active/evidence_bundle/target_matrix.tsv
353a3f9b419190ca22de894d5b533d0aba5a54ba612bb531f5034329f9acd857  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/README.md
9682b0ce17529963870246ef7a7dec81f5673c260e4fcb618bd1e32afd5cc933  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/launch_command.sh
06a07dae104a03198e3b3f7d8463e0e0cb36b5244ee9671814da5af37278c912  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/launch_packet.env
fe95c3869c02a9af5182c3ed601dc95a04ac5aafc8b32f0ad6748c4b4fc254ac  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/source_contracts.tsv
953db5ee1a229b8e2e419a5db3c81780fc8d63f5cceda59861198bc8003ea643  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/source_fingerprints.tsv
87b108a2323ed1a511407eebc263c212fb120ba5fcc47af7f97067593254ff69  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/readiness_hw.txt
6827470d728f1a53fe62a4fd703cd57801d11b9ceb0ae0cd2ba3cd194494528c  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/acceptance_gates.tsv
4dcb4c9a0777369fb1d30e0cd3d65a353407e384dd1863f5f412dbdc68f5b751  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/acceptance_check_prelaunch.tsv
caec4dfe10fd9e66d7da86c63f116911f13382fb6c0fd18c8e5c3b5bcfec5767  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/audit/audit.json
bcfaea35a4bb17f93cad508d5a999aa8ef4e7abc3f885a595db7d42309aec201  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/evidence_bundle/summary.md
5f1d4e7dacfce6df4647b4faea9290dce07b42467372ce8656430c13a59d5f85  .tmp_build/pure_pipeline_launch_packet_hw_after_8c24bb1_allow_active/evidence_bundle/target_matrix.tsv
```

## Packet-Aware Next-Step Report

As of commit `c23a1f19b74657fb93009cdee1d6b32201acdb7b`, the read-only next-step
helper reports whether a saved launch packet still matches the current
build-relevant source fingerprints. This separates two ideas:

- `flow_current`: latest no-build target-flow evidence matches the current
  build-relevant source fingerprint set.
- `packet_current`: a saved launch packet exists for the target and its
  `source_fingerprints.tsv` matches the same build-relevant source fingerprint
  set.

When `packet_current=yes` for the next missing target, the helper recommends the
packet's executable `launch_command.sh` directly instead of inventing another
equivalent label from a documentation-only commit.

Changed files:

```text
README.md
scripts/report_pure_pipeline_next_steps.py
```

Validation before committing the helper:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile scripts/report_pure_pipeline_next_steps.py
./scripts/report_pure_pipeline_next_steps.py
./scripts/report_pure_pipeline_next_steps.py --json | python3 -m json.tool \
  >/tmp/report_launch_packet_current_dirty.json
git diff --check
```

The helper change intentionally made old target-flow evidence and old launch
packets stale because `scripts/report_pure_pipeline_next_steps.py` is included
in the build-relevant `integration_scripts` fingerprint role. After committing
the helper, fresh packets were generated:

```bash
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_c23a1f1 \
  --label hw_emu_after_c23a1f1_allow_active \
  --allow-active-builders

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_c23a1f1 \
  --label hw_after_c23a1f1_allow_active \
  --allow-active-builders
```

And no-build target-flow evidence was refreshed:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_c23a1f1_packet_report \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_c23a1f1_packet_report \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Observed report after the refresh:

```text
head=c23a1f19b74657fb93009cdee1d6b32201acdb7b
source_fingerprint_sha256=efa4fa7e1ea59243d94e4db2bbe5927af1296a2f961f3db9f067164f162497f6
dirty=false

hw_emu xclbin=no readiness_ready=yes strict_ready=no strict_blockers=1 flow_current=yes packet_current=yes
hw xclbin=no readiness_ready=yes strict_ready=no strict_blockers=1 flow_current=yes packet_current=yes

active_builders=related:0 external:10
next_target=hw_emu
next_commands=.tmp_build/pure_pipeline_launch_packet_hw_emu_after_c23a1f1_allow_active/launch_command.sh
```

Prelaunch acceptance remains:

```text
hw_emu launch packet: PASS=4, PENDING=9
hw launch packet: PASS=4, PENDING=9
hw_emu target-flow prelaunch: PASS=4, PENDING=9
hw target-flow prelaunch: PASS=4, PENDING=9
```

No long Vitis compile/link was started. The hardware status is unchanged:
`sw_emu` has the only pure-pipeline xclbin, while pure `hw_emu` and `hw`
xclbins are still missing.

Evidence hashes:

```text
d071f0f7e7e9cdebb21fa1a8814eec9404575fb126bd2b49acfb8add2397a346  scripts/report_pure_pipeline_next_steps.py
01ba3169b039fae6b4f782e52b62b7b7b9f181a2ee51edfb1d49d65776799826  README.md
cd0c95139e9bfbca3e635d213c9c537516f7560995d43b4101da092a8467319c  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_c23a1f1_allow_active/launch_command.sh
fc6a8f5f04348a7c6bd0a0db4a329b98a1e5eb2223823477343a6578ad44a3d0  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_c23a1f1_allow_active/launch_packet.env
44708ce0c0e7d5efd9b0337b72e3c9917eb43bca7b41c373f2fc4f99d875fcf2  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_c23a1f1_allow_active/source_fingerprints.tsv
fbbb32673379292794de5b77c721f2c2d35877321432d8e1f251ad188feff16e  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_c23a1f1_allow_active/acceptance_check_prelaunch.tsv
0f86b42377e838771afa55a3e74aa782cdd0fb27bba498ee7d34ff5d2aca608d  .tmp_build/pure_pipeline_launch_packet_hw_after_c23a1f1_allow_active/launch_command.sh
d552dda36f62e36852567dabd4dc548ff2d3bb84b238ae98e00df98147d3ed8b  .tmp_build/pure_pipeline_launch_packet_hw_after_c23a1f1_allow_active/launch_packet.env
44708ce0c0e7d5efd9b0337b72e3c9917eb43bca7b41c373f2fc4f99d875fcf2  .tmp_build/pure_pipeline_launch_packet_hw_after_c23a1f1_allow_active/source_fingerprints.tsv
3b8504f7a7940f8e8e57408c2b7d05ef1713dfd4844bd9dd14f3fcd5b16e6e05  .tmp_build/pure_pipeline_launch_packet_hw_after_c23a1f1_allow_active/acceptance_check_prelaunch.tsv
11a3d0059c66ce26c341f433247a3a4af3f36e9bb3ed68b542022de42cfb089f  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_c23a1f1_packet_report.env
44708ce0c0e7d5efd9b0337b72e3c9917eb43bca7b41c373f2fc4f99d875fcf2  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_c23a1f1_packet_report.tsv
60b077340531934e25c6f298ab64b54646cd58261a3bc1c2dc3895d5e6252af6  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_c23a1f1_packet_report.tsv
a0f319ed89c856f48a9194cdc790541bdb9f9db4525a366fa3ba48a2e7fcbc16  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_c23a1f1_packet_report.env
44708ce0c0e7d5efd9b0337b72e3c9917eb43bca7b41c373f2fc4f99d875fcf2  .tmp_build/pure_pipeline_hw_stage0/run_logs/source_fingerprints_target_flow_prelaunch_after_c23a1f1_packet_report.tsv
457bf5a07dcbbeaa09b12d503b8b7118a82245087fc0062ba9d75129e2aa9398  .tmp_build/pure_pipeline_hw_stage0/run_logs/acceptance_check_prelaunch_target_flow_prelaunch_after_c23a1f1_packet_report.tsv
bf8b82a4ae052bc5d933f17046c6d4ebe0d539bc7f8fbe47f77b3bffd313202d  results/pure_pipeline_requirement_audit_prelaunch_after_c23a1f1_packet_report/audit.json
40541fdfe7deacff4a93d4f77a3f9c5ab1ff38349a1ad0822a9a53fcd7e64f1f  results/pure_pipeline_evidence_bundle_prelaunch_after_c23a1f1_packet_report/summary.md
4cf353c685ca781de48f03b719ce6139cb46e477bd0b208f9b6d07c39209c05e  results/pure_pipeline_evidence_bundle_prelaunch_after_c23a1f1_packet_report/target_matrix.tsv
```

## Postrun-Aware Next-Step Report

As of commits `66a5122eab8f21e57000454c4dd6637b38c6666d` and
`71d901a71d3db7b2435fcaba33e55a6fcb39fe1f`, the read-only next-step helper
also reports post-build acceptance status. This prevents a target from being
treated as complete just because its xclbin exists: after a future `hw_emu` or
`hw` xclbin appears, the helper will keep that same target active until the
postrun acceptance gates prove gate smoke, full four-family smoke,
same-input comparison, requirement audit, and evidence bundle export.

Current state after the refresh:

```text
head=71d901a71d3db7b2435fcaba33e55a6fcb39fe1f
source_fingerprint_sha256=7dede5def04f80666fedeacddb1aed92b82d4eb9539105cb4c65ef808859cdfd
dirty=false

sw_emu xclbin=yes postrun=missing
hw_emu xclbin=no flow_current=yes packet_current=yes postrun=waiting_xclbin
hw xclbin=no flow_current=yes packet_current=yes postrun=waiting_xclbin

active_builders=related:0 external:10
next_target=hw_emu
next_action=build
next_commands=.tmp_build/pure_pipeline_launch_packet_hw_emu_after_71d901a_allow_active/launch_command.sh
```

Validation commands:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile scripts/report_pure_pipeline_next_steps.py
./scripts/report_pure_pipeline_next_steps.py
./scripts/report_pure_pipeline_next_steps.py --json | python3 -m json.tool \
  >/tmp/pure_pipeline_next_steps_postrun_check.json
git diff --check
```

Fresh launch packets were generated from the clean `71d901a` tree:

```bash
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_71d901a \
  --label hw_emu_after_71d901a_allow_active \
  --allow-active-builders

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_71d901a \
  --label hw_after_71d901a_allow_active \
  --allow-active-builders
```

No-build target-flow evidence was refreshed without launching Vitis compile or
link:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_71d901a_postrun_report \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_71d901a_postrun_report \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

Prelaunch acceptance remains the expected state for both hardware targets:

```text
PASS=4, PENDING=9
```

Hardware status is still unchanged: the only pure-pipeline xclbin is
`sw_emu`; pure `hw_emu` and pure `hw` xclbins are still missing. The next long
command to hand to a build terminal is:

```bash
cd /home/chuxiao/grasu-regraph-integration
.tmp_build/pure_pipeline_launch_packet_hw_emu_after_71d901a_allow_active/launch_command.sh
```

Evidence hashes:

```text
b2407871adfd59c69db7ca90f58e44de7dece3aac5e8cae9dff04a31335fc802  scripts/report_pure_pipeline_next_steps.py
a02d87d1ffd05697039139f726b25e4408d9185a625650261fcd1c36dfba5772  README.md
8c45b74b48b30907b5cd76020bb15bf7d9a1e536d1a3eb07c80eb11c2d75d77b  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_71d901a_allow_active/launch_command.sh
4750d8794f26b7ce5d8a381fdf67af8a5463a8d9391a258e87bf5216e4f7667a  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_71d901a_allow_active/launch_packet.env
0571cec9830df3efec2d62e6a75279f9aeb9aa43126b15ab885b70e67eab958e  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_71d901a_allow_active/source_fingerprints.tsv
c33694989bbdd5cdb965b2fda7fa2ea0bd24f6cc1f8f59cbf04f161642a44b2a  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_71d901a_allow_active/acceptance_check_prelaunch.tsv
2a1885d619fc75332338418329a0d4e361ec819139b68172a1c9aef014627c7c  .tmp_build/pure_pipeline_launch_packet_hw_after_71d901a_allow_active/launch_command.sh
1e6b97389d00bfb42e4343d7c63c430bfb21895c72780621318a38bbdca70a93  .tmp_build/pure_pipeline_launch_packet_hw_after_71d901a_allow_active/launch_packet.env
0571cec9830df3efec2d62e6a75279f9aeb9aa43126b15ab885b70e67eab958e  .tmp_build/pure_pipeline_launch_packet_hw_after_71d901a_allow_active/source_fingerprints.tsv
4c445810b9b6693c7e678abf2477b0ba8939fecfded3bfd40b706faac33de882  .tmp_build/pure_pipeline_launch_packet_hw_after_71d901a_allow_active/acceptance_check_prelaunch.tsv
eced1666a18c480a46491342d8bb195aef04b6e195a3790fce8fff0525e6c2b8  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_71d901a_postrun_report.env
d8390d14e24535073abad0e8f3db48db287858085dd919aa7d246ad64c96599a  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_71d901a_postrun_report.env
83c99da5da0e2961f49ebe43f2e9f1ee77e3a457ed78ac804bd37970246937fe  results/pure_pipeline_requirement_audit_prelaunch_after_71d901a_postrun_report/audit.json
c2bc15e21dc316c5b900e6ff1bbb4a6eaca59e52e509fccd242672732dfe3c42  results/pure_pipeline_evidence_bundle_prelaunch_after_71d901a_postrun_report/summary.md
824429466f8275a30a2c6e70d50fec47c34d9cce54f98880a15f083e199f3d23  results/pure_pipeline_evidence_bundle_prelaunch_after_71d901a_postrun_report/target_matrix.tsv
```

## Skip-Build Postrun Acceptance Fix

As of commit `4f3afb93ac5180da7d1d61e18eeeb2e01991050f`, the target-flow
wrapper correctly supports postrun validation on an already-built xclbin. This
matters because the next-step helper recommends a `--skip-build` command when a
target xclbin exists but its smoke/compare/audit/bundle acceptance has not yet
passed.

The bug was:

- `run_pure_pipeline_target_flow.sh --skip-build` skipped the postrun
  acceptance check entirely.
- Its acceptance checklist still required `compile_<label>.log` and
  `link_<label>.log` for the new postrun label, even though the build was
  intentionally skipped.

The fix:

- Postrun acceptance now runs even when `--skip-build` is set, as long as
  finalize, audit, bundle, and acceptance are not skipped.
- In skip-build flows, `compile_log` and `link_log` are marked `required=no`.
  The flow still requires the existing xclbin, xclbin metadata contract, smoke
  summaries, same-input comparison, requirement audit, and evidence bundle.

Validation before committing:

```bash
cd /home/chuxiao/grasu-regraph-integration
bash -n scripts/run_pure_pipeline_target_flow.sh
git diff --check
./scripts/run_pure_pipeline_target_flow.sh \
  --target sw_emu \
  --label skipbuild_acceptance_contract_check \
  --skip-build \
  --skip-finalize \
  --skip-audit \
  --skip-bundle \
  --dry-run
```

The dry-run acceptance checklist correctly contained:

```text
compile_log required=no
link_log    required=no
```

After committing, current `sw_emu` postrun validation was rerun without
relinking:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target sw_emu \
  --label postrun_after_4f3afb9 \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 180 \
  --timeout 300
```

Result:

```text
acceptance_check_postrun: PASS=11, SKIP=2
smoke: chain, hot-source, spread, hot-destination all PASS with mismatches=0
compare: same-input host zero-cost and Spine comparison regenerated
```

The current status report is:

```text
head=4f3afb93ac5180da7d1d61e18eeeb2e01991050f
source_fingerprint_sha256=baf531b0cd3e4088eb942b511077e94954b8bfe481e98deb1a3996cad408b579
dirty=false

sw_emu xclbin=yes flow_current=yes postrun=pass:PASS=11,SKIP=2
hw_emu xclbin=no flow_current=yes packet_current=yes postrun=waiting_xclbin
hw xclbin=no flow_current=yes packet_current=yes postrun=waiting_xclbin

next_target=hw_emu
next_action=build
next_commands=.tmp_build/pure_pipeline_launch_packet_hw_emu_after_4f3afb9_allow_active/launch_command.sh
```

Fresh hardware launch packets were regenerated because the target-flow script is
part of the build-relevant source fingerprint:

```bash
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_4f3afb9 \
  --label hw_emu_after_4f3afb9_allow_active \
  --allow-active-builders

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_4f3afb9 \
  --label hw_after_4f3afb9_allow_active \
  --allow-active-builders
```

No-build target-flow evidence was also refreshed:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_4f3afb9_skipbuild_acceptance \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_4f3afb9_skipbuild_acceptance \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

The next long command remains:

```bash
cd /home/chuxiao/grasu-regraph-integration
.tmp_build/pure_pipeline_launch_packet_hw_emu_after_4f3afb9_allow_active/launch_command.sh
```

Evidence hashes:

```text
9f2e7f212091ccc729678e520dad132dfeebf23156adbf9b234934ca466a34e8  scripts/run_pure_pipeline_target_flow.sh
c506fed573012f01c15edc26582b75b84e4e2db9bf9798ef08345b6351843c53  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/acceptance_check_postrun_target_flow_postrun_after_4f3afb9.tsv
e9ac52e7b51072094450dceb0f0387871320f33f9023cf2c5216ee8f3f6cf776  results/pure_pipeline_sw_emu_smoke_postrun_after_4f3afb9/summary.tsv
76e638cb0ce204afab2843cb83b796a0b0b4ccbf1f0d30adc85aaffeb738872d  results/pure_pipeline_sw_emu_compare_postrun_after_4f3afb9/comparison.tsv
4863c32fae7df3e7735333f65a164149e07af3ec6e1f9e01fe1ac35e44e05c67  results/pure_pipeline_requirement_audit_postrun_after_4f3afb9/audit.json
b3188d00aed6bd41b88c6c9bb43aa26f86d2f45ceb1ef9ce11f676d9f9be436a  results/pure_pipeline_evidence_bundle_postrun_after_4f3afb9/summary.md
81bcaf388bd2a2ae40b2e55eac3ae88d804b19aecd28b26540e24eb38baa6fd4  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_4f3afb9_allow_active/launch_command.sh
ef37d99376b44fdb71e4e215e251a100a06dd417ef7dc51f23da631342ff1dae  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_4f3afb9_allow_active/acceptance_check_prelaunch.tsv
8257b73503fa179703391454059be7d8d86bd72dc838cb5a7e5cae1cdbcc0750  .tmp_build/pure_pipeline_launch_packet_hw_after_4f3afb9_allow_active/launch_command.sh
bdf686670a1feb8d6d827006cfa95ea61596dcca9f869555e1abf97aa4ccfdc9  .tmp_build/pure_pipeline_launch_packet_hw_after_4f3afb9_allow_active/acceptance_check_prelaunch.tsv
1e19c8937ae77a1d123dfbb2febfad7e221c0d3542e589fd138eb4b20416bd06  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_4f3afb9_skipbuild_acceptance.env
372c2c47329676555e6accead73d9ab1459333697d0b087ab0c7a6a72c369aac  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_4f3afb9_skipbuild_acceptance.env
```

## Current Pure-HW Artifact Clarification, 2026-07-15

This update records the current artifact boundary after checking the live
worktree. The old `combined` GraSU+ReGraph hardware xclbin still exists, but it
is not the current pure-hardware pipeline target. It must not be used as
evidence that the PMA barrier + adapter + ReGraph stream pipeline has a finished
`hw` build.

Current branch and report command:

```bash
cd /home/chuxiao/grasu-regraph-integration
git status --short --branch
./scripts/report_pure_pipeline_next_steps.py
find .tmp_build -name '*.xclbin' -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n'
find .tmp_build -name '*.xclbin' -exec sha256sum {} +
```

Observed state before this documentation/script cleanup:

```text
branch=codex/pure-hw-pipeline
head=3905413ed44ce5b0fbb91a491a31739b4a312be2
dirty=false
source_fingerprint_sha256=baf531b0cd3e4088eb942b511077e94954b8bfe481e98deb1a3996cad408b579

sw_emu xclbin=yes sha256=b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862 postrun=pass:PASS=11,SKIP=2
hw_emu xclbin=no postrun=waiting_xclbin
hw xclbin=no postrun=waiting_xclbin

next_target=hw_emu
next_action=build
next_commands=.tmp_build/pure_pipeline_launch_packet_hw_emu_after_4f3afb9_allow_active/launch_command.sh
```

Existing xclbins found in `.tmp_build`:

```text
d721465b8b377bf8272d4903edff4293522eea2eaab57a6a81c49cc58ea82ebd  .tmp_build/combined_hw_emu_link_check/build/grasu_regraph_combined.hw_emu.xclbin
daf8bb44c32295a27827993bdf913eb9d311f27e4d21efbaf46edfc57224995f  .tmp_build/combined_hw_emu_host_compatible/build/grasu_regraph_combined.hw_emu.xclbin
d4296714739acea95a8f6a2f66e113849f089fe8e026fd72e7ee40c9e56f05b0  .tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin
b85d8ca553b6c5aea58ec2d6acd024b73d694455dae16c190c8614767be86862  .tmp_build/pure_pipeline_sw_emu_stage0/build/grasu_regraph_pure_pipeline.sw_emu.xclbin
```

Current interpretation:

- The only current pure-pipeline xclbin is `sw_emu`.
- The current pure-pipeline `hw_emu` and `hw` xclbins are still missing.
- The old `combined_hw_coldinit_250mhz_20260712_112335` hardware xclbin proves
  an earlier same-xclbin GraSU+ReGraph baseline existed, but not the current
  no-D2H PMA-to-stream pure pipeline.
- External Vitis/Vivado builders are active, so the next hardware command should
  use the wait-idle guard already embedded in the launch packet.

The launch packet README wording was also tightened so future packets make clear
that `run_pure_pipeline_target_flow.sh` performs postrun acceptance
automatically after a full target flow. The printed manual
`check_pure_pipeline_acceptance_gates.py --mode postrun` command is now
documented as a recheck/repack command, not as an extra mandatory step after a
normal target-flow run.

## Revalidated Launch Packets After README Cleanup

After committing the launch-packet README clarification as
`9e7c4bb0969f21e4a4113e60f0957c4cf7ee3de1`, the build-relevant source
fingerprint became:

```text
97b17b31658d08ce665b13577c2943e25f258074992a490918fa926096167e49
```

Because `create_pure_pipeline_launch_packet.sh` is part of the reproducibility
source set, the old launch packets were intentionally treated as stale. Fresh
hardware packets and no-build prelaunch evidence were generated:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_9e7c4bb \
  --label hw_emu_after_9e7c4bb_allow_active \
  --allow-active-builders

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_9e7c4bb \
  --label hw_after_9e7c4bb_allow_active \
  --allow-active-builders

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_9e7c4bb_packet_readme \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_9e7c4bb_packet_readme \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

The existing `sw_emu` xclbin was then revalidated without relinking:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target sw_emu \
  --label postrun_after_9e7c4bb_packet_readme \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 180 \
  --timeout 300
```

Postrun result:

```text
acceptance_check_postrun: PASS=11, SKIP=2
summary: results/pure_pipeline_sw_emu_smoke_postrun_after_9e7c4bb_packet_readme/summary.tsv
chain: PASS, mismatches=0, vertices=16, final_edges=15, supersteps=16
hot-source: PASS, mismatches=0, vertices=16, final_edges=28, supersteps=2
spread: PASS, mismatches=0, vertices=16, final_edges=24, supersteps=16
hot-dest: PASS, mismatches=0, vertices=64, final_edges=95, supersteps=16
```

Current report after the refresh:

```text
head=9e7c4bb0969f21e4a4113e60f0957c4cf7ee3de1
source_fingerprint_sha256=97b17b31658d08ce665b13577c2943e25f258074992a490918fa926096167e49
dirty=false

sw_emu xclbin=yes postrun=pass:PASS=11,SKIP=2 flow_current=yes
hw_emu xclbin=no postrun=waiting_xclbin flow_current=yes packet_current=yes
hw xclbin=no postrun=waiting_xclbin flow_current=yes packet_current=yes

next_target=hw_emu
next_action=build
next_commands=.tmp_build/pure_pipeline_launch_packet_hw_emu_after_9e7c4bb_allow_active/launch_command.sh
```

Evidence hashes:

```text
07763905b54fbd4b3d0d46734934b0523d2bd6b3c76f7bc9542dc69df1c33790  scripts/create_pure_pipeline_launch_packet.sh
253a3e68cd0b42ac47fbf2b601faa5fc78e6009b4d6b668ccfe3310bea8d6ac6  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/acceptance_check_postrun_target_flow_postrun_after_9e7c4bb_packet_readme.tsv
a0361669e4c8d7b76752d00da73ecc5153b37fde75efa08eb5a48d8fed3660e3  results/pure_pipeline_sw_emu_smoke_postrun_after_9e7c4bb_packet_readme/summary.tsv
c990777a19ce932eed38f48a1b0984a7f97d0cb079517a4a5af7917f57f1e0f6  results/pure_pipeline_sw_emu_compare_postrun_after_9e7c4bb_packet_readme/comparison.tsv
519c878cb2fffcf41de41d12f3c8bf0ec33832ceefca67e1009b2bec569008e3  results/pure_pipeline_requirement_audit_postrun_after_9e7c4bb_packet_readme/audit.json
bb51b170bf8103183efb4d642fe72084df3e6cd70613f7ed189ecb9eb6639685  results/pure_pipeline_evidence_bundle_postrun_after_9e7c4bb_packet_readme/summary.md
efb81dbb22c02755cf8529038339b736e0456750055721605d6407c777f2e43e  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_9e7c4bb_allow_active/launch_command.sh
0cd0f873d0aaa78819834c67242bb27a6898f99cc4bacbadc5a7790d78c2575e  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_9e7c4bb_allow_active/acceptance_check_prelaunch.tsv
9f5f8724027b818f166ff027db2882c101fc35868e8013d815363e421beda0aa  .tmp_build/pure_pipeline_launch_packet_hw_after_9e7c4bb_allow_active/launch_command.sh
8210650ddf6b8d470d3dea47e0b38e64539279dc9ca776c764929c4fca29855e  .tmp_build/pure_pipeline_launch_packet_hw_after_9e7c4bb_allow_active/acceptance_check_prelaunch.tsv
52f6e1b485ca9e69c9a2d72e7e837f227011d42b9443e0320117e16db3d9684c  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_9e7c4bb_packet_readme.env
86e16823cf510c6d39e96813f8f4270e3d41f1db37168e485ffe6b6b26d90aeb  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_9e7c4bb_packet_readme.env
```

## Pure Xclbin Name Contract Guard, 2026-07-15

To avoid confusing historical `combined` artifacts with the current pure
hardware pipeline, `scripts/check_pure_pipeline_xclbin_contract.py` now checks
the xclbin basename before reading the rest of the metadata contract. A valid
pure-pipeline artifact must be named:

```text
grasu_regraph_pure_pipeline.<target>.xclbin
```

This does not require the artifact to stay in `.tmp_build`; copied release
artifacts can still pass as long as their target-specific basename and metadata
are correct. It does reject old combined artifacts such as
`grasu_regraph_combined.hw.xclbin`.

Code validation:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 -m py_compile scripts/check_pure_pipeline_xclbin_contract.py
git diff --check

./scripts/check_pure_pipeline_xclbin_contract.py \
  --target sw_emu \
  --label name_contract_positive \
  --out-file .tmp_build/pure_pipeline_xclbin_contracts/xclbin_contract_sw_emu_name_contract_positive.tsv

./scripts/check_pure_pipeline_xclbin_contract.py \
  --target hw \
  --xclbin .tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin \
  --info .tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin.info \
  --label combined_negative \
  --out-file .tmp_build/pure_pipeline_xclbin_contracts/xclbin_contract_hw_combined_negative.tsv
```

Expected results:

```text
sw_emu positive: PASS, xclbin_name_contract ok=yes
combined negative: rc=3, failed checks include xclbin_name_contract
```

After committing the guard as `28af0e5b6757c20ac6c5c00ea32cbe3d7790267b`,
the build-relevant source fingerprint became:

```text
e814be495124f11a01417ebabae9d703f30fdb89f93f211629a240edad8310f7
```

Fresh hardware launch packets and no-build prelaunch evidence were regenerated:

```bash
./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw_emu \
  --flow-label after_28af0e5 \
  --label hw_emu_after_28af0e5_allow_active \
  --allow-active-builders

./scripts/create_pure_pipeline_launch_packet.sh \
  --target hw \
  --flow-label after_28af0e5 \
  --label hw_after_28af0e5_allow_active \
  --allow-active-builders

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw_emu \
  --label prelaunch_after_28af0e5_name_contract \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 900

./scripts/run_pure_pipeline_target_flow.sh \
  --target hw \
  --label prelaunch_after_28af0e5_name_contract \
  --prepare \
  --skip-build \
  --skip-finalize \
  --wait-idle 1 \
  --idle-poll 1 \
  --idle-settle 0 \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 300
```

The existing `sw_emu` xclbin was revalidated with the new contract:

```bash
./scripts/run_pure_pipeline_target_flow.sh \
  --target sw_emu \
  --label postrun_after_28af0e5_name_contract \
  --skip-build \
  --gate-case tiny_star_v16_u12 \
  --gate-timeout 180 \
  --timeout 300
```

Postrun result:

```text
acceptance_check_postrun: PASS=11, SKIP=2
xclbin_contract_sw_emu_postrun_after_28af0e5_name_contract.tsv: xclbin_name_contract ok=yes
chain: PASS, mismatches=0, vertices=16, final_edges=15, supersteps=16
hot-source: PASS, mismatches=0, vertices=16, final_edges=28, supersteps=2
spread: PASS, mismatches=0, vertices=16, final_edges=24, supersteps=16
hot-dest: PASS, mismatches=0, vertices=64, final_edges=95, supersteps=16
```

Current status after the refresh:

```text
head=28af0e5b6757c20ac6c5c00ea32cbe3d7790267b
source_fingerprint_sha256=e814be495124f11a01417ebabae9d703f30fdb89f93f211629a240edad8310f7
dirty=false

sw_emu xclbin=yes postrun=pass:PASS=11,SKIP=2 flow_current=yes
hw_emu xclbin=no postrun=waiting_xclbin flow_current=yes packet_current=yes
hw xclbin=no postrun=waiting_xclbin flow_current=yes packet_current=yes

active_builders=related:0 external:2
next_target=hw_emu
next_action=build
next_commands=.tmp_build/pure_pipeline_launch_packet_hw_emu_after_28af0e5_allow_active/launch_command.sh
```

Evidence hashes:

```text
8260420660b004e6ddecb350d2448d3626a34f4d95795dddf89c95e8b675ca73  scripts/check_pure_pipeline_xclbin_contract.py
1cc3d8e5ad44862262cbb1294a3b0b6b0a685bf49aefb132325dad28060adcd3  .tmp_build/pure_pipeline_xclbin_contracts/xclbin_contract_sw_emu_name_contract_positive.tsv
a47b39fdb6a1b4916ab4fb173230fe89c6283a87edcb9a3d5e2ae1f2dd9313dd  .tmp_build/pure_pipeline_xclbin_contracts/xclbin_contract_hw_combined_negative.tsv
1cc3d8e5ad44862262cbb1294a3b0b6b0a685bf49aefb132325dad28060adcd3  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/xclbin_contract_sw_emu_postrun_after_28af0e5_name_contract.tsv
6bd9b4a67a06fa3d896e42d9c634c8be17168cea23ab2163e7b44201db482555  .tmp_build/pure_pipeline_sw_emu_stage0/run_logs/acceptance_check_postrun_target_flow_postrun_after_28af0e5_name_contract.tsv
64376e5c37e53fc937fb9ed2e8e6239931e1f6f6749d523fd2cfa72cbed4bddd  results/pure_pipeline_sw_emu_smoke_postrun_after_28af0e5_name_contract/summary.tsv
3b48e7163716c11b4384f8214368ad7ffb823b255711e71703cd0d5c228c3807  results/pure_pipeline_sw_emu_compare_postrun_after_28af0e5_name_contract/comparison.tsv
3ce5e50aac95abebf76294f702e8fd5c1c1cf0953144d93ab0068fa514731b70  results/pure_pipeline_requirement_audit_postrun_after_28af0e5_name_contract/audit.json
44e79e3851b4fea70143f68eff91aa370650b5be54e9430c93e42de1800f3dbe  results/pure_pipeline_evidence_bundle_postrun_after_28af0e5_name_contract/summary.md
fa9bf3f5760ac20faef0d34540414bb665086e0068f7b963f42fdb49be6281ad  .tmp_build/pure_pipeline_launch_packet_hw_emu_after_28af0e5_allow_active/launch_command.sh
e57e40d17c15b7e55b7db2997e5214aa01cb2be0c6da2c877fd7392e321cf26e  .tmp_build/pure_pipeline_launch_packet_hw_after_28af0e5_allow_active/launch_command.sh
ffd1092c5fce87ac97a14fa44b6f2c9bf70989767b16be69e4c236a694d59e82  .tmp_build/pure_pipeline_hw_emu_stage0/run_logs/target_flow_prelaunch_after_28af0e5_name_contract.env
2123c57b880ffc477f73a0415e4df5a18cc81c601ad758221af6c98bf172d8cd  .tmp_build/pure_pipeline_hw_stage0/run_logs/target_flow_prelaunch_after_28af0e5_name_contract.env
```
