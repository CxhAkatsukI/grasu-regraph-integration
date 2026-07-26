# Weighted PMA native hardware timing-closure relink

## Scope

The weighted GraSU PMA to ReGraph SSSP native pipeline built all ten `hw` XOs
and produced a packaged xclbin from integration commit `a927186`. The routed
design did not meet timing:

- WNS: `-0.187 ns`
- TNS: `-13.166 ns`
- failing endpoints: `225`
- failing clock: fixed U55C `hbm_aclk` at `450 MHz`
- worst path: `hmss_0/path_28`, crossing `SLR1 -> SLR0`
- route contribution to the worst data path: `1.882 / 1.959 ns` (`96.1%`)

The 200 MHz kernel paths are not the failing paths. Reducing only
`--kernel_frequency` therefore does not address this violation.

## Relink policy

The relink packets reuse the exact ten XOs and original connectivity. Each XO
hash is recorded in `inputs.tsv` and `manifest.json`. Only implementation
directives and output/report directories change. The failed source build is
never overwritten.

Try the profiles serially:

1. `route-aggressive`: AltSpreadLogic placement and aggressive physical
   optimization/routing.
2. `place-extranet`: ExtraNetDelay placement and AlternateCLBRouting, only if
   the first profile still has negative WNS or TNS.

Do not run both links concurrently. Their common input XOs are immutable, but
parallel Vivado implementation would compete for memory, CPU, and routing
licenses and make wall-time evidence difficult to interpret.

## Generate the first packet

```bash
cd /home/chuxiao/grasu-regraph-integration
python3 scripts/prepare_weighted_pma_hw_relink.py \
  --source-build-root /data/tmp/chuxiao/grasu_regraph_weighted_sssp_native_hw_a927186_20260726 \
  --out-root /data/tmp/chuxiao/grasu_regraph_weighted_sssp_native_hw_relink_route_aggressive_a927186_20260726 \
  --profile route-aggressive
```

Run the generated long command only after other Vitis/Vivado hardware builds
are idle:

```bash
/data/tmp/chuxiao/grasu_regraph_weighted_sssp_native_hw_relink_route_aggressive_a927186_20260726/link_command.sh \
  > /data/tmp/chuxiao/grasu_regraph_weighted_sssp_native_hw_relink_route_aggressive_a927186_20260726/link.stdout.log \
  2>&1
```

Collect the acceptance result even when `v++` exits nonzero:

```bash
/data/tmp/chuxiao/grasu_regraph_weighted_sssp_native_hw_relink_route_aggressive_a927186_20260726/collect_result.sh
```

Acceptance requires both:

- the expected xclbin exists;
- the selected routed timing report has `WNS >= 0` and `TNS >= 0`.

A packaged xclbin with negative slack remains `relink_not_accepted`.
