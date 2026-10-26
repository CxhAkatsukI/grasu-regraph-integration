#include "weighted_pma_metadata_plan.hpp"

#include <cassert>

using namespace grasu::integration;

int main()
{
    const auto graph = build_weighted_partitioned_pma_graph(
        32, 16, {{0, 1, 1}, {1, 17, 2}}, {{2, 1, 3}});
    const auto original = build_weighted_pma_runtime_plan(
        graph, 16, 23, kU55cHbmPseudoChannelBytes,
        WeightedPmaChannelPolicy::lane_aware_u55c, true);
    const auto original_buffers = pack_weighted_pma_runtime_buffers(graph, original);
    auto replicated = replicate_weighted_pma_metadata(original);
    assert(replicated.regions.size() == original.regions.size() + 6);
    const auto packed = pack_weighted_pma_runtime_buffers(graph, replicated);
    for (std::size_t shard = 0; shard < packed.size(); ++shard) {
        assert(packed[shard].updates == original_buffers[shard].updates);
        assert(packed[shard].pma_words == original_buffers[shard].pma_words);
        assert(packed[shard].row_bounds == original_buffers[shard].row_bounds);
        assert(packed[shard].binary_heads == original_buffers[shard].binary_heads);
    }
    assert(find_weighted_pma_region(replicated, 0, "row1").channel == 6);
    assert(find_weighted_pma_region(replicated, 0, "binary3").channel == 18);
    auto constrained = original;
    constrained.channel_capacity_bytes = 16384;
    replicated = replicate_weighted_pma_metadata(constrained);
    std::size_t used = 0;
    for (const auto bytes : replicated.channel_load_bytes) {
        assert(bytes <= constrained.channel_capacity_bytes);
        used += bytes != 0;
    }
    assert(used > 4);
    bool rejected = false;
    constrained.channel_capacity_bytes = 1;
    try {
        (void)replicate_weighted_pma_metadata(constrained);
    } catch (const std::overflow_error &) {
        rejected = true;
    }
    assert(rejected);
}
