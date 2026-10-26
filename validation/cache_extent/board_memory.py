"""Board-only admission with observed background work and a live reserve."""

from spine_cycle_sim.experiments.sharded_k4_stages.row_line.directory_tile.hardware import admission


def sample(lease, available, builds, policy):
    if not policy.get("allow_observed_unbounded_builds"):
        return lease.sample(available, builds, policy, commit=True)
    if policy["reserve_gib"] < 64:
        raise ValueError("observed-background board admission requires >=64 GiB live reserve")
    records = admission.reservations(builds, lease.own)
    rejected = {row["pid"] for row in records if not row["bounded"]}
    bounded = [row for row in builds if int(row.split()[0]) not in rejected]
    result = lease.sample(available, bounded, policy, commit=True)
    result["unbounded_background_observed"] = [row for row in records if not row["bounded"]]
    result["policy"] = "bounded_peer_leases_plus_observed_background_and_64GiB_live_reserve"
    result["external_growth_hard_bounded"] = not rejected
    return result
