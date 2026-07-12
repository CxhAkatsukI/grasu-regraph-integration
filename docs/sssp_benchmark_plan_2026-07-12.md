# SSSP Benchmark Plan, 2026-07-12

This note records the next performance-comparison harness for:

```text
Spine update + SSSP
vs
GraSU update + ReGraph weighted SSSP
```

The scripts added here do not claim final performance yet. They make the test
matrix reproducible so we can run it immediately after cold-start ReGraph `hw`
and combined GraSU+ReGraph `hw` are available.

## Workload Intent

The first fair cross-system comparison should use unit-weight edges. ReGraph is
using the weighted SSSP path, but every edge gets weight 1 so that the result is
comparable with Spine's current SSSP semantics.

The current presets cover:

```text
chain       high diameter; stresses per-superstep overhead and many SSSP levels
hot-source  low diameter source fanout; stresses edge throughput and broad frontier
spread      updates spread across vertices; stresses balanced partition traffic
hot-dest    many sources targeting one destination; stresses gather/min hot spot
```

Preset sizes:

```text
smoke     tiny correctness gate before trusting a new xclbin
review    small/medium timing matrix for Spine vs GraSU+ReGraph comparison
capacity  larger GraSU+ReGraph-only probes for maximum supported size and
          large-graph behavior after smoke/review pass
```

Why this matters:

```text
Small/high-diameter graphs should expose fixed overhead.
Large/low-diameter fanout should favor high edge throughput.
Hot destinations should reveal reduction and partition pressure.
Spread updates should be the balanced baseline.
```

## Scripts

```text
scripts/generate_sssp_benchmark_workloads.py
scripts/run_grasu_regraph_sssp_sweep.sh
scripts/summarize_sssp_chain_result.py
scripts/finalize_combined_hw_build.sh
scripts/run_spine_builtin_sweep.sh
scripts/summarize_spine_builtin_result.py
```

The generator writes, per case:

```text
<case>.graph          GraSU graph/update input
<case>.result         expected final edge set for GraSU checker
<case>.sssp.edges     three-column ReGraph SSSP input: src dst weight
<case>.expected.tsv   expected distance after the configured supersteps
<case>.json           scenario metadata
manifest.tsv          all paths and run parameters
```

The sweep script runs:

```text
GraSU update/check -> result-to-weighted-edge conversion -> ReGraph SSSP
```

Important caveat: the current GraSU host validates against the expected result
file but does not export the final graph. Therefore the chain converts the same
expected final-result file that GraSU just checked. This is the same limitation
as the earlier PR chain and should be disclosed in experimental notes.

## Smoke Generation

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/generate_sssp_benchmark_workloads.py \
  --preset smoke \
  --out-root /home/chuxiao/grasu-regraph-integration/workloads/sssp_benchmark_smoke
```

## Dry-run The Chain

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset smoke \
  --dry-run \
  --out-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_dryrun
```

## Real Cold-start ReGraph hw Run

After the cold-start ReGraph 250 MHz `hw` build exists:

```bash
cd /home/chuxiao/grasu-regraph-integration
REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
REGRAPH_XCLBIN=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/xclbin_hw_sssp/graph_fpga.hw.xilinx_u55c_gen3x16_xdma_3_202210_1.xclbin \
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset review \
  --out-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_coldinit_hw_250mhz
```

Standalone smoke run completed on real U55C hardware:

```text
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_smoke_standalone_hw_20260712_113110
```

This run uses separate standalone xclbins: GraSU first, then ReGraph weighted
SSSP on the checked/converted final edge set. It is a current two-stage
baseline, not the final unified-xclbin measurement.

```text
case                 status  grasu_ms  regraph_e2e_ms  processed_edges  graph_edges  mismatch_count
tiny_chain_v16       PASS    1.831960  4.52812         16               15           0
tiny_star_v16_u12    PASS    1.624356  0.948191        32               28           0
tiny_hotdst_v64_u32  PASS    1.632106  4.37758         96               95           0
```

Key evidence in each case log:

```text
GraSU:  check result passed
ReGraph: Device[0]: program successful!
ReGraph: Processed edges ...; mismatch_count=0
```

