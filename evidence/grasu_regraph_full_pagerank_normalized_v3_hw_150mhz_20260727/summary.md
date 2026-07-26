# grasu_regraph_full_pagerank_normalized_v3_hw_150mhz Vitis Evidence

- build_root: `/data/tmp/chuxiao/grasu_regraph_full_pagerank_normalized_v3_hw_retry6_7b922ee_d5c707c_150mhz_20260727`
- link_summaries: 1
- system_estimates: 1
- xclbins: 1
- selected_kernel_util: `/data/tmp/chuxiao/grasu_regraph_full_pagerank_normalized_v3_hw_retry6_7b922ee_d5c707c_150mhz_20260727/reports/link/link/imp/impl_1_kernel_util_routed.rpt`
- selected_slr_util: `/data/tmp/chuxiao/grasu_regraph_full_pagerank_normalized_v3_hw_retry6_7b922ee_d5c707c_150mhz_20260727/reports/link/link/imp/impl_1_slr_util_routed.rpt`
- selected_timing: `/data/tmp/chuxiao/grasu_regraph_full_pagerank_normalized_v3_hw_retry6_7b922ee_d5c707c_150mhz_20260727/build/link/link/vivado/vpl/prj/prj.runs/impl_1/dr_timing_summary.rpt`

## Selected Kernel Utilization Used Resources

| LUT | LUTAsMem | REG | BRAM | URAM | DSP |
| --- | -------- | --- | ---- | ---- | --- |
| 178374 | 15042 | 177836 | 278 | 64 | 304 |

## Timing

| WNS(ns) | TNS(ns) | WHS(ns) | THS(ns) |
| ------- | ------- | ------- | ------- |
| -0.130 | -15.019 | 0.009 | 0.000 |

## HLS Top-Module Area

| Kernel | Compute Unit | FF | LUT | BRAM | URAM | DSP |
| ------ | ------------ | -- | --- | ---- | ---- | --- |
| bin_search | bin_search_1 | 3286 | 4937 | 4 | 0 | 0 |
| bin_search | bin_search_2 | 3286 | 4937 | 4 | 0 | 0 |
| bin_search | bin_search_3 | 3286 | 4937 | 4 | 0 | 0 |
| bin_search | bin_search_4 | 3286 | 4937 | 4 | 0 | 0 |
| dispatch_degree | dispatch_degree_1 | 304 | 960 | 0 | 0 | 0 |
| process_cache | process_cache_1 | 6935 | 15366 | 30 | 0 | 0 |
| process_cache | process_cache_2 | 6935 | 15366 | 30 | 0 | 0 |
| process_ddr | process_ddr_1 | 17045 | 37881 | 60 | 0 | 0 |
| process_ddr | process_ddr_2 | 17045 | 37881 | 60 | 0 | 0 |
| grasu_degree_update | grasu_degree_update_1 | 2161 | 4115 | 4 | 0 | 0 |
| pma_to_regraph_adapter | pma_to_regraph_adapter_1 | 18526 | 22636 | 60 | 0 | 0 |
| lksg_stream | lksg_stream_1 | 23562 | 39535 | 128 | 64 | 0 |
| kernelLittleGSMerger | kernelLittleGSMerger_1 | 1216 | 6554 | 0 | 0 | 0 |
| regraph_pagerank_apply | regraph_pagerank_apply_1 | 160650 | 40225 | 60 | 0 | 0 |
| regraph_pagerank_source_prepare | pr_source_1 | 49551 | 26779 | 75 | 0 | 0 |
| kernelHBMWrapper | kernelHBMWrapper_1 | 9732 | 10888 | 45 | 0 | 0 |
