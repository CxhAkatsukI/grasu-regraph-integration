# Pure Pipeline HW Validation

Date: 2026-07-16 Asia/Shanghai

This note records the first successful real-U55C `hw` build and smoke run for
the current GraSU -> completion barrier -> one-shot PMA compactor -> ReGraph
little-GS pipeline.

## Source State

```text
repo: /home/chuxiao/grasu-regraph-integration
branch: codex/pure-hw-pipeline
integration_head: 3fdb3b435049355f2aa5bf32b47f536e1296311a
integration_tracked_dirty: clean
GraSU_head: b79ccb0bc6aae4a2b7dededcee095bf0ad1b67dc
GraSU_tracked_dirty: clean
ReGraph: local non-git source, represented by integration patches
```

External-source patches needed for reproduction:

```text
patches/grasu_direct_process_cache_20260715.diff
patches/regraph_little_only_hbm_wrapper_20260715.diff
```

## Build Evidence

Build command:

```bash
cd /home/chuxiao/grasu-regraph-integration
setsid nohup bash -lc './scripts/run_pure_pipeline_build.sh \
  --target hw \
  --label min32_wait_compactor_after_3fdb3b4 \
  --prepare \
  --clean-build-artifacts; rc=$?; printf "%s\n" "$rc" \
  > .tmp_build/manual_logs/hw_min32_wait_compactor_after_3fdb3b4.rc; exit "$rc"' \
  > .tmp_build/manual_logs/hw_min32_wait_compactor_after_3fdb3b4.nohup.log 2>&1 &
```

Return-code evidence:

```text
.tmp_build/pure_pipeline_hw_stage0/run_logs/compile_min32_wait_compactor_after_3fdb3b4.rc = 0
.tmp_build/pure_pipeline_hw_stage0/run_logs/link_min32_wait_compactor_after_3fdb3b4.rc = 0
.tmp_build/manual_logs/hw_min32_wait_compactor_after_3fdb3b4.rc = 0
```

Generated artifact:

```text
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin
size: 62440635 bytes
created: 2026-07-16 01:34 Asia/Shanghai
sha256: 5a730a2da85ddf522f577ca7d7024f7aa401bb07802f3bf9b4326dfd312e917e
```

Auxiliary artifact hashes:

```text
.tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin.info
sha256: d3a951cea4fdd51e1f42af51dbd377228e1f53693e7c13adfdad856a944bbe69

.tmp_build/pure_pipeline_hw_stage0/run_logs/xclbin_contract_hw_min32_wait_compactor_after_3fdb3b4.tsv
sha256: 2ad21f1d536d7b2c789c0589dc1934ecb35ca42cfaefb6ac544347df6466173a

.tmp_build/source_contracts_hw_min32_wait_compactor_after_3fdb3b4.tsv
sha256: 8608362c108ab127095709e1ea245f06abd1a5c8f9e4893b6f66c7324986de6a
```

The Vitis link log ends with:

```text
Created .../grasu_regraph_pure_pipeline.hw.xclbin
Run completed
Total elapsed time: 2h 25m 47s
```

## Contract Evidence

Source contract:

```bash
./scripts/check_pure_pipeline_source_contracts.py \
  --label hw_min32_wait_compactor_after_3fdb3b4 \
  --out-file .tmp_build/source_contracts_hw_min32_wait_compactor_after_3fdb3b4.tsv
```

Result: 19 required proofs, 0 failures.

Important proved contracts:

```text
single_context_program
completion_token_barrier
grasu_writers_emit_completion_tokens
adapter_receives_actual_pma_buffers
no_host_graph_handoff_between_grasu_and_regraph
stream_burst_8_edge_contract
unit_weight_sssp_packing
timing_fields
```

Xclbin contract:

```bash
./scripts/check_pure_pipeline_xclbin_contract.py \
  --target hw \
  --label min32_wait_compactor_after_3fdb3b4 \
  --out-file .tmp_build/pure_pipeline_hw_stage0/run_logs/xclbin_contract_hw_min32_wait_compactor_after_3fdb3b4.tsv
```

Result: 10 required checks, 0 failures.

The current `hw` xclbin contains the expected topology:

```text
GraSU process_cache/process_ddr
-> pma_completion_barrier
-> pma_to_regraph_edge_array
-> littleKernelScatterGather
-> kernelHBMWrapper/kernelLittleGSMerger/kernelApply
```

It does not use the stale stream adapter, ReGraph big-GS kernels, or the old
`lksg_stream` wrapper from the previous topology.

## Runtime Scope

All runtime data below is from real U55C hardware with the current `hw` xclbin.
Each case was run once. These are engineering smoke results, not final
paper-style statistics with warmup and repeated measurements.

