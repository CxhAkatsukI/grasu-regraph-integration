# Weighted PMA native `hw` timing failure evidence

This directory records the acceptance state of the first complete weighted
GraSU PMA to ReGraph SSSP hardware link generated from integration commit
`a927186446b61163bba04e3e263f370fa0e32d63` on 2026-07-26.

## Result

- All ten required `hw` XOs were generated.
- Vitis packaged
  `grasu_regraph_weighted_pma_native.hw.xclbin`.
- Routed timing did not close: WNS `-0.187 ns`, TNS `-13.166 ns`, 225 setup
  failing endpoints.
- The failing path group is the fixed 450 MHz `hbm_aclk`, not the 200 MHz
  kernel clock.
- The worst path is in `hmss_0/path_28`, crosses `SLR1 -> SLR0`, and has
  `1.882 ns` route delay out of a `1.959 ns` data path (`96.1%`).

The packaged xclbin is retained as evidence but is not classified as timing
closed. Lowering only `--kernel_frequency` cannot fix this path.

## Authoritative external paths

Build root:

```text
/data/tmp/chuxiao/grasu_regraph_weighted_sssp_native_hw_a927186_20260726
```

Timing report:

```text
/data/tmp/chuxiao/grasu_regraph_weighted_sssp_native_hw_a927186_20260726/build/link/link/vivado/vpl/prj/prj.runs/impl_1/hw_bb_locked_timing_summary_routed.rpt
```

`artifacts.tsv` pins the source manifest, connectivity, packaged xclbin,
timing report, and all ten XOs by SHA256. The build is reproducible through
`scripts/prepare_pure_hw_pipeline_build.sh`; timing-closure retries are created
with `scripts/prepare_weighted_pma_hw_relink.py` and never overwrite this root.
