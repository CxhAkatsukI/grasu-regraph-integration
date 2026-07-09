# Current GraSU -> ReGraph PR Sweep

Date: 2026-07-10

This sweep tests the currently available composed system:

```text
GraSU update/check -> GraSU result to ReGraph edge-list conversion -> ReGraph PR hw
```

It does not test SSSP. It is a current-system integration and timing sanity
test, not a fair comparison against Spine SSSP.

## Command

```bash
cd /home/chuxiao/grasu-regraph-integration
./scripts/run_current_pr_sweep.sh \
  --out-root results/current_pr_sweep_20260710_0001 \
  --timeout 300
```

The last three larger cases were appended with the same runner after extending
the default case list.

## Result Location

```text
results/current_pr_sweep_20260710_0001/
results/current_pr_sweep_20260710_0001/summary.tsv
```

## Summary

| case | status | wall s | updates | final edges | GraSU ms | GraSU Mups | ReGraph e2e ms | ReGraph MTEPS |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tiny_spread_v16_u8 | PASS | 16.945 | 8 | 24 | 1.627 | 0.005 | 0.191 | 0.126 |
| tiny_hot_v16_u8 | PASS | 16.797 | 8 | 24 | 1.618 | 0.005 | 0.223 | 0.107 |
| tiny_delete_v16_u8 | PASS | 16.851 | 8 | 8 | 1.643 | 0.005 | 0.226 | 0.035 |
| small_spread_v4096_u1024 | PASS | 16.894 | 1024 | 5120 | 1.868 | 0.548 | 0.215 | 23.833 |
| small_hot_v4096_u1024 | PASS | 16.392 | 1024 | 5120 | 2.617 | 0.391 | 0.226 | 22.653 |
| medium_spread_v16384_u4096 | PASS | 16.278 | 4096 | 20480 | 2.634 | 1.555 | 0.219 | 93.415 |
| medium_hot_v16384_u4096 | PASS | 16.548 | 4096 | 20480 | 5.626 | 0.728 | 0.207 | 99.006 |
| large_spread_v65536_u16384 | PASS | 16.552 | 16384 | 81920 | 4.846 | 3.381 | 0.269 | 303.973 |
| large_hot_v65536_u16384 | PASS | 16.747 | 16384 | 81920 | 20.797 | 0.788 | 0.298 | 274.910 |

## Observations

1. All 9 cases passed.

2. Cold wall time is almost flat at about 16 to 17 seconds. This includes two
   separate hardware program/load phases and host-side preprocessing, so it is
   dominated by orchestration rather than kernel execution.

3. GraSU update time scales with update shape. Spread updates improve with
   larger batches, from 1.868 ms at 1K updates to 4.846 ms at 16K updates.
   Hot-source updates become much more expensive:

```text
1K updates:   hot 2.617 ms vs spread 1.868 ms
4K updates:   hot 5.626 ms vs spread 2.634 ms
16K updates:  hot 20.797 ms vs spread 4.846 ms
```

4. ReGraph PR compute time is sub-millisecond for these small generated graphs.
   It rises slowly with final edge count, from about 0.19 ms on 24 edges to
   about 0.30 ms on 81,920 edges.

5. The current composed chain is useful as an integration baseline. It should
   not be used to claim performance against Spine SSSP until ReGraph is running
   BFS/SSSP-compatible computation.

## Next Steps

1. Add warm-run mode, if possible, to avoid programming xclbins for every case.
2. Build or locate ReGraph BFS hardware.
3. Reuse the same sweep structure for:

```text
GraSU update + ReGraph BFS
vs
Spine update + unit-weight SSSP
```

