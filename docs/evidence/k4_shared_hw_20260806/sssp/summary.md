# k4_shared_sssp_hw Vitis Evidence

- build_root: `/data/tmp/chuxiao/grasu_regraph_k4shared_sssp_hw_bb2bd3b_20260805`
- link_summaries: 1
- system_estimates: 2
- xclbins: 1
- selected_kernel_util: `/data/tmp/chuxiao/grasu_regraph_k4shared_sssp_hw_bb2bd3b_20260805/reports/link/link/imp/impl_1_kernel_util_routed.rpt`
- selected_slr_util: `/data/tmp/chuxiao/grasu_regraph_k4shared_sssp_hw_bb2bd3b_20260805/reports/link/link/imp/impl_1_slr_util_routed.rpt`
- selected_timing: `/data/tmp/chuxiao/grasu_regraph_k4shared_sssp_hw_bb2bd3b_20260805/build/link/link/vivado/vpl/prj/prj.runs/impl_1/dr_timing_summary.rpt`
- note: Conversion-free K4-shared U55C routed hardware packet.

## Selected Kernel Utilization Used Resources

| LUT | LUTAsMem | REG | BRAM | URAM | DSP |
| --- | -------- | --- | ---- | ---- | --- |
| 95589 | 11773 | 104930 | 229 | 64 | 0 |

## Timing

| WNS(ns) | TNS(ns) | WHS(ns) | THS(ns) |
| ------- | ------- | ------- | ------- |
| 0.001 | 0.000 | 0.009 | 0.000 |

## HLS Top-Module Area

| Kernel | Compute Unit | FF | LUT | BRAM | URAM | DSP |
| ------ | ------------ | -- | --- | ---- | ---- | --- |
| bin_search | bin_search_1 | 3286 | 4937 | 4 | 0 | 0 |
| bin_search | bin_search_2 | 3286 | 4937 | 4 | 0 | 0 |
| bin_search | bin_search_3 | 3286 | 4937 | 4 | 0 | 0 |
| bin_search | bin_search_4 | 3286 | 4937 | 4 | 0 | 0 |
| dispatch | dispatch_1 | 389 | 935 | 0 | 0 | 0 |
| kernelApply | kernelApply_1 | 12191 | 8221 | 30 | 0 | 0 |
| kernelHBMWrapper | kernelHBMWrapper_1 | 9732 | 10888 | 45 | 0 | 0 |
| kernelLittleGSMerger | kernelLittleGSMerger_1 | 1068 | 6100 | 0 | 0 | 0 |
| process_cache | process_cache_1 | 7006 | 15471 | 30 | 0 | 0 |
| process_cache | process_cache_2 | 7006 | 15471 | 30 | 0 | 0 |
| process_ddr | process_ddr_1 | 25045 | 39946 | 60 | 0 | 0 |
| process_ddr | process_ddr_2 | 25045 | 39946 | 60 | 0 | 0 |
| pma_completion_barrier | pma_completion_barrier_1 | 41 | 87 | 0 | 0 | 0 |
| pma_to_regraph_adapter | pma_to_regraph_adapter_1 | 18352 | 20182 | 62 | 0 | 0 |
| lksg_stream | lksg_stream_1 | 18645 | 38791 | 128 | 64 | 0 |
