# Matched K4-shared FPGA evidence (2026-08-06)

## Scope

This packet compares the routed conversion-free K4-shared GraSU + ReGraph
design with the current paper-aligned Spine owner-FIFO design on two U55C
cards. Both systems run at a nominal 150 MHz and consume the exact same graph,
batch of eight insertions, source/algorithm parameters, and independent CPU
oracle. A row is admitted only when both FPGA hosts report zero mismatches.

K4-shared contains four GraSU PMA/update lanes and one shared ReGraph worker.
The ReGraph worker is reused serially across at most four destination
partitions; these results are neither K4-ideal nor four replicated ReGraph
pipelines. The PMA-to-ReGraph handoff is an AXIS stream and does not materialize
an intermediate edge array.

The compared timing window is:

- G+R: `event_e2e_ms`, the union of update, correction, and iterative graph
  kernel OpenCL events;
- Spine: `dynamic_kernel_ms`, the maintenance kernel plus iterative
  reader/compute kernel spans.

Static graph construction, xclbin programming, result checking, and host-device
buffer migration are outside this kernel-window comparison. Raw
setup-inclusive fields remain in every `summary.tsv` and are not substituted
for these matched device windows.

## Three-repeat medians

| Algorithm | Real topology | G+R (ms) | Spine (ms) | G+R / Spine | Winner |
| --- | --- | ---: | ---: | ---: | --- |
| Weighted SSSP | Amazon-2008 | 2.103651 | 0.963368 | 2.159x | Spine |
| Weighted SSSP | Web-Google | 4.605314 | 1.130000 | 4.099x | Spine |
| Weighted SSSP | Flickr | 9.388083 | 3.104750 | 3.039x | Spine |
| Connected Components | Amazon-2008 | 8.794465 | 32.880300 | 0.267x | G+R |
| Connected Components | Web-Google | 28.415503 | 90.248000 | 0.315x | G+R |
| Connected Components | Flickr | 20.907257 | 94.486500 | 0.221x | G+R |
| Full PageRank | Amazon-2008 | 4.078030 | 18.036700 | 0.220x | G+R |
| Full PageRank | Web-Google | 11.246700 | 58.932200 | 0.190x | G+R |
| Full PageRank | Flickr | 10.015800 | 50.566300 | 0.198x | G+R |
| Residual PageRank | Amazon-2008 | 3.015640 | 1.746040 | 1.727x | Spine |
| Residual PageRank | Web-Google | 7.796740 | 4.341330 | 1.796x | Spine |
| Residual PageRank | Flickr | 6.900140 | 6.445720 | 1.066x | Spine |

Values greater than one favor Spine. These compact real-topology workloads fit
one destination partition during the timed run; the routed xclbins separately
pass a 65,537-vertex, two-partition boundary workload. That boundary run is a
correctness/topology gate, not a performance row.

The CC inputs are reciprocal, unweighted simple graphs because that is the
G+R CC contract; Spine consumes the exact same converted files.

The weighted SSSP result supports a 2.16--4.10x Spine advantage in this measured
domain. The equally important negative evidence is that G+R is 3.18--4.52x
faster for CC and 4.54--5.27x faster for Full PageRank. No projected or failed
row enters these ranges.
Spine also leads Residual PageRank by 1.07--1.80x. The Flickr result is a narrow
advantage: its three observed speedups span 1.053--1.072x. Amazon has a wider
1.403--1.748x range because Spine's three device-window samples have 11.03%
coefficient of variation. The raw repeats are retained so this variance is not
hidden by the median.

## Repetition and evidence files

The three-run aggregate is generated from the raw summaries with:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 scripts/aggregate_matched_fpga_repeats.py \
  --summary /data/tmp/chuxiao/matched_fpga_sssp_k4_real_20260805/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_sssp_k4_real_20260805_repeat2/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_sssp_k4_real_20260805_repeat3/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_cc_k4_real_20260805/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_cc_k4_real_20260805_repeat2/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_cc_k4_real_20260805_repeat3/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_fullpr_k4_real_20260805/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_fullpr_k4_real_20260805_repeat2/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_fullpr_k4_real_20260805_repeat3/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_respr_k4_real_20260805/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_respr_k4_real_20260805_repeat2/summary.tsv \
  --summary /data/tmp/chuxiao/matched_fpga_respr_k4_real_20260805_repeat3/summary.tsv \
  --output /data/tmp/chuxiao/matched_fpga_four_algorithm_k4_repeat_aggregate_20260806.tsv
```

The generated aggregate records each system's coefficient of variation and the
minimum/maximum speedup across repeats. Routed build packets and report
digests are documented in `docs/k4_shared_partition_hls_20260805.md`. The
aggregate and all twelve input summaries are tracked under
`docs/evidence/matched_fpga_k4_20260806/`.

## Evidence boundary

This packet establishes correctness-gated, matched-window FPGA behavior for
the frozen compact insertion matrix. It does not claim that compact one-
partition timing predicts multi-partition throughput, deletion/weight-change
behavior, or graphs beyond the implemented capacity. The current Spine xclbin
also has a known cross-level differential-resolution gap for SSSP deletion and
weight change; those rows remain rejected rather than being reported as
performance evidence.
