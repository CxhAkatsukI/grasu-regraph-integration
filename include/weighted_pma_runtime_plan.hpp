#pragma once

#include "weighted_pma_graph.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace grasu::integration {

constexpr std::size_t kU55cHbmPseudoChannelBytes = 512ULL << 20;
constexpr std::size_t kWeightedPmaRuntimeChannels = 23;
constexpr std::size_t kWeightedPmaRuntimeAlignment = 4096;

struct WeightedPmaBufferRegion {
    std::size_t shard{};
    std::string name;
    std::size_t logical_bytes{};
    std::size_t allocated_bytes{};
    std::size_t channel{};
};

struct WeightedPmaShardRuntimePlan {
    std::uint32_t destination_base{};
    std::size_t destination_vertices{};
    std::size_t pma_slot_count{};
    std::size_t even_segments{};
    std::size_t odd_segments{};
    std::array<std::size_t, 4> pma_words{};
    std::array<std::size_t, 4> update_counts{};
    std::array<std::size_t, 4> update_alloc_counts{};
    std::size_t row_words{};
    std::size_t binary_words{};
};

struct WeightedPmaRuntimePlan {
    std::size_t max_cache_segments{};
    std::size_t channel_capacity_bytes{};
    std::vector<WeightedPmaShardRuntimePlan> shards;
    std::vector<WeightedPmaBufferRegion> regions;
    std::vector<std::size_t> channel_load_bytes;
    std::size_t total_allocated_bytes{};
};

struct WeightedPmaPackedShardBuffers {
    std::array<std::vector<std::uint64_t>, 4> updates;
    std::array<std::vector<std::uint32_t>, 4> pma_words;
    std::vector<std::uint64_t> row_bounds;
    std::vector<std::uint64_t> binary_heads;
};

inline std::size_t align_weighted_pma_runtime_bytes(
    std::size_t value,
    std::size_t alignment = kWeightedPmaRuntimeAlignment)
{
    if (alignment == 0 || (alignment & (alignment - 1)) != 0 ||
        value > std::numeric_limits<std::size_t>::max() - (alignment - 1)) {
        throw std::invalid_argument("invalid weighted PMA runtime alignment");
    }
    return (value + alignment - 1) & ~(alignment - 1);
}

inline WeightedPmaRuntimePlan build_weighted_pma_runtime_plan(
    const WeightedPartitionedPmaGraph &graph,
    std::size_t max_cache_segments,
    std::size_t channels = kWeightedPmaRuntimeChannels,
    std::size_t channel_capacity_bytes = kU55cHbmPseudoChannelBytes)
{
    if (graph.vertices == 0 || graph.shards.empty() ||
        max_cache_segments == 0 || channels == 0 ||
        channel_capacity_bytes == 0) {
        throw std::invalid_argument("invalid weighted PMA runtime geometry");
    }

    WeightedPmaRuntimePlan result;
    result.max_cache_segments = max_cache_segments;
    result.channel_capacity_bytes = channel_capacity_bytes;
    result.channel_load_bytes.assign(channels, 0);
    result.shards.reserve(graph.shards.size());

    const auto add_region = [&result](std::size_t shard,
                                      std::string name,
                                      std::size_t logical_bytes) {
        result.regions.push_back({
            .shard = shard,
            .name = std::move(name),
            .logical_bytes = logical_bytes,
            .allocated_bytes = align_weighted_pma_runtime_bytes(
                std::max<std::size_t>(logical_bytes, 1)),
        });
    };

    for (std::size_t shard_index = 0; shard_index < graph.shards.size();
         ++shard_index) {
        const WeightedPmaShard &shard = graph.shards[shard_index];
        if (shard.initial_pma_words.empty() ||
            shard.initial_pma_words.size() % kWeightedPmaSegmentSlots != 0 ||
            shard.row_bounds.size() != graph.vertices + 1 ||
            shard.binary_heads.size() !=
                shard.initial_pma_words.size() / kWeightedPmaSegmentSlots) {
            throw std::invalid_argument("invalid weighted PMA shard buffers");
        }

        WeightedPmaShardRuntimePlan plan;
        plan.destination_base = shard.destination_base;
        plan.destination_vertices = shard.destination_vertices;
        plan.pma_slot_count = shard.initial_pma_words.size();
        const std::size_t segments =
            shard.initial_pma_words.size() / kWeightedPmaSegmentSlots;
        plan.even_segments = (segments + 1) / 2;
        plan.odd_segments = segments / 2;
        plan.pma_words[0] = max_cache_segments * kWeightedPmaSegmentSlots;
        plan.pma_words[1] =
            (plan.even_segments > max_cache_segments
                 ? plan.even_segments
                 : 1) *
            kWeightedPmaSegmentSlots;
        plan.pma_words[2] = max_cache_segments * kWeightedPmaSegmentSlots;
        plan.pma_words[3] =
            (plan.odd_segments > max_cache_segments
                 ? plan.odd_segments
                 : 1) *
            kWeightedPmaSegmentSlots;
        plan.row_words = shard.row_bounds.size();
        plan.binary_words = std::max<std::size_t>(shard.binary_heads.size(), 1);

        for (std::size_t lane = 0; lane < 4; ++lane) {
            plan.update_counts[lane] = shard.physical_updates.size() / 4;
        }
        for (std::size_t lane = 0;
             lane < shard.physical_updates.size() % 4; ++lane) {
            ++plan.update_counts[lane];
        }
        for (std::size_t lane = 0; lane < 4; ++lane) {
            plan.update_alloc_counts[lane] =
                std::max<std::size_t>(plan.update_counts[lane], 1);
            add_region(shard_index, "update" + std::to_string(lane),
                       plan.update_alloc_counts[lane] * sizeof(std::uint64_t));
            add_region(shard_index, "pma" + std::to_string(lane),
                       plan.pma_words[lane] * sizeof(std::uint32_t));
        }
        add_region(shard_index, "row", plan.row_words * sizeof(std::uint64_t));
        add_region(shard_index, "binary",
                   plan.binary_words * sizeof(std::uint64_t));
        result.shards.push_back(plan);
    }

    std::vector<std::size_t> order(result.regions.size());
    for (std::size_t index = 0; index < order.size(); ++index) {
        order[index] = index;
    }
    std::sort(order.begin(), order.end(), [&result](std::size_t left,
                                                     std::size_t right) {
        const auto &a = result.regions[left];
        const auto &b = result.regions[right];
        if (a.allocated_bytes != b.allocated_bytes) {
            return a.allocated_bytes > b.allocated_bytes;
        }
        return std::pair(a.shard, a.name) < std::pair(b.shard, b.name);
    });

    for (const std::size_t region_index : order) {
        WeightedPmaBufferRegion &region = result.regions[region_index];
        std::size_t selected = channels;
        for (std::size_t channel = 0; channel < channels; ++channel) {
            if (region.allocated_bytes > channel_capacity_bytes ||
                result.channel_load_bytes[channel] >
                    channel_capacity_bytes - region.allocated_bytes) {
                continue;
            }
            if (selected == channels ||
                result.channel_load_bytes[channel] <
                    result.channel_load_bytes[selected]) {
                selected = channel;
            }
        }
        if (selected == channels) {
            throw std::overflow_error(
                "weighted PMA runtime buffers exceed HBM pseudo-channel capacity");
        }
        region.channel = selected;
        result.channel_load_bytes[selected] += region.allocated_bytes;
        result.total_allocated_bytes += region.allocated_bytes;
    }
    return result;
}

