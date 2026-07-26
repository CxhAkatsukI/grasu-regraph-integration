# Weighted SSSP normalized-v3 HW evidence

This bundle records the exact conversion-free GraSU+ReGraph weighted-SSSP
prototype built for the Xilinx U55C with a 150 MHz target.  It is implementation
evidence for the Candidate10 normalized simulator profile; it is not FPGA
runtime calibration and was not used to fit simulator cycle counts.

## Source and artifact identity

- integration repository commit: `7b922ee24c488b8864f0951dc06275d9d0d54b1c`
- GraSU source commit: `d5c707c5b30b6c0e19ff1e56ea4b16801a46cfae`
- build configuration SHA-256: `dd4c5a9bc562383f8cc016c3e93f96ab5beebf100dd2d1ca0efef9f09472f856`
- xclbin SHA-256: `81c88089dcdc26e067e2cd33b9dd4d9be4d1edfdc92f8013a737eb7ce7a0d3c4`
- xclbin size: 61,522,672 bytes
- tool/device: Vitis 2024.1, `xilinx_u55c_gen3x16_xdma_3_202210_1`

The large xclbin is retained under `/data/tmp/chuxiao/` and is intentionally not
tracked in Git.  `artifacts.tsv` binds this evidence bundle to it by size and
hash.

## Result

- Vitis compile, link, placement, and routing completed.
- A hardware xclbin was generated.
- Routed user-kernel resources are 96,559 LUT, 107,380 registers, 233 BRAM,
  64 URAM, and 0 DSP.
- The linked topology contains four `bin_search`, two `process_cache`, two
  `process_ddr`, and one each of the remaining adapter/ReGraph kernels.  See
  `link_kernels.tsv` for the complete list.
- The 150 MHz timing target missed by 0.013 ns: WNS is -0.013 ns and TNS is
  -0.045 ns across seven endpoints.  Hold timing passes.

The corresponding period is approximately 6.680 ns, or 149.7 MHz.  Therefore
this bundle proves routed feasibility very close to 150 MHz, but it must not be
reported as 150 MHz timing closure.  A lower-frequency relink or a small timing
fix is still required for that stronger claim.

## Files

- `collector_summary.md`: human-readable extractor output.
- `artifacts.tsv`: xclbin identity.
- `link_kernels.tsv`: linked kernels and CU multiplicities.
- `connectivity.tsv`: port, stream, memory, and SLR mapping.
- `accelerator_util.tsv`, `slr_util.tsv`: routed utilization.
- `hls_area.tsv`: per-top HLS estimates.
- `timing.tsv`: routed setup/hold/pulse-width timing.
- `commands.tsv`, `system_estimate_*.tsv`, `copied_reports.tsv`: provenance.

Recreate the tables from the retained build with:

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 scripts/collect_vitis_evidence.py \
  --label grasu_regraph_weighted_sssp_normalized_v3_hw_150mhz \
  --build-root /data/tmp/chuxiao/grasu_regraph_weighted_sssp_normalized_v3_hw_20260726 \
  --out-dir /tmp/grasu_regraph_weighted_sssp_evidence \
  --artifact /data/tmp/chuxiao/grasu_regraph_weighted_sssp_normalized_v3_hw_20260726/build/grasu_regraph_weighted_pma_native.hw.xclbin
```
