# grasu_regraph_weighted_sssp_normalized_v3_hw_150mhz Vitis Evidence

- build_root: `/data/tmp/chuxiao/grasu_regraph_weighted_sssp_normalized_v3_hw_20260726`
- link_summaries: 1
- system_estimates: 11
- xclbins: 1
- selected_kernel_util: `/data/tmp/chuxiao/grasu_regraph_weighted_sssp_normalized_v3_hw_20260726/reports/link/link/imp/impl_1_kernel_util_routed.rpt`
- selected_slr_util: `/data/tmp/chuxiao/grasu_regraph_weighted_sssp_normalized_v3_hw_20260726/reports/link/link/imp/impl_1_slr_util_routed.rpt`
- selected_timing: `/data/tmp/chuxiao/grasu_regraph_weighted_sssp_normalized_v3_hw_20260726/build/link/link/vivado/vpl/prj/prj.runs/impl_1/dr_timing_summary.rpt`
- note: Candidate10 normalized v3 weighted SSSP exact conversion-free topology; Vitis 2024.1 U55C target 150 MHz.

## Selected Kernel Utilization Used Resources

| LUT | LUTAsMem | REG | BRAM | URAM | DSP |
| --- | -------- | --- | ---- | ---- | --- |
| 96559 | 12365 | 107380 | 233 | 64 | 0 |

## Timing

| WNS(ns) | TNS(ns) | WHS(ns) | THS(ns) |
| ------- | ------- | ------- | ------- |
| -0.013 | -0.045 | 0.009 | 0.000 |

## HLS Top-Module Area

| Kernel | Compute Unit | FF | LUT | BRAM | URAM | DSP |
| ------ | ------------ | -- | --- | ---- | ---- | --- |
| bin_search | bin_search_1 | 4008 | 5765 | 6 | 0 | 0 |
| dispatch | dispatch_1 | 389 | 935 | 0 | 0 | 0 |
| kernelApply | kernelApply_1 | 11888 | 7314 | 30 | 0 | 0 |
| kernelHBMWrapper | kernelHBMWrapper_1 | 9732 | 10888 | 45 | 0 | 0 |
| kernelLittleGSMerger | kernelLittleGSMerger_1 | 1068 | 6100 | 0 | 0 | 0 |
| bin_search | bin_search_2 | 4008 | 5765 | 6 | 0 | 0 |
| bin_search | bin_search_3 | 4008 | 5765 | 6 | 0 | 0 |
| bin_search | bin_search_4 | 4008 | 5765 | 6 | 0 | 0 |
| process_cache | process_cache_1 | 7006 | 15471 | 30 | 0 | 0 |
| process_cache | process_cache_2 | 7006 | 15471 | 30 | 0 | 0 |
| process_ddr | process_ddr_1 | 25045 | 39946 | 60 | 0 | 0 |
| process_ddr | process_ddr_2 | 25045 | 39946 | 60 | 0 | 0 |
| pma_completion_barrier | pma_completion_barrier_1 | 41 | 87 | 0 | 0 | 0 |
| pma_to_regraph_adapter | pma_to_regraph_adapter_1 | 18243 | 18654 | 62 | 0 | 0 |
| lksg_stream | lksg_stream_1 | 18645 | 38791 | 128 | 64 | 0 |
