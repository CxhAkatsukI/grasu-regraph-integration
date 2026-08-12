#pragma once

#include "weighted_pma_graph.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <stdexcept>
#include <utility>
#include <vector>

namespace grasu::integration {

struct WeightedPmaTouchedSegment {
    std::size_t shard{};
    std::size_t logical_segment{};
    std::size_t port{};
    std::size_t port_word_offset{};
    std::array<std::uint32_t, kWeightedPmaSegmentSlots> expected{};
};

inline std::size_t weighted_pma_update_segment(
    const WeightedPmaShard &shard,
    std::uint64_t packed_update)
{
    const std::uint64_t edge = packed_update & ~kWeightedPmaDelete;
    const std::uint32_t source = static_cast<std::uint32_t>(edge >> 32);
    const std::uint32_t word = static_cast<std::uint32_t>(edge);
    const std::uint64_t bounds = shard.row_bounds.at(source);
    const std::size_t begin_segment =
        (bounds >> 32) / kWeightedPmaSegmentSlots;
    const std::size_t end_segment =
        static_cast<std::uint32_t>(bounds) / kWeightedPmaSegmentSlots;
    if (begin_segment >= end_segment) {
        throw std::logic_error("weighted PMA update has no reserved segment");
    }

    const std::uint64_t key =
        (static_cast<std::uint64_t>(source) << 32) | word;
    std::size_t segment = begin_segment;
    for (std::size_t candidate = begin_segment; candidate < end_segment;
         ++candidate) {
        if (shard.binary_heads.at(candidate) <= key) {
            segment = candidate;
        }
    }
    return segment;
}

inline std::pair<std::size_t, std::size_t> weighted_pma_segment_port(
    std::size_t logical_segment,
    std::size_t max_cache_segments)
{
    const std::size_t parity = logical_segment & 1U;
    const std::size_t local_segment = logical_segment >> 1U;
    const std::size_t port = local_segment < max_cache_segments
                                 ? parity * 2U
                                 : parity * 2U + 1U;
    return {port, local_segment * kWeightedPmaSegmentSlots};
}

inline std::vector<WeightedPmaTouchedSegment>
build_weighted_pma_update_reference(
    const WeightedPartitionedPmaGraph &graph,
    std::size_t max_cache_segments)
{
    using SegmentKey = std::pair<std::size_t, std::size_t>;
    std::map<SegmentKey,
             std::array<std::uint32_t, kWeightedPmaSegmentSlots>> expected;

    for (std::size_t shard_index = 0; shard_index < graph.shards.size();
         ++shard_index) {
        const WeightedPmaShard &shard = graph.shards[shard_index];
        for (const std::uint64_t update : shard.physical_updates) {
            const std::size_t segment =
                weighted_pma_update_segment(shard, update);
            auto [entry, inserted] = expected.try_emplace(
                SegmentKey{shard_index, segment});
            if (inserted) {
                std::copy_n(
                    shard.initial_pma_words.begin() +
                        segment * kWeightedPmaSegmentSlots,
                    kWeightedPmaSegmentSlots, entry->second.begin());
            }

            auto &words = entry->second;
            const bool delete_op = (update & kWeightedPmaDelete) != 0;
            const std::uint32_t word = static_cast<std::uint32_t>(update);
            auto position = std::lower_bound(words.begin(), words.end(), word);
            if (delete_op) {
                if (position == words.end() || *position != word) {
                    throw std::logic_error(
                        "weighted PMA reference delete did not find edge");
                }
                std::rotate(position, position + 1, words.end());
                words.back() = kWeightedPmaEmpty;
            } else {
                if (words.back() != kWeightedPmaEmpty) {
                    throw std::logic_error(
                        "weighted PMA reference insertion overflowed segment");
                }
                std::move_backward(position, words.end() - 1, words.end());
                *position = word;
            }
        }
    }

    std::vector<WeightedPmaTouchedSegment> result;
    result.reserve(expected.size());
    for (const auto &[key, words] : expected) {
        const auto [port, offset] =
            weighted_pma_segment_port(key.second, max_cache_segments);
        result.push_back({
            .shard = key.first,
            .logical_segment = key.second,
            .port = port,
            .port_word_offset = offset,
            .expected = words,
        });
    }
    return result;
}

}  // namespace grasu::integration