## Combined hw Run

After the combined real `hw` xclbin exists:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/finalize_combined_hw_build.sh \
  --target hw \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335 \
  --session combined_hw_coldinit_250mhz_20260712_112335 \
  --preset smoke
```

This one command checks the final combined xclbin, records its hash, collects
combined-vs-standalone resource evidence, and runs the GraSU->ReGraph SSSP
smoke sweep with both hosts loading the same combined xclbin. It exits before
running anything if the xclbin is still missing.

For the full review sweep after smoke passes:

```bash
cd /home/chuxiao/grasu-regraph-integration
COMBINED_XCLBIN=/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz/build/grasu_regraph_combined.hw.xclbin \
REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset review \
  --combined-xclbin "${COMBINED_XCLBIN}" \
  --out-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_250mhz
```

For larger GraSU+ReGraph capacity probes after the review sweep is stable:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/finalize_combined_hw_build.sh \
  --target hw \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335 \
  --session combined_hw_coldinit_250mhz_20260712_112335 \
  --preset capacity \
  --skip-evidence
```

The `capacity` preset is intended to answer architecture questions such as:
how much vertex/edge state the chain can carry, whether low-diameter fanout is
faster than balanced spread traffic, and how expensive hot-destination gather
pressure is on larger inputs.

For combined-hardware claims, both hosts must load the same combined xclbin.
Using only `REGRAPH_XCLBIN=<combined>` while leaving `GRASU_XCLBIN` at its
default would measure a mixed setup instead of the unified hardware binary.

Expected summary:

```text
summary.tsv
```

Key columns:

```text
grasu_ms
grasu_mups
regraph_e2e_ms
regraph_mteps
processed_edges
graph_edges
mismatch_count
```

Use `grasu_ms + regraph_e2e_ms` as the current two-stage total. This is not a
single scheduled hardware dataflow measurement; it is the current host-level
composition and remains useful because it isolates whether ReGraph SSSP compute
dominates or whether GraSU update time dominates.

## Spine Side

The current Spine host has built-in scenarios rather than the same external
graph-file interface. The reusable runner is:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_spine_builtin_sweep.sh \
  --preset review \
  --out-root /home/chuxiao/grasu-regraph-integration/results/spine_builtin_review_hw
```

Smoke baseline completed on real hardware:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_builtin_smoke_hw_20260712_121740
```

Artifacts:

```text
host sha256:   b1e88bc593da7e598452d7676bcc3e7f0cf0c0c9fb192049912364e30a888349
xclbin sha256: 69145517738cc1ffff95e91c24393260c346ac683db9eef2989bbc1bdb7a3469
```

Smoke summary:

```text
fanout_1024_s64  PASS  maint_ms=27.4725  conv_ms=128.139  kernel_e2e_ms=155.611  errors=0
hot_cold         PASS  maint_ms=0.424933 conv_ms=9.57297                    errors=0
star_1024        PASS  maint_ms=27.4768  conv_ms=125.289  kernel_e2e_ms=152.766  errors=0
```

Parser note: `PARTITIONED_CSR_E2E_BATCH` is an intermediate line and does not
carry final `PASS/FAIL`; the summarizer now prefers the later
`PARTITIONED_CSR_E2E_SMOKE PASS ...` line when present.

Review baseline completed on real hardware:

```text
/home/chuxiao/grasu-regraph-integration/results/spine_builtin_review_hw_20260712_121941
```

All 10 review scenarios passed:

```text
hot_cold                    PASS  maint_ms=0.410352  conv_ms=9.59798
star_4096                  PASS  maint_ms=108.733   conv_ms=125.367  kernel_e2e_ms=234.1
star_65536                 PASS  maint_ms=1733.54   conv_ms=132.365  kernel_e2e_ms=1865.91
fanout_4096_s64            PASS  maint_ms=108.745   conv_ms=133.188  kernel_e2e_ms=241.932
fanout_65536_s256          PASS  maint_ms=1733.88   conv_ms=178.6    kernel_e2e_ms=1912.48
repeat_star_4096_b4        PASS  maint_ms=443.525   conv_ms=126.64   kernel_e2e_ms=570.165
repeat_fanout_4096_b4_s64  PASS  maint_ms=902.566   conv_ms=162.568  kernel_e2e_ms=1065.13
duplicate_heavy_4096       PASS  maint_ms=108.704   conv_ms=125.487  kernel_e2e_ms=234.19
carry_l1                   PASS  maint_ms=0.466734  conv_ms=9.5169   kernel_e2e_ms=9.98364
carry_l3                   PASS  maint_ms=1.85856   conv_ms=25.9946  kernel_e2e_ms=27.8531
```

