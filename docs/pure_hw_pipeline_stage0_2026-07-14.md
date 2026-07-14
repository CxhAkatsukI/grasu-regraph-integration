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
