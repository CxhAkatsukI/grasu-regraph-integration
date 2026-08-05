# Preliminary matched FPGA evidence (2026-08-05)

## Scope

This evidence is a hardware preflight while the final K4-shared G+R xclbins are
being routed. It uses the already routed one-destination-partition G+R SSSP and
CC xclbins and the current paper-aligned Spine owner-FIFO xclbins. Both systems
run on U55C cards at 150 MHz and consume the exact same generated `.graph` file.

Only rows that pass both FPGA hosts' independent CPU oracles are admitted.
The compared timing window is:

- G+R: `event_e2e_ms`, the union of update and iterative graph-kernel events.
- Spine: `dynamic_kernel_ms`, maintenance kernel plus iterative reader/compute
  kernel spans.

Static graph construction, xclbin programming, result checking, and host-device
buffer migration are outside this kernel-window comparison. Raw setup-inclusive
fields remain in `summary.tsv`, but are not used for speedup because the current
hosts allocate different state capacities for these compact graphs.

## Admitted insertion rows

| Algorithm | Real topology | G+R (ms) | Spine (ms) | G+R / Spine |
| --- | --- | ---: | ---: | ---: |
| Weighted SSSP | Amazon-2008 | 1.834347 | 0.860706 | 2.131x |
| Weighted SSSP | Web-Google | 4.257551 | 1.097540 | 3.879x |
| Weighted SSSP | Flickr | 8.520440 | 3.095040 | 2.753x |
| CC | Amazon-2008 | 7.131877 | 33.986300 | 0.210x |
| CC | Web-Google | 26.367646 | 90.352400 | 0.292x |
| CC | Flickr | 18.782695 | 95.824600 | 0.196x |

Values greater than one favor Spine. The three CC inputs are explicitly
converted to unweighted reciprocal simple graphs because the G+R CC contract
requires reciprocal directed edge pairs. Both architectures consume the same
reciprocal file.

Evidence:

- SSSP: `/data/tmp/chuxiao/matched_fpga_sssp_k1_real_20260805/summary.tsv`
- CC: `/data/tmp/chuxiao/matched_fpga_cc_k1_real_reciprocal_v2_20260805/summary.tsv`
- converted workloads:
  `/data/tmp/chuxiao/matched_fpga_real_workloads_20260805`

## Correctness-rejected rows

The SSSP delete and weight-change rows are not performance evidence. G+R passed
all six, but current Spine hardware did not resolve old positive records and new
negative records across different LSM levels before map execution. Insertions of
new endpoints do not exercise this missing cross-level differential resolution.
The matrix driver rejected all six rows and left their speedup cells empty.

This is a Spine HLS functional gap requiring a new routed xclbin; relaxing the
oracle or only removing the processed-edge assertion would not fix it.

## Reproduction

The matrix and conversion tools are:

```bash
python3 scripts/convert_spine_slices_to_pma_graph.py --help
scripts/run_matched_fpga_matrix.sh --help
```

The final comparison must rerun these same admitted workloads with the final
K4-shared SSSP/CC xclbins and add Full PageRank and thresholded residual
PageRank. These preliminary numbers must not be presented as final K4 results.