inline const WeightedPmaBufferRegion &find_weighted_pma_region(
    const WeightedPmaRuntimePlan &plan,
    std::size_t shard,
    const std::string &name)
{
    const auto found = std::find_if(
        plan.regions.begin(), plan.regions.end(),
        [shard, &name](const WeightedPmaBufferRegion &region) {
            return region.shard == shard && region.name == name;
        });
    if (found == plan.regions.end()) {
        throw std::out_of_range("weighted PMA runtime region is missing");
    }
    return *found;
}

inline std::vector<WeightedPmaPackedShardBuffers>
pack_weighted_pma_runtime_buffers(
    const WeightedPartitionedPmaGraph &graph,
    const WeightedPmaRuntimePlan &plan)
{
    if (graph.shards.size() != plan.shards.size()) {
        throw std::invalid_argument("weighted PMA graph/runtime shard mismatch");
    }
    std::vector<WeightedPmaPackedShardBuffers> result(graph.shards.size());
    for (std::size_t shard_index = 0; shard_index < graph.shards.size();
         ++shard_index) {
        const WeightedPmaShard &shard = graph.shards[shard_index];
        const WeightedPmaShardRuntimePlan &shard_plan = plan.shards[shard_index];
        WeightedPmaPackedShardBuffers &buffers = result[shard_index];
        for (std::size_t lane = 0; lane < 4; ++lane) {
            buffers.updates[lane].assign(
                shard_plan.update_alloc_counts[lane], 0);
            buffers.pma_words[lane].assign(
                shard_plan.pma_words[lane], kWeightedPmaEmpty);
        }
        for (std::size_t update = 0; update < shard.physical_updates.size();
             ++update) {
            buffers.updates[update % 4][update / 4] =
                shard.physical_updates[update];
        }
        for (std::size_t slot = 0; slot < shard.initial_pma_words.size();
             slot += kWeightedPmaSegmentSlots) {
            const std::size_t segment = slot / kWeightedPmaSegmentSlots;
            const std::size_t parity = segment & 1;
            const std::size_t local_segment = segment >> 1;
            const std::size_t port =
                local_segment < plan.max_cache_segments
                    ? parity * 2
                    : parity * 2 + 1;
            const std::size_t output_slot =
                local_segment * kWeightedPmaSegmentSlots;
            if (output_slot + kWeightedPmaSegmentSlots >
                buffers.pma_words[port].size()) {
                throw std::logic_error("weighted PMA packed port overflow");
            }
            std::copy_n(shard.initial_pma_words.begin() + slot,
                        kWeightedPmaSegmentSlots,
                        buffers.pma_words[port].begin() + output_slot);
        }
        buffers.row_bounds = shard.row_bounds;
        buffers.binary_heads.assign(shard_plan.binary_words, 0);
        std::copy(shard.binary_heads.begin(), shard.binary_heads.end(),
                  buffers.binary_heads.begin());
    }
    return result;
}

}  // namespace grasu::integration
