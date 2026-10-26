#pragma once

#include "weighted_pma_runtime_plan.hpp"

#include <numeric>

namespace grasu::integration {

inline bool weighted_pma_shard_has_updates(const WeightedPmaShardRuntimePlan &shard)
{
    return std::accumulate(shard.update_counts.begin(), shard.update_counts.end(),
                           std::size_t{0}) != 0;
}

// Copies are only needed by updating shards; gather retains the canonical row.
inline WeightedPmaRuntimePlan replicate_weighted_pma_metadata(
    WeightedPmaRuntimePlan plan)
{
    for (std::size_t shard = 0; shard < plan.shards.size(); ++shard) {
        if (!weighted_pma_shard_has_updates(plan.shards[shard])) continue;
        for (const std::string name : {"row", "binary"}) {
            const auto original = find_weighted_pma_region(plan, shard, name);
            for (std::size_t lane = 1; lane < 4; ++lane) {
                auto copy = original;
                copy.name += std::to_string(lane);
                copy.channel_first = kWeightedPmaU55cLaneChannelRanges[lane].first;
                copy.channel_last = kWeightedPmaU55cLaneChannelRanges[lane].second;
                plan.regions.push_back(copy);
            }
        }
    }
    const auto place = [&](bool fixed) {
        std::fill(plan.channel_load_bytes.begin(), plan.channel_load_bytes.end(), 0);
        plan.total_allocated_bytes = 0;
        std::vector<std::size_t> order(plan.regions.size());
        std::iota(order.begin(), order.end(), 0);
        std::stable_sort(order.begin(), order.end(), [&](auto left, auto right) {
            return plan.regions[left].allocated_bytes > plan.regions[right].allocated_bytes;
        });
        for (const auto index : order) {
            auto &region = plan.regions[index];
            const bool metadata = region.name.rfind("row", 0) == 0 ||
                                  region.name.rfind("binary", 0) == 0;
            std::size_t first = region.channel_first, last = region.channel_last;
            if (fixed) {
                const auto lane = metadata && (region.name == "row" || region.name == "binary")
                    ? 0 : static_cast<std::size_t>(region.name.back() - '0');
                first = kWeightedPmaU55cLaneChannelRanges.at(lane).first;
                last = first + 1;
            } else if (metadata && (region.name == "row" || region.name == "binary") &&
                       weighted_pma_shard_has_updates(plan.shards[region.shard])) {
                first = 0;
                last = kWeightedPmaU55cLaneChannelRanges[0].second;
            }
            auto selected = plan.channel_load_bytes.size();
            for (auto bank = first; bank < last; ++bank) {
                if (region.allocated_bytes > plan.channel_capacity_bytes -
                    plan.channel_load_bytes.at(bank)) continue;
                if (selected == plan.channel_load_bytes.size() ||
                    plan.channel_load_bytes[bank] < plan.channel_load_bytes[selected]) {
                    selected = bank;
                }
            }
            if (selected == plan.channel_load_bytes.size()) return false;
            region.channel = selected;
            plan.channel_load_bytes[selected] += region.allocated_bytes;
            plan.total_allocated_bytes += region.allocated_bytes;
        }
        return true;
    };
    // Capacity, not measured speed, selects the fixed-bank diagnostic layout.
    if (!place(true) && !place(false)) {
        throw std::overflow_error("replicated metadata exceeds lane-aware HBM capacity");
    }
    return plan;
}

}  // namespace grasu::integration
