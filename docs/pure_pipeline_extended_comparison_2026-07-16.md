# Pure Pipeline Extended Fixed-Step Comparison

Date: 2026-07-16 Asia/Shanghai

This note compares the previous GraSU + ReGraph fixed-step reference table
against the current real-U55C pure hardware pipeline.

Baseline meaning:

```text
old Stage sum ms = old GraSU kernel ms + old ReGraph E2E ms
old handoff model = zero-cost host-side expected-final-edge handoff
```

Current pure-hw meaning:

```text
GraSU actual PMA
-> completion barrier
-> one-shot PMA compactor
-> ReGraph little-GS SSSP

pure hw E2E ms = event_union_ms(all GraSU/barrier/compactor/ReGraph events)
```

Each current result below is a single real-U55C run, not a repeated performance
sweep.

## Evidence

Source/artifact state:

```text
repo: /home/chuxiao/grasu-regraph-integration
branch: codex/pure-hw-pipeline
head used by first extended run: b990100942032643a3f504ab6661e243aaabfb16
xclbin: .tmp_build/pure_pipeline_hw_stage0/build/grasu_regraph_pure_pipeline.hw.xclbin
xclbin sha256: 5a730a2da85ddf522f577ca7d7024f7aa401bb07802f3bf9b4326dfd312e917e
host sha256: 0189b94f16af5ea4e9a5803f963db6558229be76447187862737aadf5a9ad9cb
```

Supported-case run:

```bash
cd /home/chuxiao/grasu-regraph-integration
rm -rf results/pure_pipeline_hw_min32_wait_compactor_extended_fixed_steps
unset XCL_EMULATION_MODE
./scripts/run_pure_pipeline_smoke.sh \
  --target hw \
  --manifest workloads/sssp_benchmark_pure_stage0/manifest.tsv \
  --out-dir results/pure_pipeline_hw_min32_wait_compactor_extended_fixed_steps \
  --timeout 1800 \
  --case small_chain_v64,small_star_v4096_u1024,small_spread_v4096_u1024,small_hotdst_v4096_u1024,medium_star_v65536_u8192,medium_spread_v65536_u16384,large_star_v1048576_u65536,large_spread_v262144_u65536,large_hotdst_v262144_u65536,large_chain_v4096 \
  --case-timeout large_chain_v4096=3600 \
  --case-timeout large_star_v1048576_u65536=3600 \
  --case-timeout large_spread_v262144_u65536=3600 \
  --case-timeout large_hotdst_v262144_u65536=3600
```

The selected manifest only contains 7 of the requested 10 cases. All 7 passed.

```text
summary: results/pure_pipeline_hw_min32_wait_compactor_extended_fixed_steps/summary.tsv
summary sha256: 3e259a86a1e6786e2c5a66eea953f92ea21c80920a2e36c41ee28adb7ff1768e
run.env sha256: 842457f8553d274240f1b8c5735a39e0ce88b9c132655056d90f179332e79f5e
```

Unsupported large-case check:

```bash
cd /home/chuxiao/grasu-regraph-integration
rm -rf results/pure_pipeline_hw_min32_wait_compactor_capacity_fixed_steps
unset XCL_EMULATION_MODE
./scripts/run_pure_pipeline_smoke.sh \
  --target hw \
  --manifest workloads/sssp_benchmark_capacity/manifest.tsv \
  --out-dir results/pure_pipeline_hw_min32_wait_compactor_capacity_fixed_steps \
  --timeout 3600 \
  --case large_star_v1048576_u65536,large_spread_v262144_u65536,large_hotdst_v262144_u65536
```

These three cases fail before launching kernels because the current first-stage
host path explicitly enforces `1 <= V <= 65536`:

```text
tools/pure_pipeline_host.cpp:149-150
ERROR: first-stage pure pipeline requires 1 <= V <= 65536

summary: results/pure_pipeline_hw_min32_wait_compactor_capacity_fixed_steps/summary.tsv
summary sha256: a3c26c89e4f869f7979eca5c45033a3bdf61d1b53559c4d01bd43ad6c09de5fd
run.env sha256: 0fcf3ce8fd43d888f04ef732077107c773e176aa4a5d7d8805470da44b30c4a0
```

