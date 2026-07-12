# Spine vs GraSU+ReGraph Conclusions

Date: 2026-07-12

## Scope

This note consolidates the current real-hw evidence for the horizontal
comparison:

- Spine split-CU, same exported edge files where the input fits Spine's current
  partitioned level layout.
- GraSU + ReGraph combined real-hw xclbin, with ReGraph weighted SSSP full
  verification.
- Capacity stress cases, separated from normal timing cases by the offline
  Spine capacity classifier.

## Core Artifacts

Combined GraSU+ReGraph hw xclbin:

```text
/home/chuxiao/grasu-regraph-integration/.tmp_build/combined_hw_coldinit_250mhz_20260712_112335/build/grasu_regraph_combined.hw.xclbin
sha256 d4296714739acea95a8f6a2f66e113849f089fe8e026fd72e7ee40c9e56f05b0
```

Resource evidence:

```text
/home/chuxiao/grasu-regraph-integration/results/resource_evidence_20260712_195442_combined_hw_user_check
```

Important resource-review result:

```text
kernel CU count same-kernel changes: 0
connectivity binding same-endpoint changes: 0
hls_top_area same-component changes: 0
```

Timing closure note:

```text
Requested kernel frequency: 250 MHz
Post-route WNS: -0.101 ns
Observed Vitis auto-scaling: about 243.8 MHz
```

## Valid Same-Edge Performance Cases

Inputs:

```text
GraSU+ReGraph summary:
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_20260712_195628/summary.tsv

Spine split-CU summary:
/home/chuxiao/grasu-regraph-integration/results/spine_split_edge_file_review_hw_20260712_201541/summary.tsv

Spine capacity classifier:
/home/chuxiao/grasu-regraph-integration/results/spine_capacity_analysis_20260712_212808/review_combined_capacity.tsv
```

All six review inputs classify as `FITS`, so these are valid timing comparisons
for the current Spine layout.

`GraSU+ReGraph total ms = grasu_ms + regraph_e2e_ms`.
`Spine ms = kernel_e2e_ms`.

| case | capacity | GraSU+ReGraph ms | Spine split ms | winner | ratio |
| --- | --- | ---: | ---: | --- | ---: |
| small_chain_v64 | FITS | 17.4392 | 2.17218 | Spine | 8.03x faster |
| small_star_v4096_u1024 | FITS | 3.23011 | 64.8235 | GraSU+ReGraph | 20.1x faster |
| small_spread_v4096_u1024 | FITS | 6.01264 | 65.358 | GraSU+ReGraph | 10.9x faster |
| small_hotdst_v4096_u1024 | FITS | 9.88242 | 65.1231 | GraSU+ReGraph | 6.59x faster |
| medium_star_v65536_u8192 | FITS | 9.92411 | 997.137 | GraSU+ReGraph | 100.5x faster |
| medium_spread_v65536_u16384 | FITS | 15.2861 | 1023 | GraSU+ReGraph | 66.9x faster |

Interpretation:

```text
Spine is very strong on a tiny high-diameter chain, where the graph update is
small and ReGraph must still perform many SSSP supersteps.

GraSU+ReGraph is much stronger on low-diameter star/spread/hot-destination
cases, especially as the graph grows. The ReGraph SSSP stage reaches high
throughput on these cases, and GraSU's update stage stays comparatively small.
```

## Large Capacity Cases

Inputs:

```text
GraSU+ReGraph full-verification capacity summary:
/home/chuxiao/grasu-regraph-integration/results/grasu_regraph_capacity_verifyfix_hw_20260712_205303/summary.tsv

Spine capacity classification:
/home/chuxiao/grasu-regraph-integration/results/spine_capacity_analysis_20260712_212808/large_capacity_verifyfix_capacity.tsv
```

| case | GraSU+ReGraph status | GraSU+ReGraph total ms | ReGraph MTEPS | Spine capacity | conclusion |
| --- | --- | ---: | ---: | --- | --- |
| large_chain_v4096 | PASS | 1092.99 | 15.3695 | FITS | GraSU+ReGraph is slow because the graph requires 4096 SSSP supersteps; Spine is a better fit for this structure. |
| large_star_v1048576_u65536 | PASS | 84.4166 | 272.539 | UNSUPPORTED_CAPACITY | GraSU+ReGraph handles and verifies the graph; current Spine layout cannot store it after carry under this vertex placement. |
| large_spread_v262144_u65536 | PASS | 53.3452 | 254.884 | UNSUPPORTED_CAPACITY | GraSU+ReGraph handles and verifies the graph; current Spine layout hits L1 per-partition capacity. |
| large_hotdst_v262144_u65536 | PASS | 97.6952 | 245.134 | UNSUPPORTED_CAPACITY | GraSU+ReGraph handles and verifies the graph; current Spine layout hits L1 per-partition capacity. |

The Spine classifier details for the three unsupported large cases are:

```text
failure_level=1
failure_partition=0
failure_partition_edges=262144
failure_partition_capacity=16384
failure_reason=level_partition_capacity
```

This is not just a performance loss. It is a current storage-layout limitation
for concentrated destination-partition inputs.

## Reproduction Commands

Regenerate the valid-review capacity classification:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/analyze_spine_edge_capacity.py \
  --chain-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_20260712_195628 \
  --out /home/chuxiao/grasu-regraph-integration/results/spine_capacity_analysis_20260712_212808/review_combined_capacity.tsv
```

Regenerate the large-capacity classification:

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/analyze_spine_edge_capacity.py \
  --chain-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_capacity_verifyfix_hw_20260712_205303 \
  --out /home/chuxiao/grasu-regraph-integration/results/spine_capacity_analysis_20260712_212808/large_capacity_verifyfix_capacity.tsv
```

Re-run the split Spine same-edge review sweep:

```bash
cd /home/chuxiao/grasu-regraph-integration
SPINE_HOST=/home/chuxiao/grasu-regraph-integration/.tmp_build/spine_split_edge_host_chunked_repro_20260712_202403/host_partitioned_csr_e2e_smoke_edge \
SPINE_XCLBIN=/data/feiyang/spine-dynamic-graph-builds/split_e2e_hw_150_depth32_bram_20260711_2100/xclbin/spine_partitioned_split_e2e.hw.xclbin \
SPINE_PARTITIONED_SPLIT_VALUE=1 \
OUT_ROOT=/home/chuxiao/grasu-regraph-integration/results/spine_split_edge_file_review_hw_20260712_201541 \
./scripts/run_spine_edge_file_sweep.sh \
  --chain-root /home/chuxiao/grasu-regraph-integration/results/grasu_regraph_sssp_review_combined_hw_20260712_195628 \
  --timeout 300
```

## Current Optimization Direction

For GraSU+ReGraph:

```text
The main optimization target is high-diameter graphs. ReGraph's repeated
superstep structure makes chains slow even when each step is small.
```

For Spine:

```text
The main optimization target is the partitioned level layout. To compete on
large star/spread/hot-destination graphs, Spine needs a way to avoid a single
destination partition becoming the capacity bottleneck during carry.
```

## Short Answer For Progress Sync

```text
We have a real-hw combined GraSU+ReGraph system with weighted SSSP verification
passing, resource/CU/connectivity evidence recorded, and same-edge Spine
comparison on all valid small/medium review cases. GraSU+ReGraph wins strongly
on low-diameter star/spread/hot-destination graphs; Spine wins on tiny
high-diameter chain. Large low-diameter graphs reveal a real Spine layout
capacity limitation, not merely a software crash or timeout.
```