The pipeline test uses one update batch followed by unit-weight SSSP. It does
not implement the GraSU paper's cross-batch overlap between value measurement
and graph computation.

## Tiny Smoke

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
rm -rf results/pure_pipeline_hw_min32_wait_compactor_smoke
unset XCL_EMULATION_MODE
./scripts/run_pure_pipeline_smoke.sh \
  --target hw \
  --manifest workloads/sssp_benchmark_pure_stage0/manifest.tsv \
  --out-dir results/pure_pipeline_hw_min32_wait_compactor_smoke \
  --timeout 600 \
  --case tiny_chain_v16,tiny_star_v16_u12,tiny_spread_v16_u8,tiny_hotdst_v64_u32
```

Summary:

```text
summary: results/pure_pipeline_hw_min32_wait_compactor_smoke/summary.tsv
sha256: 42afd5d10da18205287612320f84ebc0658d8c2c1b4733eb1123e765566afc67
```

| case | family | V | updates | final edges | supersteps | status | mismatches | PMA scan slots once | edge slots/step | GraSU ms | compact ms | ReGraph event E2E ms | wall ms |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tiny_chain_v16 | chain | 16 | 0 | 15 | 16 | PASS | 0 | 240 | 32 | 0.415212 | 0.081483 | 5.898910 | 5.977483 |
| tiny_star_v16_u12 | hot-source | 16 | 12 | 28 | 2 | PASS | 0 | 256 | 32 | 0.467284 | 0.088242 | 1.583896 | 1.673728 |
| tiny_spread_v16_u8 | spread | 16 | 8 | 24 | 16 | PASS | 0 | 256 | 32 | 0.596777 | 0.098803 | 6.207438 | 6.284841 |
| tiny_hotdst_v64_u32 | hot-dest | 64 | 32 | 95 | 16 | PASS | 0 | 1008 | 96 | 0.693710 | 0.137794 | 6.461987 | 6.539459 |

## Small Smoke

Command:

```bash
cd /home/chuxiao/grasu-regraph-integration
rm -rf results/pure_pipeline_hw_min32_wait_compactor_small_smoke
unset XCL_EMULATION_MODE
./scripts/run_pure_pipeline_smoke.sh \
  --target hw \
  --manifest workloads/sssp_benchmark_pure_stage0/manifest.tsv \
  --out-dir results/pure_pipeline_hw_min32_wait_compactor_small_smoke \
  --timeout 1200 \
  --case small_chain_v64,small_star_v4096_u1024,small_spread_v4096_u1024,small_hotdst_v4096_u1024
```

Summary:

```text
summary: results/pure_pipeline_hw_min32_wait_compactor_small_smoke/summary.tsv
sha256: 3c62afd9df5f61f080091027dcd595b2ed2ec2290a53cd87f42ce13a61837ff7
```

| case | family | V | updates | final edges | supersteps | status | mismatches | PMA scan slots once | edge slots/step | GraSU ms | compact ms | ReGraph event E2E ms | wall ms |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| small_chain_v64 | chain | 64 | 0 | 63 | 64 | PASS | 0 | 1008 | 64 | 1.077240 | 0.151584 | 22.153688 | 22.233431 |
| small_star_v4096_u1024 | hot-source | 4096 | 1024 | 5120 | 2 | PASS | 0 | 66560 | 5120 | 1.290257 | 3.598633 | 5.907950 | 5.995503 |
| small_spread_v4096_u1024 | spread | 4096 | 1024 | 5120 | 16 | PASS | 0 | 65536 | 5120 | 0.900716 | 3.618624 | 10.499783 | 10.579595 |
| small_hotdst_v4096_u1024 | hot-dest | 4096 | 1024 | 5119 | 32 | PASS | 0 | 65520 | 5120 | 0.939527 | 3.582783 | 15.327291 | 15.413373 |

## Interpretation

The current `hw` artifact is usable for the next comparison round: it builds,
passes source/xclbin topology checks, reads GraSU's actual PMA on device, and
matches the CPU oracle on chain, hot-source, spread, and hot-destination smoke
cases.

The small `4096`-vertex cases also show the remaining structural cost clearly:
the one-shot compactor scans the PMA capacity once before ReGraph starts. For
these cases the scan is about 65k PMA slots and costs about 3.6 ms. This is far
better than scanning before every ReGraph superstep, but it is still a visible
fixed handoff cost on small graphs.

Next recommended test step: rerun the prior baseline comparison matrix with the
same inputs, then separate the conclusion into update time, one-shot PMA
compaction time, ReGraph SSSP time, and full pipeline E2E time.