## Total E2E Comparison

`pure hw E2E ms` is the measured unified pure-pipeline event time. It includes
the real one-shot PMA compaction cost. Therefore this is stricter than the old
zero-cost handoff baseline.

| Case | old Stage sum ms | pure hw E2E ms | delta ms | ratio | compact ms | status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| small_chain_v64 | 17.439 | 21.692 | +4.253 | 1.24x | 0.161 | PASS |
| small_star_v4096_u1024 | 3.230 | 6.054 | +2.824 | 1.87x | 3.587 | PASS |
| small_spread_v4096_u1024 | 6.013 | 10.174 | +4.161 | 1.69x | 3.506 | PASS |
| small_hotdst_v4096_u1024 | 9.882 | 15.207 | +5.325 | 1.54x | 3.539 | PASS |
| medium_star_v65536_u8192 | 9.924 | 66.572 | +56.648 | 6.71x | 55.393 | PASS |
| medium_spread_v65536_u16384 | 15.286 | 76.071 | +60.785 | 4.98x | 54.925 | PASS |
| large_star_v1048576_u65536 | 84.417 | N/A | N/A | N/A | N/A | unsupported V=1048576 |
| large_spread_v262144_u65536 | 53.345 | N/A | N/A | N/A | N/A | unsupported V=262144 |
| large_hotdst_v262144_u65536 | 97.695 | N/A | N/A | N/A | N/A | unsupported V=262144 |
| large_chain_v4096 | 1092.990 | 1432.893 | +339.903 | 1.31x | 3.620 | PASS |

## ReGraph Component Comparison

This isolates the ReGraph-side compute component using current `hbm_ms` and the
old `ReGraph ms`. It is not the total pipeline time.

| Case | old ReGraph ms | pure hbm_ms | old MTEPS | pure ReGraph MTEPS |
| --- | ---: | ---: | ---: | ---: |
| small_chain_v64 | 15.909 | 17.413 | 0.25 | 0.23 |
| small_star_v4096_u1024 | 0.971 | 0.795 | 10.55 | 12.88 |
| small_spread_v4096_u1024 | 4.362 | 4.592 | 18.78 | 17.84 |
| small_hotdst_v4096_u1024 | 8.049 | 8.985 | 20.35 | 18.23 |
| medium_star_v65536_u8192 | 1.053 | 1.330 | 139.97 | 110.90 |
| medium_spread_v65536_u16384 | 10.769 | 11.834 | 243.42 | 221.51 |
| large_star_v1048576_u65536 | 8.176 | N/A | 272.54 | N/A |
| large_spread_v262144_u65536 | 41.139 | N/A | 254.88 | N/A |
| large_hotdst_v262144_u65536 | 85.551 | N/A | 245.13 | N/A |
| large_chain_v4096 | 1091.320 | 1175.983 | 15.37 | 14.26 |

## Current Conclusion

For the 7 supported cases, correctness is good: all passed with
`mismatches=0`. Performance is not yet better than the previous zero-cost
handoff reference. The main reason is not the ReGraph SSSP compute itself; it
is the current handoff implementation.

The one-shot compactor scans PMA capacity, not only live final edges:

```text
small 4096-vertex cases: about 65k PMA slots scanned, about 3.5 ms
medium 65536-vertex cases: about 1.05M PMA slots scanned, about 55 ms
```

This explains why medium-star and medium-spread become much slower than the
old baseline even though their ReGraph compute component remains around the
same order of magnitude.

The next optimization target is therefore clear: replace capacity-wide PMA
scanning with a sparse/change-aware handoff path, or make GraSU emit a compact
edge/update stream while maintaining PMA, so ReGraph does not pay the full PMA
capacity scan before every batch.

The three larger table entries cannot be claimed for the current first-stage
pipeline because they exceed the explicit `V <= 65536` bound. Supporting them
requires lifting the single-partition/little-GS host path limit before rerunning
the same comparison.
