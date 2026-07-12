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

## Combined hw Run

After the combined real `hw` xclbin exists:

```bash
cd /home/chuxiao/grasu-regraph-integration
COMBINED_XCLBIN=/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz/build/grasu_regraph_combined.hw.xclbin \
REGRAPH_HOST=/data/tmp/chuxiao/ReGraph_sssp_hw_coldinit_250mhz_scratch/host_graph_fpga_sssp \
./scripts/run_grasu_regraph_sssp_sweep.sh \
  --preset review \
  --combined-xclbin "${COMBINED_XCLBIN}" \
  --out-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_250mhz
```

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
