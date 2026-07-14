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
