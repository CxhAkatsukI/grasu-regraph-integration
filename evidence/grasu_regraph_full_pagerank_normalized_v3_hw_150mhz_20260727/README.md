# Full PageRank normalized-v3 HW evidence

This bundle records the exact conversion-free GraSU+ReGraph Full PageRank
prototype built for the Xilinx U55C with a 150 MHz target. It is implementation
and PPA/timing evidence for the Candidate10 normalized simulator profile. It is
not FPGA runtime calibration and was not used to fit simulator cycle counts.

## Source and artifact identity

- integration source commit: `7b922ee24c488b8864f0951dc06275d9d0d54b1c`
- GraSU source commit: `d5c707c5b30b6c0e19ff1e56ea4b16801a46cfae`
- link configuration SHA-256: `1f44f40b273ca19bcf835c3baa0c57be950b4f92795f1c5431e0048613801563`
- xclbin SHA-256: `2b9dc0a57c5474fb929dcf64ee3483e94361dade2ecc86e3da82f67c327e209f`
- xclbin size: 67,330,105 bytes
- tool/device: Vitis 2024.1, `xilinx_u55c_gen3x16_xdma_3_202210_1`

The xclbin is retained under `/data/tmp/chuxiao/` and is intentionally not
tracked in Git. `artifacts.tsv` binds this evidence bundle to the exact artifact
by size and hash.

## Result

- Vitis compile, link, placement, routing, and bitstream generation completed.
- A hardware xclbin was generated.
- Routed user resources are 178,374 LUT, 177,836 registers, 278 BRAM, 64 URAM,
  and 304 DSP.
- The conversion-free graph path includes the PMA update CUs, degree update,
  PMA-to-ReGraph adapter, partition gather/merge path, PageRank source prepare,
  PageRank apply, and HBM wrapper. `link_kernels.tsv` records every CU and its
  multiplicity.
- The 150 MHz setup target missed by 0.130 ns: WNS is -0.130 ns and TNS is
  -15.019 ns across 311 endpoints. Hold and pulse-width timing pass.

The corresponding worst setup period is approximately 6.797 ns, or 147.1 MHz.
This proves a routed, bitstream-generating implementation close to 150 MHz. It
must not be reported as 150 MHz timing closure; a lower-frequency relink or a
timing fix is required for that stronger claim.

## Files

- `summary.md`: human-readable collector output.
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
  --label grasu_regraph_full_pagerank_normalized_v3_hw_150mhz \
  --build-root /data/tmp/chuxiao/grasu_regraph_full_pagerank_normalized_v3_hw_retry6_7b922ee_d5c707c_150mhz_20260727 \
  --out-dir /tmp/grasu_regraph_full_pagerank_evidence \
  --artifact /data/tmp/chuxiao/grasu_regraph_full_pagerank_normalized_v3_hw_retry6_7b922ee_d5c707c_150mhz_20260727/build/grasu_regraph_full_pagerank.hw.xclbin
```
