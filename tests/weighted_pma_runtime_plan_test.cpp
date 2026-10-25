#include "weighted_pma_runtime_plan.hpp"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <stdexcept>
#include <vector>

using grasu::integration::WeightedEdgeRecord;
using grasu::integration::WeightedPmaChannelPolicy;
using grasu::integration::build_weighted_partitioned_pma_graph;
using grasu::integration::build_weighted_pma_runtime_plan;
using grasu::integration::find_weighted_pma_region;
using grasu::integration::kWeightedPmaSegmentSlots;
using grasu::integration::pack_weighted_pma_runtime_buffers;

int main()
{
    {
        grasu::integration::WeightedPmaShardRuntimePlan shard{};
        shard.even_segments = 17;
        shard.odd_segments = 15;
        using grasu::integration::weighted_pma_cache_valid_segments;
        assert(weighted_pma_cache_valid_segments(shard, 0, 32) == 17);
        assert(weighted_pma_cache_valid_segments(shard, 1, 32) == 15);
        assert(weighted_pma_cache_valid_segments(shard, 0, 16) == 16);
        shard.even_segments = 0;
        assert(weighted_pma_cache_valid_segments(shard, 0, 32) == 0);
        for (const auto capacity : {0U, 15U, 17U}) {
            bool rejected = false;
            try { (void)weighted_pma_cache_valid_segments(shard, 0, capacity); }
            catch (const std::invalid_argument &) { rejected = true; }
            assert(rejected);
        }
        bool rejected = false;
        try { (void)weighted_pma_cache_valid_segments(shard, 2, 32); }
        catch (const std::invalid_argument &) { rejected = true; }
        assert(rejected);
    }
    const std::vector<WeightedEdgeRecord> initial = {
        {.source = 0, .destination = 1, .weight = 2},
        {.source = 1, .destination = 8, .weight = 3},
        {.source = 2, .destination = 16, .weight = 4},
        {.source = 3, .destination = 24, .weight = 5},
    };
    const std::vector<WeightedEdgeRecord> updates = {
        {.source = 0, .destination = 9, .weight = 6},
        {.source = 2, .destination = 16, .weight = 7},
    };
    const auto graph =
        build_weighted_partitioned_pma_graph(25, 8, initial, updates);
    const auto plan = build_weighted_pma_runtime_plan(
        graph, 32, 4, 1ULL << 20);

    assert(plan.shards.size() == 4);
    assert(plan.regions.size() == 4 * 10);
    assert(plan.channel_load_bytes.size() == 4);
    assert(plan.total_allocated_bytes > 0);
    for (const auto &shard : plan.shards) {
        assert(shard.pma_words[0] == 32 * kWeightedPmaSegmentSlots);
        assert(shard.pma_words[2] == 32 * kWeightedPmaSegmentSlots);
        assert(shard.row_words == 26);
        assert(shard.binary_words >= 1);
    }
    for (const auto &region : plan.regions) {
        assert(region.allocated_bytes % 4096 == 0);
        assert(region.channel < 4);
        assert(region.allocated_bytes <= 1ULL << 20);
    }
    assert(find_weighted_pma_region(plan, 0, "row").logical_bytes ==
           26 * sizeof(std::uint64_t));

    const auto packed = pack_weighted_pma_runtime_buffers(graph, plan);
    const auto line_plan = build_weighted_pma_runtime_plan(
        graph, 32, 4, 1ULL << 20, WeightedPmaChannelPolicy::unrestricted, true);
    const auto line_packed = pack_weighted_pma_runtime_buffers(graph, line_plan);
    assert(line_plan.total_allocated_bytes == plan.total_allocated_bytes);
    assert(packed.size() == graph.shards.size());
    for (std::size_t shard_index = 0; shard_index < graph.shards.size();
         ++shard_index) {
        const auto &shard = graph.shards[shard_index];
        const auto &buffers = packed[shard_index];
        assert(buffers.row_bounds == shard.row_bounds);
        assert(line_plan.shards[shard_index].row_words == 32);
        assert(line_packed[shard_index].row_bounds.size() == 32);
        assert(find_weighted_pma_region(line_plan, shard_index, "row").logical_bytes == 256);
        assert(std::equal(shard.row_bounds.begin(), shard.row_bounds.end(),
                          line_packed[shard_index].row_bounds.begin()));
        assert(std::all_of(line_packed[shard_index].row_bounds.begin() + 26,
                           line_packed[shard_index].row_bounds.end(),
                           [](auto row) { return row == 0; }));
        assert(line_packed[shard_index].pma_words == buffers.pma_words);
        assert(line_packed[shard_index].updates == buffers.updates);
        assert(line_packed[shard_index].binary_heads == buffers.binary_heads);
        assert(std::equal(shard.binary_heads.begin(), shard.binary_heads.end(),
                          buffers.binary_heads.begin()));
        for (std::size_t slot = 0; slot < shard.initial_pma_words.size();
             slot += kWeightedPmaSegmentSlots) {
            const std::size_t segment = slot / kWeightedPmaSegmentSlots;
            const std::size_t parity = segment & 1;
            const std::size_t local_segment = segment >> 1;
            const std::size_t port = local_segment < plan.max_cache_segments
                ? parity * 2
                : parity * 2 + 1;
            const std::size_t packed_slot =
                local_segment * kWeightedPmaSegmentSlots;
            assert(std::equal(
                shard.initial_pma_words.begin() + slot,
                shard.initial_pma_words.begin() +
                    slot + kWeightedPmaSegmentSlots,
                buffers.pma_words[port].begin() + packed_slot));
        }
    }

    bool rejected = false;
    try {
        (void)build_weighted_pma_runtime_plan(graph, 32, 1, 4096);
    } catch (const std::overflow_error &) {
        rejected = true;
    }
    assert(rejected);

    const auto u55c_plan = build_weighted_pma_runtime_plan(
        graph, 32, 23, 1ULL << 20,
        WeightedPmaChannelPolicy::lane_aware_u55c);
    for (const auto &region : u55c_plan.regions) {
        if (region.name.rfind("update", 0) == 0 ||
            region.name.rfind("pma", 0) == 0) {
            const std::size_t lane =
                static_cast<std::size_t>(region.name.back() - '0');
            const auto range =
                grasu::integration::kWeightedPmaU55cLaneChannelRanges[lane];
            assert(region.channel >= range.first);
            assert(region.channel < range.second);
            assert(region.channel_first == range.first);
            assert(region.channel_last == range.second);
        } else {
            assert(region.channel_first == 0);
            assert(region.channel_last == 23);
        }
    }
    return 0;
}
