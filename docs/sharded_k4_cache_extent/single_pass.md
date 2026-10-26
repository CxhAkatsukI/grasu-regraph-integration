# Replicated-Metadata Single-Pass FPGA Check

## Contract

This is a quick check, not a repeated statistical experiment: eight full
graphs by SSSP, CC and residual PR, exactly one G+R execution and one Spine
execution per case, no warmups, no averaging, no discarded successful samples.
Inputs, source vertices, bitstreams and Spine hosts are inherited from the
completed `full-matrix-v2` comparison. No routing or kernel changes are needed.

The continuous resident wall starts with the update and ends after convergence
and final readback, including host launch/wait/relaunch. Initial graph/PMA
construction, old-graph convergence, residency and correctness oracles remain
outside this boundary for both systems. The legacy G+R log field
`setup_inclusive_ms` denotes that resident wall, not initial graph setup.

## Host Change

`GRASU_SHARDED_METADATA_REPLICAS=4` gives each G search CU its own immutable row
and binary-head buffers. Only shards containing physical updates need copies;
the adapter keeps using the canonical row buffer. All copies are initialized
and migrated before updates. No PMA contents are overwritten after updating.
The default `1` retains the previous shared-metadata allocation.

The planner first checks whether the whole graph, including copies, fits fixed
banks 0/6/12/18, matching the isolated G diagnostic's bank arrangement. If not,
it places buffers over the original lane-compatible 23-bank budget. This choice
depends only on allocation sizes, never on measured speed. Every bank is capped
at 512 MiB, with 4096-byte allocation rounding. Non-updated shards do not receive
three unnecessary extra full-source directories. `SHARDED_METADATA_POLICY` logs
the chosen layout and allocation size. A large-graph 23-bank run must not be
described as the four-bank diagnostic control.

The planner is in `include/weighted_pma_metadata_plan.hpp`; allocation and search
binding are shared by the three algorithm hosts in
`tools/sharded_cache_runtime.hpp`. Kernel ABI, graph ordering, partitions,
update contents and convergence policy do not change.

## Reproduction And Evidence

The runner is `validation/cache_extent/single_pass.py`. It validates the prior
graph/bitstream/Spine-host hashes, pins the new G+R hosts and host sources, and
reuses the board/correctness checks. Each case has a 16/24/32-GiB cgroup limit,
zero swap and a process-tree watchdog. The initial fifteen completed cases
reserved 24 GiB; subsequent cases reserve 64 GiB (including 40 GiB extra
headroom for unrelated, uncapped background tools). It
holds the existing device-1 board lock and checks for other card users.

```sh
PYTHONPATH=/home/chuxiao/spine-cycle-sim/spine-cycle-sim-production-board:/home/chuxiao/grasu-regraph-sim-aligned \
python3 -m validation.cache_extent.single_pass \
  --previous /data/chuxiao/checks/spine-cc-respr-host-20261026/full-matrix-v2 \
  --hosts /data/chuxiao/checks/grasu-replicated-host-singlepass-20261026-v1/hosts \
  --output /data/chuxiao/checks/grasu-replicated-host-singlepass-20261026-v1/matrix \
  --pythonpath /home/chuxiao/spine-cycle-sim/spine-cycle-sim-production-board:/home/chuxiao/grasu-regraph-sim-aligned
```

Output must be a new directory. `matrix/summary.csv` and `matrix/results.json`
contain the single-run ratios and raw walls. Each case retains both FPGA logs,
clock dumps, hashes, memory events and convergence/correctness results.

`--resume` skips every previously attempted case, including retained failures.
It refuses a partially recorded `RUNNING` case unless its stopped unit and
saved admission state prove no sample ever started: no sample directory,
no current sample, no completed samples and `board_tested=false`. That
unexecuted admission attempt is archived under `admission-interruptions/`
before retrying. Prior artifact hashes come from both the old configuration and its
actual execution manifest; conflicting hashes are rejected.

This campaign's coordinator initially stopped after all eight SSSP pairs,
before executing CC. The old CC configuration omitted its Spine bitstream pin,
although the prior execution manifest contained it. The coordinator was fixed
to consult that manifest and resumed the remaining sixteen pairs without
repeating SSSP. `single_pass-v1.py` and `single_pass-v2.py` in the evidence root
preserve both coordinator revisions. Host sources and all six host binaries
remained unchanged across this interruption. This was not an FPGA failure.

After fifteen completed pairs, CC R19 waited at admission because unrelated
FPGA tools had no acceptable finite cgroup/swap budget, despite ample measured
memory and an idle card. The coordinator and unexecuted unit were stopped.
The board-only admission now preserves finite peer reservations while recording
uncapped background processes separately and requiring a 64-GiB live reserve;
the watchdog stops our child if that reserve is breached. This is observed
headroom, not a claim that another user's future memory use is hard bounded.
Our own hard cgroup cap and zero swap remain enforced. Shared compiler
admission rules and the other user's processes were not changed.
`board-v1.py`, `board-v2.py` and `single_pass-v3.py` preserve the revisions.
No measured pair was repeated and no host executable or bitstream changed.

As in the inherited matrix, residual PR uses the direct per-vertex threshold
`1e-6`. These eight batches previously required zero propagation rounds. Such
rows measure update/correction/completion, not a demonstrated nonzero-propagation
speedup. Do not substitute a new threshold or a different batch silently.

The isolated G-only diagnostic's 9-17% comparison with the public HLS port is
not automatically a claim about these eight-update full-system workloads, nor
about agreement with the GraSU paper's unpublished implementation.