Use this summary for the first Spine-vs-chain join unless a newer Spine review
run is explicitly recorded.

Dry-run without touching the board:

```bash
./scripts/run_spine_builtin_sweep.sh \
  --preset smoke \
  --dry-run \
  --out-root /home/chuxiao/grasu-regraph-integration/results/spine_builtin_dryrun
```

Current useful direct commands are:

```bash
SPINE_PARTITIONED_SPLIT=1 \
/home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke \
  /data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
  --hot-cold \
  --timeout 120

SPINE_PARTITIONED_SPLIT=1 \
/home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke \
  /data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
  --star 4096 \
  --timeout 120

SPINE_PARTITIONED_SPLIT=1 \
/home/feiyang/dev_space/spine-dynamic-graph/tests/test_integration/host_partitioned_csr_e2e_smoke \
  /data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
  --fanout 4096 64 \
  --timeout 120
```

For the final paper-style comparison, we should either:

```text
1. add an external workload loader to the Spine host, or
2. map each GraSU+ReGraph generated case to the closest existing Spine built-in
   scenario and clearly state that the comparison is scenario-level, not
   identical-input.
```

The Spine runner currently follows option 2. It records the original host args
and the emitted `PARTITIONED_CSR_E2E_*` line for every case so the limitation is
visible in the evidence.

## Cross Summary Join

The comparison joiner is:

```text
scripts/compare_spine_chain_summaries.py
scripts/run_combined_review_compare.sh
```

The lower-level joiner does not run hardware. It reads the two `summary.tsv`
files and writes:

```text
comparison.tsv
comparison.md
```

Important derived columns:

```text
chain_total_ms = grasu_ms + regraph_e2e_ms
spine_maint_conv_ms = maint_ms + conv_ms
chain_over_spine_kernel = chain_total_ms / spine_kernel_e2e_ms
chain_over_spine_maint_conv = chain_total_ms / spine_maint_conv_ms
```

Use explicit pairs so the scenario-level nature of the comparison is visible:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_combined_review_compare.sh \
  --target hw \
  --build-root /home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335 \
  --session combined_hw_coldinit_250mhz_20260712_112335 \
  --spine-summary /home/chuxiao/grasu-regraph-integration/results/spine_builtin_review_hw_20260712_121941/summary.tsv
```

The wrapper runs the combined GraSU+ReGraph review sweep, then calls the
lower-level joiner with the fixed scenario pairs. To join an already completed
chain summary manually:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/compare_spine_chain_summaries.py \
  --chain-summary /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_250mhz/summary.tsv \
  --spine-summary /home/chuxiao/grasu-regraph-integration/results/spine_builtin_review_hw_20260712_121941/summary.tsv \
  --pair small_chain_v64=carry_l1:small_high_diameter \
  --pair small_star_v4096_u1024=star_4096:small_hot_source \
  --pair small_spread_v4096_u1024=fanout_4096_s64:small_spread_fanout \
  --pair small_hotdst_v4096_u1024=duplicate_heavy_4096:small_hot_destination \
  --pair medium_star_v65536_u8192=star_65536:medium_hot_source \
  --pair medium_spread_v65536_u16384=fanout_65536_s256:medium_spread_fanout \
  --out-dir /home/chuxiao/grasu-regraph-integration/results/spine_vs_grasu_regraph_review_combined_hw_250mhz
```

Dry-run format check completed without touching hardware:

```text
/home/chuxiao/grasu-regraph-integration/results/compare_spine_chain_drycheck_20260712_114640
```

That dry-check only validates parsing/output shape; the Spine side was a
`DRY_RUN`, so it is not performance evidence.
