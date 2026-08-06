#include "weighted_pma_runtime_plan.hpp"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <stdexcept>
#include <vector>

using grasu::integration::WeightedEdgeRecord;
using grasu::integration::build_weighted_partitioned_pma_graph;
using grasu::integration::build_weighted_pma_runtime_plan;
using grasu::integration::find_weighted_pma_region;
using grasu::integration::kWeightedPmaSegmentSlots;
using grasu::integration::pack_weighted_pma_runtime_buffers;

int main()
{
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
    assert(packed.size() == graph.shards.size());
    for (std::size_t shard_index = 0; shard_index < graph.shards.size();
         ++shard_index) {
        const auto &shard = graph.shards[shard_index];
        const auto &buffers = packed[shard_index];
        assert(buffers.row_bounds == shard.row_bounds);
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
    return 0;
}
